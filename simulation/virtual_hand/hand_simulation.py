"""Ideal hand-observation and reconstruction simulation.

The observation hand uses all 24 Shadow Hand joints.  The reconstruction only
receives marker_id + XYZ packets and five raw flex values, then drives the same
24-joint model from 16 independent states (palm 6-DoF plus bend/spread per
finger).  No camera-image recognition, noise, occlusion, motor control or
contact dynamics are included in this first reference implementation.
"""

from __future__ import annotations

import argparse
import math
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import mujoco
import mujoco_menagerie
import numpy as np


FINGERS = ("thumb", "index", "middle", "ring", "little")
FINGER_CODES = {
    "thumb": "TH",
    "index": "FF",
    "middle": "MF",
    "ring": "RF",
    "little": "LF",
}

# Marker colours are RGB.  Thumb and little finger deliberately share red.
MARKER_COLOURS = {
    "thumb": (0.95, 0.15, 0.12, 1.0),
    "index": (0.15, 0.90, 0.25, 1.0),
    "middle": (0.15, 0.40, 1.00, 1.0),
    "ring": (1.00, 0.80, 0.10, 1.0),
    "little": (0.95, 0.15, 0.12, 1.0),
}

# Four asymmetric palm markers, expressed in the Shadow palm frame.
PALM_MARKERS = {
    "palm_wr": np.array((0.026, -0.018, 0.016)),
    "palm_wu": np.array((-0.026, -0.018, 0.016)),
    "palm_fr": np.array((0.026, -0.018, 0.076)),
    "palm_fu": np.array((-0.014, -0.018, 0.082)),
}
PALM_MARKER_COLOURS = {
    "palm_wr": (0.95, 0.15, 0.12, 1.0),
    "palm_wu": (0.15, 0.90, 0.25, 1.0),
    "palm_fr": (0.15, 0.40, 1.00, 1.0),
    "palm_fu": (1.00, 0.80, 0.10, 1.0),
}

# Finger marker sits halfway between MCP and PIP on the dorsal surface.
FINGER_MARKER_LOCAL = {
    "thumb": np.array((0.0, -0.012, 0.019)),
    "index": np.array((0.0, -0.012, 0.023)),
    "middle": np.array((0.0, -0.012, 0.023)),
    "ring": np.array((0.0, -0.012, 0.023)),
    "little": np.array((0.0, -0.012, 0.023)),
}
FINGER_BODY = {
    "thumb": "rh_thproximal",
    "index": "rh_ffproximal",
    "middle": "rh_mfproximal",
    "ring": "rh_rfproximal",
    "little": "rh_lfproximal",
}
TIP_BODY = {
    "thumb": "rh_thdistal",
    "index": "rh_ffdistal",
    "middle": "rh_mfdistal",
    "ring": "rh_rfdistal",
    "little": "rh_lfdistal",
}

# MCP locations in the palm frame.  Little finger metacarpal motion is fixed in
# this first version, so its knuckle position is constant as well.
FINGER_BASE_LOCAL = {
    "index": np.array((0.033, 0.0, 0.095)),
    "middle": np.array((0.011, 0.0, 0.099)),
    "ring": np.array((-0.011, 0.0, 0.095)),
    "little": np.array((-0.033, 0.0, 0.0865)),
    "thumb": np.array((0.034, -0.00858, 0.029)),
}

OBS_COLOUR = np.array((0.08, 0.48, 0.95, 1.0))
TELE_COLOUR = np.array((1.00, 0.42, 0.06, 0.58))
RAW_FLEX_MIN = 300
RAW_FLEX_MAX = 3700
FLEX_LUT = np.linspace(0.0, 1.0, 256, dtype=np.float64)
PREVIEW_PATH = Path("hand_simulation_preview.png")
MAX_SPREAD_ERROR_DEG = 5.0


@dataclass(slots=True)
class HandState:
    palm_position: np.ndarray
    palm_rotation: np.ndarray
    bend: np.ndarray
    spread: np.ndarray
    detail: np.ndarray


@dataclass(slots=True)
class SensorPacket:
    timestamp_us: int
    markers: dict[str, np.ndarray]
    flex_raw: np.ndarray


@dataclass(slots=True)
class Metrics:
    palm_position_mm: float
    palm_rotation_deg: float
    bend_deg: float
    spread_deg: float
    fingertip_mean_mm: float
    fingertip_max_mm: float


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm < 1e-9:
        raise ValueError("cannot normalize a zero-length vector")
    return vector / norm


def rotation_xyz(roll: float, pitch: float, yaw: float) -> np.ndarray:
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array(((1, 0, 0), (0, cr, -sr), (0, sr, cr)), dtype=float)
    ry = np.array(((cp, 0, sp), (0, 1, 0), (-sp, 0, cp)), dtype=float)
    rz = np.array(((cy, -sy, 0), (sy, cy, 0), (0, 0, 1)), dtype=float)
    return rz @ ry @ rx


def matrix_to_quaternion(rotation: np.ndarray) -> np.ndarray:
    quaternion = np.empty(4, dtype=float)
    mujoco.mju_mat2Quat(quaternion, np.asarray(rotation, dtype=float).reshape(9))
    return quaternion


def rotation_error_deg(first: np.ndarray, second: np.ndarray) -> float:
    cosine = clamp((float(np.trace(first.T @ second)) - 1.0) * 0.5, -1.0, 1.0)
    return math.degrees(math.acos(cosine))


def wrap_angle(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def _colour_visual_geoms(spec: mujoco.MjSpec, colour: np.ndarray) -> None:
    for geom in spec.geoms:
        if geom.group == 2:
            geom.rgba = colour


def _add_sites(spec: mujoco.MjSpec) -> None:
    palm = spec.body("rh_palm")
    for marker_id, position in PALM_MARKERS.items():
        palm.add_site(
            name=f"marker_{marker_id}",
            pos=position,
            size=(0.006, 0.0, 0.0),
            type=mujoco.mjtGeom.mjGEOM_SPHERE,
            rgba=PALM_MARKER_COLOURS[marker_id],
            group=0,
        )

    for finger in FINGERS:
        spec.body(FINGER_BODY[finger]).add_site(
            name=f"marker_{finger}",
            pos=FINGER_MARKER_LOCAL[finger],
            size=(0.006, 0.0, 0.0),
            type=mujoco.mjtGeom.mjGEOM_SPHERE,
            rgba=MARKER_COLOURS[finger],
            group=0,
        )
        spec.body(TIP_BODY[finger]).add_site(
            name=f"tip_{finger}",
            pos=(0.0, 0.0, 0.025),
            size=(0.002, 0.0, 0.0),
            type=mujoco.mjtGeom.mjGEOM_SPHERE,
            rgba=(1.0, 1.0, 1.0, 0.15),
            group=1,
        )


def _hand_spec(model_path: Path, colour: np.ndarray) -> mujoco.MjSpec:
    spec = mujoco.MjSpec.from_file(str(model_path))
    _colour_visual_geoms(spec, colour)
    _add_sites(spec)
    return spec


def build_scene() -> tuple[mujoco.MjModel, mujoco.MjData]:
    cache = mujoco_menagerie.Cache(".menagerie-cache")
    model_path = mujoco_menagerie.get("shadow_hand").xml("right_hand", cache)

    scene = mujoco.MjSpec.from_string(
        """
        <mujoco model="ideal_hand_reconstruction">
          <option gravity="0 0 0" timestep="0.01" cone="elliptic" impratio="10"/>
          <visual>
            <global offwidth="1280" offheight="720"/>
            <quality shadowsize="4096"/>
            <map znear="0.01" zfar="5"/>
            <rgba haze="0.04 0.06 0.10 1"/>
          </visual>
          <asset>
            <texture type="skybox" builtin="gradient"
                     rgb1="0.08 0.11 0.18" rgb2="0.005 0.008 0.015"
                     width="512" height="3072"/>
            <texture name="floor_tex" type="2d" builtin="checker"
                     rgb1="0.09 0.11 0.15" rgb2="0.035 0.045 0.065"
                     mark="edge" markrgb="0.18 0.22 0.30"
                     width="512" height="512"/>
            <material name="floor_mat" texture="floor_tex"
                      texrepeat="5 5" texuniform="true" reflectance="0.18"/>
          </asset>
          <worldbody>
            <light pos="0 -0.6 1.2" dir="0 0.35 -1" directional="true" diffuse="0.9 0.9 1"/>
            <light pos="0.7 -0.2 0.7" dir="-1 0 -0.4" directional="true" diffuse="0.45 0.55 0.8"/>
            <geom name="floor" type="plane" pos="0 0 0" size="2 2 0.05" material="floor_mat"/>
          </worldbody>
        </mujoco>
        """
    )
    observation_root = scene.worldbody.add_body(name="obs_root")
    observation_root.add_joint(name="obs_ROOT", type=mujoco.mjtJoint.mjJNT_FREE)
    observation_frame = observation_root.add_frame(name="observation_mount")
    reconstruction_root = scene.worldbody.add_body(name="tele_root")
    reconstruction_root.add_joint(name="tele_ROOT", type=mujoco.mjtJoint.mjJNT_FREE)
    reconstruction_frame = reconstruction_root.add_frame(name="reconstruction_mount")
    scene.attach(
        _hand_spec(model_path, OBS_COLOUR),
        prefix="obs_",
        frame=observation_frame,
    )
    scene.attach(
        _hand_spec(model_path, TELE_COLOUR),
        prefix="tele_",
        frame=reconstruction_frame,
    )
    model = scene.compile()
    data = mujoco.MjData(model)
    data.qpos[:] = model.qpos0
    mujoco.mj_forward(model, data)
    return model, data


class HandSimulation:
    def __init__(self) -> None:
        self.model, self.data = build_scene()
        self.root_addresses = {
            prefix: int(self.model.jnt_qposadr[self.model.joint(f"{prefix}ROOT").id])
            for prefix in ("obs_", "tele_")
        }
        self.rest_palm = {}
        for prefix in ("obs_", "tele_"):
            palm = self.data.body(f"{prefix}rh_palm")
            self.rest_palm[prefix] = (
                np.array(palm.xpos, dtype=float),
                np.array(palm.xmat, dtype=float).reshape(3, 3),
            )
        self.last_spread = np.zeros(5, dtype=float)

    def _joint_address(self, prefix: str, joint_name: str) -> int:
        return int(self.model.jnt_qposadr[self.model.joint(f"{prefix}{joint_name}").id])

    def set_joint(self, prefix: str, joint_name: str, value: float) -> None:
        joint = self.model.joint(f"{prefix}{joint_name}")
        low, high = self.model.jnt_range[joint.id]
        address = int(self.model.jnt_qposadr[joint.id])
        self.data.qpos[address] = clamp(value, float(low), float(high))

    def set_palm_pose(self, prefix: str, position: np.ndarray, rotation: np.ndarray) -> None:
        rest_position, rest_rotation = self.rest_palm[prefix]
        root_rotation = rotation @ rest_rotation.T
        root_position = position - root_rotation @ rest_position
        address = self.root_addresses[prefix]
        self.data.qpos[address : address + 3] = root_position
        self.data.qpos[address + 3 : address + 7] = matrix_to_quaternion(root_rotation)

    def apply_observation(self, state: HandState) -> None:
        self.set_palm_pose("obs_", state.palm_position, state.palm_rotation)
        for index, finger in enumerate(FINGERS):
            bend = float(state.bend[index])
            spread = float(state.spread[index])
            detail = float(state.detail[index])
            code = FINGER_CODES[finger]
            if finger == "thumb":
                self.set_joint("obs_", "rh_THJ5", 0.70 * spread)
                self.set_joint("obs_", "rh_THJ4", bend * (0.78 + 0.05 * detail))
                self.set_joint("obs_", "rh_THJ3", 0.10 * detail)
                self.set_joint("obs_", "rh_THJ2", bend * (0.46 - 0.04 * detail))
                self.set_joint("obs_", "rh_THJ1", bend * (1.05 + 0.08 * detail))
            else:
                self.set_joint("obs_", f"rh_{code}J4", 0.28 * spread)
                self.set_joint("obs_", f"rh_{code}J3", bend * (1.12 + 0.10 * detail))
                self.set_joint("obs_", f"rh_{code}J2", bend * (1.25 - 0.08 * detail))
                self.set_joint("obs_", f"rh_{code}J1", bend * (0.92 + 0.06 * detail))
                if finger == "little":
                    self.set_joint("obs_", "rh_LFJ5", 0.0)

    def apply_reconstruction(self, state: HandState) -> None:
        self.set_palm_pose("tele_", state.palm_position, state.palm_rotation)
        for index, finger in enumerate(FINGERS):
            bend = float(state.bend[index])
            spread = float(state.spread[index])
            code = FINGER_CODES[finger]
            if finger == "thumb":
                self.set_joint("tele_", "rh_THJ5", 0.70 * spread)
                self.set_joint("tele_", "rh_THJ4", 0.78 * bend)
                self.set_joint("tele_", "rh_THJ3", 0.0)
                self.set_joint("tele_", "rh_THJ2", 0.46 * bend)
                self.set_joint("tele_", "rh_THJ1", 1.05 * bend)
            else:
                self.set_joint("tele_", f"rh_{code}J4", 0.28 * spread)
                self.set_joint("tele_", f"rh_{code}J3", 1.12 * bend)
                self.set_joint("tele_", f"rh_{code}J2", 1.25 * bend)
                self.set_joint("tele_", f"rh_{code}J1", 0.92 * bend)
                if finger == "little":
                    self.set_joint("tele_", "rh_LFJ5", 0.0)

    def _joint_value(self, prefix: str, joint_name: str) -> float:
        return float(self.data.qpos[self._joint_address(prefix, joint_name)])

    def read_sensor_packet(self, timestamp_us: int) -> SensorPacket:
        mujoco.mj_forward(self.model, self.data)
        markers = {}
        for marker_id in (*PALM_MARKERS, *FINGERS):
            markers[marker_id] = np.array(
                self.data.site(f"obs_marker_{marker_id}").xpos,
                dtype=float,
            )

        bend_values = []
        for finger in FINGERS:
            code = FINGER_CODES[finger]
            if finger == "thumb":
                bend = (
                    0.42 * self._joint_value("obs_", "rh_THJ4") / 0.78
                    + 0.23 * self._joint_value("obs_", "rh_THJ2") / 0.46
                    + 0.35 * self._joint_value("obs_", "rh_THJ1") / 1.05
                )
            else:
                bend = (
                    0.42 * self._joint_value("obs_", f"rh_{code}J3") / 1.12
                    + 0.33 * self._joint_value("obs_", f"rh_{code}J2") / 1.25
                    + 0.25 * self._joint_value("obs_", f"rh_{code}J1") / 0.92
                )
            bend_values.append(clamp(bend, 0.0, 1.0))

        raw = np.rint(RAW_FLEX_MIN + np.asarray(bend_values) * (RAW_FLEX_MAX - RAW_FLEX_MIN))
        return SensorPacket(timestamp_us, markers, raw.astype(np.uint16))

    @staticmethod
    def _estimate_palm(markers: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        wrist_mid = 0.5 * (markers["palm_wr"] + markers["palm_wu"])
        finger_mid = 0.5 * (markers["palm_fr"] + markers["palm_fu"])
        axis_x = normalize(markers["palm_wr"] - markers["palm_wu"])
        rough_z = normalize(finger_mid - wrist_mid)
        axis_y = normalize(np.cross(rough_z, axis_x))
        axis_z = normalize(np.cross(axis_x, axis_y))
        rotation = np.column_stack((axis_x, axis_y, axis_z))

        local_points = np.stack([PALM_MARKERS[name] for name in PALM_MARKERS])
        world_points = np.stack([markers[name] for name in PALM_MARKERS])
        position = world_points.mean(axis=0) - rotation @ local_points.mean(axis=0)
        return position, rotation

    @staticmethod
    def _decode_flex(raw_values: np.ndarray) -> np.ndarray:
        indices = np.rint(
            (raw_values.astype(float) - RAW_FLEX_MIN)
            / (RAW_FLEX_MAX - RAW_FLEX_MIN)
            * (len(FLEX_LUT) - 1)
        ).astype(int)
        return FLEX_LUT[np.clip(indices, 0, len(FLEX_LUT) - 1)]

    @staticmethod
    def _estimate_spread(
        finger: str,
        marker_local: np.ndarray,
        bend: float,
    ) -> float | None:
        vector = marker_local - FINGER_BASE_LOCAL[finger]
        if finger in ("index", "middle"):
            # At deep flexion the marker can briefly lie on the spread axis;
            # one 3-D point then contains no spread information.  The caller
            # holds the previous estimate until the marker leaves that axis.
            if math.hypot(float(vector[0]), float(vector[2])) < 0.002:
                return None
            flexed = rotation_xyz(1.12 * bend, 0.0, 0.0) @ FINGER_MARKER_LOCAL[finger]
            measured = math.atan2(-float(vector[0]), float(vector[2]))
            reference = math.atan2(0.0, float(flexed[2]))
            joint_angle = wrap_angle(measured - reference)
            return clamp(joint_angle / 0.28, -1.0, 1.0)
        if finger in ("ring", "little"):
            if math.hypot(float(vector[0]), float(vector[2])) < 0.002:
                return None
            flexed = rotation_xyz(1.12 * bend, 0.0, 0.0) @ FINGER_MARKER_LOCAL[finger]
            measured = math.atan2(float(vector[0]), float(vector[2]))
            reference = math.atan2(0.0, float(flexed[2]))
            joint_angle = wrap_angle(measured - reference)
            return clamp(joint_angle / 0.28, -1.0, 1.0)

        # Thumb base is rotated +45 degrees around palm Y.  Convert the marker
        # vector into that fixed base frame before recovering THJ5 around -Z.
        c = math.sqrt(0.5)
        base_rotation = np.array(((c, 0.0, c), (0.0, 1.0, 0.0), (-c, 0.0, c)))
        vector_base = base_rotation.T @ vector
        if math.hypot(float(vector_base[0]), float(vector_base[1])) < 0.002:
            return None
        flexed = rotation_xyz(0.78 * bend, 0.0, 0.0) @ FINGER_MARKER_LOCAL[finger]
        measured = math.atan2(-float(vector_base[0]), -float(vector_base[1]))
        reference = math.atan2(-float(flexed[0]), -float(flexed[1]))
        joint_angle = wrap_angle(measured - reference)
        return clamp(joint_angle / 0.70, -1.0, 1.0)

    def reconstruct(self, packet: SensorPacket) -> HandState:
        position, rotation = self._estimate_palm(packet.markers)
        bend = self._decode_flex(packet.flex_raw)
        spread = []
        for index, finger in enumerate(FINGERS):
            marker_local = rotation.T @ (packet.markers[finger] - position)
            estimate = self._estimate_spread(finger, marker_local, float(bend[index]))
            spread.append(self.last_spread[index] if estimate is None else estimate)
        self.last_spread[:] = spread
        return HandState(
            palm_position=position,
            palm_rotation=rotation,
            bend=bend,
            spread=np.asarray(spread),
            detail=np.zeros(5),
        )

    def fingertip_positions(self, prefix: str) -> np.ndarray:
        return np.stack(
            [np.array(self.data.site(f"{prefix}tip_{finger}").xpos) for finger in FINGERS]
        )

    def evaluate(self, truth: HandState, estimated: HandState) -> Metrics:
        mujoco.mj_forward(self.model, self.data)
        observed_tips = self.fingertip_positions("obs_")
        reconstructed_tips = self.fingertip_positions("tele_")
        tip_errors = np.linalg.norm(observed_tips - reconstructed_tips, axis=1) * 1000.0
        return Metrics(
            palm_position_mm=float(np.linalg.norm(truth.palm_position - estimated.palm_position) * 1000.0),
            palm_rotation_deg=rotation_error_deg(truth.palm_rotation, estimated.palm_rotation),
            bend_deg=float(np.max(np.abs(truth.bend - estimated.bend)) * 90.0),
            spread_deg=float(np.max(np.abs(truth.spread - estimated.spread)) * 20.0),
            fingertip_mean_mm=float(np.mean(tip_errors)),
            fingertip_max_mm=float(np.max(tip_errors)),
        )

    def set_display_offsets(self, observation_x: float, reconstruction_x: float) -> None:
        for prefix, offset in (("obs_", observation_x), ("tele_", reconstruction_x)):
            address = self.root_addresses[prefix]
            self.data.qpos[address] += offset
        mujoco.mj_forward(self.model, self.data)


def static_pose(name: str) -> HandState:
    poses = {
        "open": (np.zeros(5), np.zeros(5)),
        "fist": (np.ones(5) * 0.92, np.zeros(5)),
        "spread": (np.zeros(5), np.array((-0.55, 0.65, 0.18, -0.18, -0.65))),
        "point": (np.array((0.65, 0.05, 0.90, 0.92, 0.95)), np.zeros(5)),
        "thumb": (np.array((0.82, 0.16, 0.16, 0.16, 0.16)), np.array((0.70, 0, 0, 0, 0))),
    }
    bend, spread = poses[name]
    return HandState(
        palm_position=np.array((0.0, 0.0, 0.31)),
        palm_rotation=rotation_xyz(math.radians(-8), math.radians(3), math.radians(4)),
        bend=bend.copy(),
        spread=spread.copy(),
        detail=np.array((0.35, -0.30, 0.20, -0.25, 0.30)),
    )


def animated_pose(seconds: float) -> HandState:
    bend_phase = np.array((0.0, 0.6, 1.2, 1.8, 2.4))
    spread_phase = np.array((0.8, 0.0, 0.4, 0.8, 1.2))
    bend = 0.48 + 0.42 * np.sin(seconds * 1.15 + bend_phase)
    spread = 0.62 * np.sin(seconds * 0.72 + spread_phase)
    detail = 0.35 * np.sin(seconds * 0.91 + bend_phase * 1.7)
    position = np.array(
        (
            0.025 * math.sin(seconds * 0.55),
            0.018 * math.sin(seconds * 0.43),
            0.31 + 0.018 * math.cos(seconds * 0.49),
        )
    )
    rotation = rotation_xyz(
        math.radians(10.0) * math.sin(seconds * 0.43),
        math.radians(8.0) * math.sin(seconds * 0.37),
        math.radians(12.0) * math.sin(seconds * 0.31),
    )
    return HandState(position, rotation, bend, spread, detail)


def solve_frame(simulation: HandSimulation, truth: HandState, timestamp_us: int) -> tuple[HandState, Metrics]:
    simulation.data.qpos[:] = simulation.model.qpos0
    simulation.apply_observation(truth)
    mujoco.mj_forward(simulation.model, simulation.data)
    packet = simulation.read_sensor_packet(timestamp_us)
    estimated = simulation.reconstruct(packet)
    simulation.apply_reconstruction(estimated)
    mujoco.mj_forward(simulation.model, simulation.data)
    metrics = simulation.evaluate(truth, estimated)
    return estimated, metrics


def _camera(distance: float) -> mujoco.MjvCamera:
    camera = mujoco.MjvCamera()
    camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    camera.lookat[:] = (0.0, 0.0, 0.30)
    camera.distance = distance
    camera.azimuth = 92.0
    camera.elevation = -18.0
    return camera


def render_frame(
    simulation: HandSimulation,
    renderer: mujoco.Renderer,
    truth: HandState,
    estimated: HandState,
    metrics: Metrics,
) -> np.ndarray:
    # Side-by-side panel.
    simulation.set_palm_pose("obs_", truth.palm_position, truth.palm_rotation)
    simulation.set_palm_pose("tele_", estimated.palm_position, estimated.palm_rotation)
    simulation.set_display_offsets(-0.145, 0.145)
    renderer.update_scene(simulation.data, camera=_camera(0.72))
    side = renderer.render().copy()

    # Overlap panel, with the reconstruction rendered semi-transparent.
    simulation.set_palm_pose("obs_", truth.palm_position, truth.palm_rotation)
    simulation.set_palm_pose("tele_", estimated.palm_position, estimated.palm_rotation)
    mujoco.mj_forward(simulation.model, simulation.data)
    renderer.update_scene(simulation.data, camera=_camera(0.62))
    overlap = renderer.render().copy()

    frame = np.concatenate((side, overlap), axis=1)
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    height, width = frame.shape[:2]
    cv2.line(frame, (width // 2, 0), (width // 2, height), (75, 85, 105), 2)
    cv2.putText(frame, "OBSERVATION / RECONSTRUCTION", (24, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (245, 245, 245), 2, cv2.LINE_AA)
    cv2.putText(frame, "OVERLAP", (width // 2 + 24, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (245, 245, 245), 2, cv2.LINE_AA)
    lines = (
        f"Palm position : {metrics.palm_position_mm:6.2f} mm",
        f"Palm rotation : {metrics.palm_rotation_deg:6.2f} deg",
        f"Bend max      : {metrics.bend_deg:6.2f} deg",
        f"Spread max    : {metrics.spread_deg:6.2f} deg",
        f"Tip mean/max  : {metrics.fingertip_mean_mm:5.1f} / {metrics.fingertip_max_mm:5.1f} mm",
    )
    panel_x = width // 2 + 24
    panel_y = height - 142
    cv2.rectangle(frame, (panel_x - 10, panel_y - 30), (width - 18, height - 18), (14, 18, 28), -1)
    for index, line in enumerate(lines):
        cv2.putText(frame, line, (panel_x, panel_y + index * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 235, 245), 1, cv2.LINE_AA)
    return frame


def run_headless(args: argparse.Namespace) -> int:
    simulation = HandSimulation()
    samples = []
    last = None
    for frame_index in range(args.frames):
        seconds = frame_index / 60.0
        truth = static_pose(args.pose) if args.pose else animated_pose(seconds)
        estimated, metrics = solve_frame(simulation, truth, int(seconds * 1_000_000))
        samples.append(metrics)
        last = (truth, estimated, metrics)

    assert last is not None
    renderer = mujoco.Renderer(simulation.model, height=540, width=640)
    preview = render_frame(simulation, renderer, *last)
    renderer.close()
    if not cv2.imwrite(str(args.output), preview):
        raise RuntimeError(f"无法保存预览图: {args.output}")

    maxima = Metrics(
        *(max(getattr(sample, field) for sample in samples) for field in Metrics.__dataclass_fields__)
    )
    print(f"frames={args.frames}")
    print(f"preview={args.output.resolve()}")
    print(
        "max_errors",
        f"palm_mm={maxima.palm_position_mm:.3f}",
        f"rotation_deg={maxima.palm_rotation_deg:.3f}",
        f"bend_deg={maxima.bend_deg:.3f}",
        f"spread_deg={maxima.spread_deg:.3f}",
        f"tip_mean_mm={maxima.fingertip_mean_mm:.3f}",
        f"tip_max_mm={maxima.fingertip_max_mm:.3f}",
    )
    passed = (
        maxima.palm_position_mm < 2.0
        and maxima.palm_rotation_deg < 1.0
        and maxima.bend_deg < 2.0
        and maxima.spread_deg < MAX_SPREAD_ERROR_DEG
        and maxima.fingertip_mean_mm < 15.0
        and maxima.fingertip_max_mm < 25.0
    )
    print("RESULT", "PASS" if passed else "FAIL")
    return 0 if passed else 1


def run_window(args: argparse.Namespace) -> int:
    simulation = HandSimulation()
    renderer = mujoco.Renderer(simulation.model, height=540, width=640)
    started = time.perf_counter()
    cv2.namedWindow("Ideal hand reconstruction - Q/Esc quit", cv2.WINDOW_NORMAL)
    try:
        while True:
            seconds = time.perf_counter() - started
            truth = static_pose(args.pose) if args.pose else animated_pose(seconds)
            estimated, metrics = solve_frame(simulation, truth, int(seconds * 1_000_000))
            frame = render_frame(simulation, renderer, truth, estimated, metrics)
            cv2.imshow("Ideal hand reconstruction - Q/Esc quit", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                return 0
    finally:
        renderer.close()
        cv2.destroyAllWindows()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true", help="run numerical validation and save one preview")
    parser.add_argument("--frames", type=int, default=240, help="headless validation frame count")
    parser.add_argument("--pose", choices=("open", "fist", "spread", "point", "thumb"), help="hold a static pose")
    parser.add_argument("--output", type=Path, default=PREVIEW_PATH, help="headless preview image")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.frames <= 0:
        raise ValueError("--frames must be positive")
    if args.headless:
        return run_headless(args)
    return run_window(args)


if __name__ == "__main__":
    raise SystemExit(main())

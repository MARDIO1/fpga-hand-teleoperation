"""Drive the local MANO hand from the canonical camera/IMU/flex sequence."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import mujoco
import numpy as np

from hand_sequence import (FINGERS, WristTracker, demo_sequence, load_sequence,
                           save_sequence, static_frame)
from mano_mapping import map_hand_pose


ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / ".runtime" / "DexHOI2Sim"
HAND_DIR = ROOT / ".runtime" / "mano_hand"
PREVIEW = ROOT / "mano_controller_preview.png"
DEMO_SEQUENCE = ROOT / ".runtime" / "demo_sequence.npz"
TIP_BODIES = {
    "thumb": "right_thumb3",
    "index": "right_index3",
    "middle": "right_middle3",
    "ring": "right_ring3",
    "little": "right_pinky3",
}


def _load_upstream():
    if not (HAND_DIR / "teleop_hand.urdf").is_file():
        raise RuntimeError("MANO runtime missing; run prepare_mano_runtime.py first")
    sys.path.insert(0, str(UPSTREAM / "sim"))
    from mano2urdf_mujoco import build_hand_model, build_qpos_indexer, hide_collision_geoms
    return build_hand_model, build_qpos_indexer, hide_collision_geoms


class ManoController:
    def __init__(self, width: int = 420, height: int = 420) -> None:
        build_model, build_indexer, hide_collisions = _load_upstream()
        self.model, _ = build_model(HAND_DIR, gravity=0.0, floor_z=-0.12,
                                    cam_pos="0 -0.62 0.38", lookat="0 0 0.38",
                                    actuated=False)
        hide_collisions(self.model)
        self.data = mujoco.MjData(self.model)
        self.to_qpos = build_indexer(self.model)
        self.renderer = mujoco.Renderer(self.model, height=height, width=width)
        self.address = {
            mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, joint):
            int(self.model.jnt_qposadr[joint]) for joint in range(self.model.njnt)
        }

    def close(self) -> None:
        self.renderer.close()

    def apply(self, sensor_frame) -> dict:
        payload = map_hand_pose(sensor_frame).as_upstream_frame()
        self.data.qpos[:] = self.model.qpos0
        self.to_qpos(payload, self.data.qpos)
        mujoco.mj_forward(self.model, self.data)
        return payload

    def render(self) -> np.ndarray:
        self.renderer.update_scene(self.data, camera="view")
        return self.renderer.render().copy()

    def tip_positions(self) -> np.ndarray:
        return np.stack([np.asarray(self.data.body(TIP_BODIES[name]).xpos).copy() for name in FINGERS])


def _verify(controller: ManoController) -> tuple[float, np.ndarray]:
    maximum_error = 0.0
    controller.apply(static_frame("open"))
    open_tips = controller.tip_positions()
    for pose_name in ("open", "relaxed", "fist", "point", "thumb"):
        payload = controller.apply(static_frame(pose_name))
        expected = {
            "right_wrist_0x": payload["wrist_xyz"][0],
            "right_wrist_0y": payload["wrist_xyz"][1],
            "right_wrist_0z": payload["wrist_xyz"][2],
            "right_wrist_0rx": payload["wrist_rpy"][0],
            "right_wrist_0ry": payload["wrist_rpy"][1],
            "right_wrist_0rz": payload["wrist_rpy"][2],
            **payload["joint_angles"],
        }
        for name, value in expected.items():
            error = abs(float(controller.data.qpos[controller.address[name]]) - value)
            maximum_error = max(maximum_error, error)

    movement = []
    for index in range(5):
        frame = static_frame("open")
        frame.bend[index] = 1.0
        controller.apply(frame)
        movement.append(np.linalg.norm(controller.tip_positions()[index] - open_tips[index]) * 1000.0)
    return maximum_error, np.asarray(movement)


def _preview(controller: ManoController, output: Path) -> None:
    panels = []
    for name in ("open", "relaxed", "fist", "point", "thumb"):
        controller.apply(static_frame(name))
        panel = cv2.cvtColor(controller.render(), cv2.COLOR_RGB2BGR)
        cv2.putText(panel, name.upper(), (18, 34), cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (245, 245, 245), 2, cv2.LINE_AA)
        panels.append(panel)
    if not cv2.imwrite(str(output), np.concatenate(panels, axis=1)):
        raise RuntimeError(f"cannot write {output}")


def _sequence(path: Path | None, frame_count: int) -> list:
    if path:
        return load_sequence(path)
    frames = demo_sequence(frame_count)
    DEMO_SEQUENCE.parent.mkdir(parents=True, exist_ok=True)
    save_sequence(DEMO_SEQUENCE, frames)
    return load_sequence(DEMO_SEQUENCE)


def run_headless(args: argparse.Namespace) -> int:
    controller = ManoController()
    frames = _sequence(args.sequence, args.frames)
    tracker = WristTracker()
    try:
        maximum_error, movement = _verify(controller)
        for frame in frames:
            controller.apply(tracker.update(frame))
        _preview(controller, args.output)
    finally:
        controller.close()

    passed = maximum_error < 1e-9 and bool(np.all(movement > 5.0))
    print(f"sequence_frames={len(frames)}")
    print(f"qpos_max_error={maximum_error:.3e}")
    print("tip_movement_mm=" + ",".join(f"{value:.2f}" for value in movement))
    print(f"preview={args.output.resolve()}")
    print("RESULT", "PASS" if passed else "FAIL")
    return 0 if passed else 1


def run_window(args: argparse.Namespace) -> int:
    import mujoco.viewer

    controller = ManoController()
    frames = _sequence(args.sequence, args.frames)
    tracker = WristTracker()
    index = 0
    try:
        with mujoco.viewer.launch_passive(controller.model, controller.data) as viewer:
            while viewer.is_running():
                controller.apply(tracker.update(frames[index]))
                viewer.sync()
                index = (index + 1) % len(frames)
                if index == 0:
                    tracker = WristTracker()
                time.sleep(1.0 / 60.0)
    finally:
        controller.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--frames", type=int, default=240)
    parser.add_argument("--sequence", type=Path)
    parser.add_argument("--output", type=Path, default=PREVIEW)
    args = parser.parse_args()
    return run_headless(args) if args.headless else run_window(args)


if __name__ == "__main__":
    raise SystemExit(main())

"""Collision-aware SO-101 end-effector controller built on Mink."""

from __future__ import annotations

import mink
import mujoco
import numpy as np

from mapping import (EndEffectorMapper, gripper_command, load_axis_calibration,
                     matrix_rpy_degrees)
from protocol import SensorSample
from scene import collision_groups, load_model


ARM_JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex",
              "wrist_flex", "wrist_roll")
STANDARD_POSITION = np.array((0.30, 0.0, 0.20))
STANDARD_ROTATION = np.eye(3)


class So101Twin:
    def __init__(self, position_scale: float = 1.0,
                 calibration_path=None) -> None:
        self.model = load_model()
        self.data = mujoco.MjData(self.model)
        mujoco.mj_resetDataKeyframe(self.model, self.data, 0)
        mujoco.mj_forward(self.model, self.data)

        self.configuration = mink.Configuration(self.model, self.data.qpos.copy())
        axis_calibration, yaw_gain = load_axis_calibration(calibration_path)
        self.mapper = EndEffectorMapper(STANDARD_POSITION, STANDARD_ROTATION,
                                        position_scale, yaw_gain, axis_calibration)

        self.pose_task = mink.FrameTask("gripperframe", "site", position_cost=60.0,
                                        orientation_cost=0.12, gain=0.75,
                                        lm_damping=1e-3)
        self.axis_task = mink.AxisAlignTask("gripperframe", "site", axis=(0, 0, 1),
                                            cost=30.0, gain=0.75,
                                            lm_damping=1e-3)
        posture_cost = np.zeros(self.model.nv)
        posture_cost[:5] = (0.05, 0.04, 0.035, 0.02, 0.012)
        self.posture_task = mink.PostureTask(self.model, cost=posture_cost)
        self.posture_task.set_target_from_configuration(self.configuration)
        self.tasks = [self.pose_task, self.axis_task, self.posture_task,
                      mink.DampingTask(self.model, cost=1e-3)]
        self.limits = self._limits()

        self.arm_qpos = np.array([
            self.model.jnt_qposadr[self.model.joint(name).id] for name in ARM_JOINTS
        ])
        self.gripper_joint = self.model.joint("gripper").id
        self.gripper_qpos = int(self.model.jnt_qposadr[self.gripper_joint])
        self.target_mocap = int(self.model.body("ee_target").mocapid[0])
        self.data.ctrl[:] = self.data.qpos[:self.model.nu]
        self.position_error = 0.0
        self.axis_error = 0.0
        self.target_position = STANDARD_POSITION.copy()
        self.target_rotation = STANDARD_ROTATION.copy()

    def _limits(self) -> list:
        groups = collision_groups(self.model)
        distal = groups["gripper"] + groups["camera_mount"] + groups["moving_jaw_so101_v1"]
        pairs = [
            (groups["shoulder"], groups["lower_arm"] + groups["wrist"] + distal),
            (groups["upper_arm"], groups["wrist"] + distal),
            (groups["lower_arm"], distal),
            (groups["upper_arm"] + groups["lower_arm"] + groups["wrist"] + distal,
             groups["world"]),
        ]
        collision = mink.CollisionAvoidanceLimit(
            self.model, pairs, minimum_distance_from_collisions=0.003,
            collision_detection_distance=0.045, gain=0.8)
        velocities = dict(zip(ARM_JOINTS, (1.2, 1.0, 1.2, 1.5, 2.0), strict=True))
        return [mink.ConfigurationLimit(self.model),
                mink.VelocityLimit(self.model, velocities), collision]

    def reset_reference(self) -> None:
        self.mapper.reset()

    def step(self, sample: SensorSample, seconds: float = 1.0 / 60.0) -> None:
        target_position, target_rotation = self.mapper.update(sample)
        self.target_position = target_position.copy()
        self.target_rotation = target_rotation.copy()
        target = mink.SE3.from_rotation_and_translation(
            mink.SO3.from_matrix(target_rotation), target_position)
        self.pose_task.set_target(target)
        self.axis_task.set_target(target_rotation @ np.array((0.0, 0.0, 1.0)))

        self.configuration.update(self.data.qpos)
        velocity = mink.solve_ik(self.configuration, self.tasks, seconds, "daqp",
                                 limits=self.limits, damping=1e-6)
        command = self.configuration.integrate(velocity, seconds)
        self.data.ctrl[:5] = command[self.arm_qpos]
        self.data.ctrl[5] = gripper_command(
            sample.bend, self.model.jnt_range[self.gripper_joint])

        self.data.mocap_pos[self.target_mocap] = target_position
        self.data.mocap_quat[self.target_mocap] = mink.SO3.from_matrix(target_rotation).parameters()
        for _ in range(max(1, round(seconds / self.model.opt.timestep))):
            mujoco.mj_step(self.model, self.data)

        actual = self.data.site("gripperframe")
        self.position_error = float(np.linalg.norm(actual.xpos - target_position))
        self.axis_error = float(np.arccos(np.clip(
            (actual.xmat.reshape(3, 3) @ np.array((0.0, 0.0, 1.0))) @
            (target_rotation @ np.array((0.0, 0.0, 1.0))), -1.0, 1.0)))

    @property
    def reach_limited(self) -> bool:
        return self.position_error > 0.02 or self.axis_error > np.deg2rad(12.0)

    def telemetry(self) -> str:
        actual = self.data.site("gripperframe")
        target_rpy = matrix_rpy_degrees(self.target_rotation)
        actual_rpy = matrix_rpy_degrees(actual.xmat.reshape(3, 3))
        source_rpy = self.mapper.relative_rpy_degrees
        values = np.concatenate((source_rpy, self.target_position, actual.xpos,
                                 target_rpy, actual_rpy))
        text = " ".join(f"{value:7.2f}" for value in values)
        return ("imu_rpy_deg target_xyz actual_xyz target_rpy_deg actual_rpy_deg | "
                + text)


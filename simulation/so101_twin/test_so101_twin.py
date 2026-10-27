"""Focused checks for the independent SO-101 digital twin."""

import unittest

import numpy as np

from controller import ARM_JOINTS, STANDARD_POSITION, STANDARD_ROTATION, So101Twin
from mapping import EndEffectorMapper, gripper_command
from protocol import SensorSample, demo_sequence


class So101TwinTest(unittest.TestCase):
    def setUp(self) -> None:
        self.twin = So101Twin()

    def test_curated_model_and_controller(self) -> None:
        self.assertEqual(tuple(self.twin.model.joint(i).name for i in range(5)), ARM_JOINTS)
        self.assertEqual(self.twin.model.nu, 6)
        self.assertGreater(len(self.twin.limits), 2)

    def test_middle_bend_controls_gripper(self) -> None:
        joint_range = self.twin.model.jnt_range[self.twin.gripper_joint]
        opened = gripper_command(np.zeros(5), joint_range)
        bend = np.zeros(5)
        bend[2] = 1.0
        closed = gripper_command(bend, joint_range)
        self.assertGreater(opened, closed)

    def test_standard_hand_pose_has_explicit_robot_target(self) -> None:
        sample = SensorSample(0, False, True, True, np.zeros(3),
                              np.array((1.0, 0.0, 0.0, 0.0)), np.zeros(5))
        position, rotation = self.twin.mapper.update(sample)
        np.testing.assert_allclose(position, STANDARD_POSITION)
        np.testing.assert_allclose(rotation, STANDARD_ROTATION, atol=1e-12)

    def test_sequence_stays_finite(self) -> None:
        for sample in demo_sequence(240):
            self.twin.step(sample)
        self.assertTrue(np.isfinite(self.twin.data.qpos).all())
        self.assertLess(self.twin.position_error, 0.02)

    def test_unreachable_target_stops_at_limits(self) -> None:
        samples = demo_sequence(2)
        self.twin.step(samples[0])
        samples[1].wrist_xyz[2] += 1.0
        for _ in range(120):
            self.twin.step(samples[1])
        self.assertTrue(np.isfinite(self.twin.data.qpos).all())
        self.assertTrue(self.twin.reach_limited)
        for name in ARM_JOINTS:
            joint = self.twin.model.joint(name)
            value = self.twin.data.qpos[self.twin.model.jnt_qposadr[joint.id]]
            self.assertGreaterEqual(value, joint.range[0] - 1e-6)
            self.assertLessEqual(value, joint.range[1] + 1e-6)

    def test_missing_camera_and_imu_hold_last_target(self) -> None:
        mapper = EndEffectorMapper(np.zeros(3), np.eye(3))
        first = SensorSample(0, True, True, True, np.array((1.0, 2.0, 3.0)),
                             np.array((1.0, 0.0, 0.0, 0.0)), np.zeros(5))
        mapper.update(first)
        moved = SensorSample(1, True, True, False, np.array((1.1, 2.0, 3.0)),
                             np.array((0.999, 0.0, 0.045, 0.0)), np.zeros(5))
        expected_position, expected_rotation = mapper.update(moved)
        missing = SensorSample(2, False, False, False, np.full(3, 99.0),
                               np.zeros(4), np.zeros(5))
        position, rotation = mapper.update(missing)
        np.testing.assert_allclose(position, expected_position)
        np.testing.assert_allclose(rotation, expected_rotation)

    def test_yaw_moves_target_on_horizontal_arc(self) -> None:
        origin = np.array((0.30, 0.10, 0.25))
        mapper = EndEffectorMapper(origin, np.eye(3))
        reference = SensorSample(0, False, True, True, np.zeros(3),
                                 np.array((1.0, 0.0, 0.0, 0.0)), np.zeros(5))
        mapper.update(reference)
        angle = np.deg2rad(30.0)
        moved = SensorSample(1, False, True, False, np.zeros(3),
                             np.array((np.cos(angle / 2.0), 0.0,
                                       np.sin(angle / 2.0), 0.0)), np.zeros(5))
        position = origin.copy()
        for _ in range(60):
            position, _ = mapper.update(moved)
        self.assertGreater(np.linalg.norm(position[:2] - origin[:2]), 0.05)
        self.assertAlmostEqual(np.linalg.norm(position[:2]),
                               np.linalg.norm(origin[:2]), places=6)
        self.assertAlmostEqual(position[2], origin[2], places=6)

    def test_mano_mount_axes_drive_robot_roll_and_pitch(self) -> None:
        angle = np.deg2rad(20.0)
        half = angle / 2.0
        expected_roll = np.array(((1.0, 0.0, 0.0),
                                  (0.0, np.cos(angle), -np.sin(angle)),
                                  (0.0, np.sin(angle), np.cos(angle))))
        expected_pitch = np.array(((np.cos(angle), 0.0, np.sin(angle)),
                                   (0.0, 1.0, 0.0),
                                   (-np.sin(angle), 0.0, np.cos(angle))))
        for quaternion, expected in (
                (np.array((np.cos(half), np.sin(half), 0.0, 0.0)), expected_roll),
                (np.array((np.cos(half), 0.0, 0.0, -np.sin(half))), expected_pitch)):
            mapper = EndEffectorMapper(np.zeros(3), np.eye(3))
            mapper.update(SensorSample(0, False, True, True, np.zeros(3),
                                       np.array((1.0, 0.0, 0.0, 0.0)), np.zeros(5)))
            rotation = np.eye(3)
            for index in range(80):
                _, rotation = mapper.update(SensorSample(index + 1, False, True, False,
                                                          np.zeros(3), quaternion,
                                                          np.zeros(5)))
            np.testing.assert_allclose(rotation, expected, atol=1e-7)


if __name__ == "__main__":
    unittest.main()


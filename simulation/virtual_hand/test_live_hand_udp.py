"""Focused tests for the first-board UDP receiver and mapper."""

import struct
import socket
import unittest

import numpy as np

from live_hand_udp import (FirstBoardMapper, MAGIC, PALM_DOWN_QUATERNION,
                           SENSOR, SENSOR_PACKET,
                           UdpSensorReceiver, VERSION, decode_packet)


def packet(sequence: int, middle: int, quaternion=(1.0, 0.0, 0.0, 0.0)) -> bytes:
    return SENSOR_PACKET.pack(
        MAGIC, VERSION, SENSOR, sequence, sequence * 10_000,
        sequence == 0, 0, 1, 0,
        0.0, 0.0, 0.0, *quaternion,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0, 0, middle, 0, 0, 0,
    )


class LiveHandUdpTest(unittest.TestCase):
    def test_packet_layout(self):
        frame = decode_packet(packet(7, 2048))
        self.assertEqual(SENSOR_PACKET.size, 84)
        self.assertEqual(frame.sequence, 7)
        self.assertEqual(int(frame.sensor.flex_raw[2]), 2048)

    def test_middle_only_and_imu_zero(self):
        mapper = FirstBoardMapper()
        first = mapper.update(decode_packet(packet(0, 0, (0.7071068, 0.0, 0.0, 0.7071068))))
        second = mapper.update(decode_packet(packet(1, 2048, (1.0, 0.0, 0.0, 0.0))))
        np.testing.assert_allclose(first.wrist_quaternion_wxyz, PALM_DOWN_QUATERNION, atol=1e-6)
        np.testing.assert_allclose(second.bend, (0, 0, 2048 / 4095, 0, 0))
        self.assertAlmostEqual(np.linalg.norm(second.wrist_quaternion_wxyz), 1.0)

    def test_mount_mapping_swaps_roll_and_pitch(self):
        mapper = FirstBoardMapper()
        mapper.update(decode_packet(packet(0, 0)))
        angle = np.deg2rad(10.0) / 2.0
        hand = mapper.update(decode_packet(packet(
            1, 0, (np.cos(angle), np.sin(angle), 0.0, 0.0))))
        expected_relative = np.array((np.cos(angle), 0.0, np.sin(angle), 0.0))
        expected = np.array((
            expected_relative[0] * PALM_DOWN_QUATERNION[0]
            - expected_relative[2] * PALM_DOWN_QUATERNION[2],
            expected_relative[0] * PALM_DOWN_QUATERNION[1]
            + expected_relative[2] * PALM_DOWN_QUATERNION[3],
            expected_relative[0] * PALM_DOWN_QUATERNION[2]
            + expected_relative[2] * PALM_DOWN_QUATERNION[0],
            expected_relative[0] * PALM_DOWN_QUATERNION[3]
            - expected_relative[2] * PALM_DOWN_QUATERNION[1],
        ))
        np.testing.assert_allclose(hand.wrist_quaternion_wxyz, expected, atol=1e-6)

    def test_all_bends_and_camera_position(self):
        payload = SENSOR_PACKET.pack(
            MAGIC, VERSION, SENSOR, 0, 0, 1, 1, 1, 0,
            0.1, 0.2, 0.3, 1.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0, 1024, 2048, 3071, 4095, 0,
        )
        hand = FirstBoardMapper().update(decode_packet(payload))
        np.testing.assert_allclose(hand.wrist_xyz, (0.1, 0.2, 0.3))
        np.testing.assert_allclose(hand.bend, np.asarray((0, 1024, 2048, 3071, 4095)) / 4095)

    def test_bad_packet_is_rejected(self):
        with self.assertRaises(ValueError):
            decode_packet(struct.pack("<I", MAGIC))

    def test_udp_receiver_keeps_latest_and_counts_gap(self):
        receiver = UdpSensorReceiver("127.0.0.1", 0)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            address = receiver.socket.getsockname()
            sender.sendto(packet(2, 1200), address)
            sender.sendto(packet(4, 1800), address)
            latest = receiver.poll()
            self.assertIsNotNone(latest)
            self.assertEqual(latest.sequence, 4)
            self.assertEqual(receiver.received, 2)
            self.assertEqual(receiver.dropped, 1)
        finally:
            sender.close()
            receiver.close()


if __name__ == "__main__":
    unittest.main()

import argparse
import csv
import json
import math
import struct
import time
from pathlib import Path

import serial


PACKET_SIZE = 46
MAGIC = b"IMUQ"


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def quaternion_to_euler_deg(q):
    w, x, y, z = q
    roll = math.degrees(math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y)))
    sin_pitch = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.degrees(math.asin(sin_pitch))
    yaw = math.degrees(math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))
    return roll, pitch, yaw


class FrameReader:
    def __init__(self, port):
        self.port = port
        self.buffer = bytearray()
        self.crc_errors = 0
        self.bytes_discarded = 0

    def read(self, deadline):
        while time.monotonic() < deadline:
            chunk = self.port.read(self.port.in_waiting or 1)
            if chunk:
                self.buffer.extend(chunk)
            marker = self.buffer.find(MAGIC)
            if marker < 0:
                if len(self.buffer) > 3:
                    self.bytes_discarded += len(self.buffer) - 3
                    del self.buffer[:-3]
                continue
            if marker > 0:
                self.bytes_discarded += marker
                del self.buffer[:marker]
            if len(self.buffer) < PACKET_SIZE:
                continue
            packet = bytes(self.buffer[:PACKET_SIZE])
            declared_length = struct.unpack_from("<H", packet, 6)[0]
            received_crc = struct.unpack_from("<H", packet, 44)[0]
            if declared_length != PACKET_SIZE or crc16_ccitt(packet[:-2]) != received_crc:
                self.crc_errors += 1
                del self.buffer[0]
                continue
            del self.buffer[:PACKET_SIZE]
            return {
                "status": packet[5],
                "sequence": struct.unpack_from("<I", packet, 8)[0],
                "timestamp_us": struct.unpack_from("<I", packet, 12)[0],
                "q": struct.unpack_from("<4f", packet, 16),
                "adc": struct.unpack_from("<5H", packet, 32),
                "temperature_raw": struct.unpack_from("<h", packet, 42)[0],
            }
        return None


def collect_for(reader, seconds):
    deadline = time.monotonic() + seconds
    frames = []
    while time.monotonic() < deadline:
        frame = reader.read(deadline)
        if frame is not None:
            frames.append(frame)
    return frames


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="COM13")
    parser.add_argument("--duration", type=float, default=300.0)
    parser.add_argument("--output", type=Path, default=Path("build/hardware_zero_drift.json"))
    parser.add_argument("--skip-calibration", action="store_true")
    args = parser.parse_args()

    serial_port = serial.Serial(args.port, 115200, timeout=0.05, write_timeout=1.0)
    reader = FrameReader(serial_port)
    serial_port.reset_input_buffer()

    precheck = collect_for(reader, 3.0)
    if len(precheck) < 200:
        raise RuntimeError(f"UART precheck received only {len(precheck)} valid frames")
    print(f"PRECHECK_OK frames={len(precheck)} status=0x{precheck[-1]['status']:02X}", flush=True)

    if args.skip_calibration:
        calibrated_frame = precheck[-1]
        if (calibrated_frame["status"] & 0x08) == 0:
            raise RuntimeError("Existing calibration requested but calibrated status is not set")
        print("USING_EXISTING_CALIBRATION", flush=True)
    else:
        serial_port.write(b"C")
        serial_port.flush()
        print("CALIBRATION_COMMAND_SENT", flush=True)

        saw_calibrating = False
        calibration_deadline = time.monotonic() + 20.0
        calibrated_frame = None
        while time.monotonic() < calibration_deadline:
            frame = reader.read(calibration_deadline)
            if frame is None:
                continue
            if frame["status"] & 0x04:
                saw_calibrating = True
            if frame["status"] & 0x08:
                calibrated_frame = frame
                break
        if calibrated_frame is None:
            raise RuntimeError(f"Calibration did not finish; saw_calibrating={saw_calibrating}")
    print(f"CALIBRATION_OK seq={calibrated_frame['sequence']} status=0x{calibrated_frame['status']:02X}", flush=True)

    start_wall = time.monotonic()
    end_wall = start_wall + args.duration
    next_report = start_wall + 30.0
    frames = []
    one_hz_rows = []
    last_sample_second = -1
    previous_yaw = None
    unwrapped_yaw = None

    while time.monotonic() < end_wall:
        frame = reader.read(end_wall)
        if frame is None:
            continue
        roll, pitch, yaw = quaternion_to_euler_deg(frame["q"])
        if previous_yaw is None:
            unwrapped_yaw = yaw
        else:
            delta = yaw - previous_yaw
            if delta > 180.0:
                delta -= 360.0
            elif delta < -180.0:
                delta += 360.0
            unwrapped_yaw += delta
        previous_yaw = yaw
        frame["euler"] = (roll, pitch, yaw)
        frame["unwrapped_yaw"] = unwrapped_yaw
        frames.append(frame)

        elapsed = time.monotonic() - start_wall
        elapsed_second = int(elapsed)
        if elapsed_second != last_sample_second:
            one_hz_rows.append((elapsed, frame["sequence"], roll, pitch, unwrapped_yaw, frame["adc"][0]))
            last_sample_second = elapsed_second
        if time.monotonic() >= next_report:
            drift = unwrapped_yaw - frames[0]["unwrapped_yaw"]
            print(f"PROGRESS elapsed={elapsed:.1f}s frames={len(frames)} yaw_drift={drift:.3f}deg", flush=True)
            next_report += 30.0

    serial_port.close()
    if len(frames) < args.duration * 80.0:
        raise RuntimeError(f"Too few valid frames: {len(frames)}")

    sequences = [frame["sequence"] for frame in frames]
    sequence_span = (sequences[-1] - sequences[0]) & 0xFFFFFFFF
    sequence_gaps = max(0, sequence_span + 1 - len(frames))
    device_elapsed_s = ((frames[-1]["timestamp_us"] - frames[0]["timestamp_us"]) & 0xFFFFFFFF) / 1_000_000.0
    frame_rate_hz = (len(frames) - 1) / device_elapsed_s
    norms = [math.sqrt(sum(value * value for value in frame["q"])) for frame in frames]
    adc_values = [frame["adc"][0] for frame in frames]
    temperatures = [frame["temperature_raw"] / 340.0 + 36.53 for frame in frames]
    start_euler = frames[0]["euler"]
    end_euler = frames[-1]["euler"]
    yaw_drift = frames[-1]["unwrapped_yaw"] - frames[0]["unwrapped_yaw"]

    summary = {
        "port": args.port,
        "duration_s": device_elapsed_s,
        "valid_frames": len(frames),
        "frame_rate_hz": frame_rate_hz,
        "sequence_gaps": sequence_gaps,
        "crc_errors": reader.crc_errors,
        "discarded_bytes": reader.bytes_discarded,
        "status_final": frames[-1]["status"],
        "quaternion_norm_max_error": max(abs(value - 1.0) for value in norms),
        "start_euler_deg": start_euler,
        "end_euler_deg": end_euler,
        "yaw_drift_deg": yaw_drift,
        "yaw_drift_deg_per_min": yaw_drift / device_elapsed_s * 60.0,
        "projected_5min_yaw_drift_deg": yaw_drift / device_elapsed_s * 300.0,
        "adc0_min": min(adc_values),
        "adc0_max": max(adc_values),
        "temperature_c_min": min(temperatures),
        "temperature_c_max": max(temperatures),
        "pass_observed_drift_within_2deg": abs(yaw_drift) <= 2.0,
        "pass_projected_5min_yaw_drift_2deg":
            abs(yaw_drift / device_elapsed_s * 300.0) <= 2.0,
        "pass_frame_rate": 95.0 <= frame_rate_hz <= 105.0,
        "pass_crc": reader.crc_errors == 0,
        "pass_sequence": sequence_gaps == 0,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["elapsed_s", "sequence", "roll_deg", "pitch_deg", "yaw_unwrapped_deg", "adc0_raw"])
        writer.writerows(one_hz_rows)

    print("RESULT " + json.dumps(summary, ensure_ascii=False), flush=True)
    print(f"SAVED {args.output} {csv_path}", flush=True)


if __name__ == "__main__":
    main()

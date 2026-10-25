"""PYNQ board capture or deterministic raw JSONL replay; outputs pose JSONL."""
import argparse
import json
from pathlib import Path
import statistics
import struct
import sys
import time

from attitude import Attitude, Sample


def signed16(value):
    value &= 0xffff
    return value-65536 if value & 0x8000 else value


def read_sample(mmio):
    if mmio.read(0) != 0x4d505531:
        raise RuntimeError("Wrong IMU register ABI or overlay")
    for _ in range(5):
        status = mmio.read(4)
        if status & 3 != 3:
            return None
        errors = mmio.read(0x30)
        sequence = mmio.read(8)
        low, high = mmio.read(0x0c), mmio.read(0x10)
        axes = [signed16(mmio.read(offset)) for offset in range(0x14, 0x2c, 4)]
        temperature = signed16(mmio.read(0x2c))
        if (mmio.read(8) == sequence and mmio.read(4) & 3 == 3
                and mmio.read(0x30) == errors):
            return Sample(sequence, (high << 32) | low,
                          tuple(axes[:3]), tuple(axes[3:]), temperature, errors)
    return None


def packet_words(pose):
    """64-byte IMU1 packet; raw data and pose share one acquisition identity."""
    def pair(a, b):
        return (a & 0xffff) | ((b & 0xffff) << 16)
    def float_word(value):
        return struct.unpack("<I", struct.pack("<f", value))[0]
    ax, ay, az = pose["raw_accel"]
    gx, gy, gz = pose["raw_gyro"]
    flags = 3 | (int(pose["accel_correction"]) << 2)
    return [0x494d5531, (1 << 16) | flags, pose["sequence"],
            pose["timestamp_us"] & 0xffffffff, pose["timestamp_us"] >> 32,
            pair(ax, ay), pair(az, pose["raw_temperature"]), pair(gx, gy), pair(gz, 0),
            float_word(pose["yaw_deg"]), float_word(pose["pitch_deg"]), float_word(pose["roll_deg"]),
            pose["i2c_errors"], pose["dropped_samples"] & 0xffffffff,
            pose["attitude_epoch"] & 0xffffffff, 0]


def publish_packet(mmio, pose):
    if mmio.read(0x80) & 1:
        return False
    for i, word in enumerate(packet_words(pose)):
        mmio.write(0x40+4*i, word)
    mmio.write(0x80, 1)
    return True


def read_clock_us(mmio):
    for _ in range(3):
        high = mmio.read(0x3c)
        low = mmio.read(0x38)
        if high == mmio.read(0x3c):
            return (high << 32) | low
    raise RuntimeError("Unstable FPGA timestamp counter")


def board_samples(mmio, timeout):
    last = None
    last_new = time.perf_counter()
    while True:
        sample = read_sample(mmio)
        if sample is not None and (sample.sequence, sample.errors) != last:
            last = (sample.sequence, sample.errors)
            last_new = time.perf_counter()
            yield sample
        else:
            if time.perf_counter()-last_new > timeout:
                raise RuntimeError("No fresh IMU sample; check wiring, address, pull-ups and I2C error count")
            time.sleep(0.0001)


def replay_samples(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield Sample(**json.loads(line))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bitstream", type=Path)
    parser.add_argument("--base", type=lambda s: int(s, 0), default=0x43c10000)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--output", type=Path, help="Pose JSONL; default stdout")
    parser.add_argument("--raw-output", type=Path, help="Raw JSONL for replay/reference comparison")
    parser.add_argument("--calibration-samples", type=int, default=1000)
    parser.add_argument("--seconds", type=float, default=0, help="Capture duration; 0 = until interrupted")
    parser.add_argument("--timeout", type=float, default=5)
    args = parser.parse_args()
    if args.timeout <= 0 or args.seconds < 0:
        parser.error("timeout must be positive; seconds must be nonnegative")
    paths = [p.resolve() for p in (args.output, args.raw_output) if p]
    if len(set(paths)) != len(paths) or (args.replay and args.replay.resolve() in paths):
        parser.error("Input, pose and raw capture paths must differ")
    if args.replay:
        samples = replay_samples(args.replay)
    else:
        from pynq import MMIO, Overlay
        if args.bitstream:
            overlay = Overlay(str(args.bitstream.resolve()))
        mmio = MMIO(args.base, 0x1000)
        samples = board_samples(mmio, args.timeout)
    estimator = Attitude(args.calibration_samples)
    output = args.output.open("w", encoding="utf-8") if args.output else sys.stdout
    raw = args.raw_output.open("w", encoding="utf-8") if args.raw_output else None
    compute_ns, processing_us, sample_age_us = [], [], []
    count = received = dropped = resets = packet_drops = 0
    first_ts = last_ts = None
    first_pose_wall = last_pose_wall = None
    last_errors = None
    start = time.perf_counter()
    print("Keep the sensor stationary for calibration; yaw is relative and will drift.", file=sys.stderr)
    try:
        for sample in samples:
            processing_start = time.perf_counter()
            received += 1
            if first_ts is None:
                first_ts = sample.timestamp_us
            last_ts = sample.timestamp_us
            if raw:
                raw.write(json.dumps(sample._asdict())+"\n")
            if last_errors is not None and sample.errors != last_errors:
                estimator = Attitude(args.calibration_samples)
                resets += 1
                print("I2C recovery: restart stationary calibration", file=sys.stderr)
            last_errors = sample.errors
            begin = time.perf_counter()
            try:
                pose = estimator.update(sample)
            except ValueError as exc:
                resets += 1
                print(str(exc), file=sys.stderr)
                estimator = Attitude(args.calibration_samples)
                pose = estimator.update(sample)
            elapsed = (time.perf_counter()-begin)*1e9
            if pose:
                pose["attitude_epoch"] = resets
                count += 1
                compute_ns.append(elapsed)
                # Bound statistics memory during unattended captures.
                if len(compute_ns) > 100000:
                    del compute_ns[:50000]
                dropped += pose["dropped_samples"]
                estimator.dropped = 0
                pose["dropped_samples"] = dropped
                if not args.replay and not publish_packet(mmio, pose):
                    packet_drops += 1
                if not args.replay:
                    sample_age_us.append(read_clock_us(mmio)-sample.timestamp_us)
                output.write(json.dumps(pose, separators=(",", ":"))+"\n")
                last_pose_wall = time.perf_counter()
                if first_pose_wall is None:
                    first_pose_wall = last_pose_wall
                processing_us.append((time.perf_counter()-processing_start)*1e6)
                if len(processing_us) > 100000:
                    del processing_us[:50000]
                    del sample_age_us[:50000]
            if args.seconds and time.perf_counter()-start >= args.seconds:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if raw:
            raw.close()
        if output is not sys.stdout:
            output.close()
        duration = time.perf_counter()-start
        sensor_duration = (last_ts-first_ts)/1e6 if first_ts is not None and last_ts > first_ts else 0
        values = sorted(compute_ns)
        processing_us.sort()
        sample_age_us.sort()
        stats = {"received": received, "poses": count, "dropped_samples": dropped,
                 "attitude_resets": resets, "wall_output_hz": count/max(duration, 1e-9),
                 "packet_backpressure_drops": packet_drops,
                 "steady_output_hz": (count-1)/(last_pose_wall-first_pose_wall) if count > 1 and last_pose_wall > first_pose_wall else 0,
                 "processing_us_p99": processing_us[min(len(processing_us)-1, int(len(processing_us)*0.99))] if processing_us else None,
                 "sample_age_us_p99": sample_age_us[min(len(sample_age_us)-1, int(len(sample_age_us)*0.99))] if sample_age_us else None,
                 "received_sensor_hz": (received-1)/sensor_duration if sensor_duration else 0,
                 "filter_us_median": statistics.median(values)/1000 if values else None,
                 "filter_us_p99": values[min(len(values)-1, int(len(values)*0.99))]/1000 if values else None}
        print(json.dumps(stats), file=sys.stderr)


if __name__ == "__main__":
    main()

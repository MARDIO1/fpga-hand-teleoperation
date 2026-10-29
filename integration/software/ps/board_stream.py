"""Receive F103 IMU/strain frames, then send HAND v2 at 100 Hz."""

import argparse
from pathlib import Path
import socket
import struct
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "modules" / "strain" / "software" / "ps"))

from strain_uart import Calibration, FingerCalibration, PreviewCalibration, StrainSerial
from vision_latest import LatestVision
from wrist_ring import RingCalibration, WristRingTracker


HAND = struct.Struct("<IHHIIBBBB13f5HH")
MAGIC = 0x444e4148
DEFAULT_CALIBRATION = ROOT / "modules" / "strain" / "data" / "finger_calibration.json"


def packet(sequence, timestamp_us, quaternion, bend, position,
           acceleration=(0.0, 0.0, 0.0), angular_velocity=(0.0, 0.0, 0.0),
           reset=False, camera_valid=False):
    return HAND.pack(MAGIC, 2, 1, sequence, timestamp_us & 0xffffffff,
                     int(reset), int(camera_valid), 1, 0,
                     position[0], position[1], position[2],
                     quaternion[0], quaternion[1], quaternion[2], quaternion[3],
                     acceleration[0], acceleration[1], acceleration[2],
                     angular_velocity[0], angular_velocity[1], angular_velocity[2],
                     bend[0], bend[1], bend[2], bend[3], bend[4], 0)


def smooth_bend(previous, current, alpha, deadband):
    if previous is None:
        return tuple(float(value) for value in current)
    return tuple(old if abs(value - old) <= deadband else old + alpha * (value - old)
                 for old, value in zip(previous, current))


def middle_finger_bend(calibration, raw):
    """Map F103 ADC slot 0 to the middle finger in HAND v2."""
    mapped = calibration.map(raw)
    return (0, 0, mapped[0], 0, 0)


def finger_bend(calibration, raw):
    if isinstance(calibration, FingerCalibration):
        return calibration.map(raw)
    return middle_finger_bend(calibration, raw)


def pose_from_frame(frame):
    if not (frame.mpu_present and frame.sample_valid and frame.calibrated):
        return None
    return {
        "timestamp_us": frame.timestamp_us,
        "quaternion_wxyz": frame.quaternion_wxyz,
        "acceleration_g": (0.0, 0.0, 0.0),
        "angular_velocity_rad_s": (0.0, 0.0, 0.0),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="/dev/ttyACM0")
    parser.add_argument("--calibrate-imu", action="store_true",
                        help="send one manual gyro-calibration command at startup")
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--strain-mode", choices=("auto", "calibrated", "preview"), default="auto")
    parser.add_argument("--preview-span", type=float, default=600.0)
    parser.add_argument("--host", default="192.168.137.1")
    parser.add_argument("--port", type=int, default=47000)
    parser.add_argument("--rate", type=float, default=100.0)
    parser.add_argument("--bend-alpha", type=float, default=0.25)
    parser.add_argument("--bend-deadband", type=float, default=16.0)
    parser.add_argument("--position", type=float, nargs=3, default=(0.0, 0.0, 0.31))
    parser.add_argument("--vision-json", type=Path,
                        help="optimized stereo latest.json; omitted disables camera input")
    parser.add_argument("--wrist-calibration", type=Path,
                        help="calibrated marker-ring geometry; required with --vision-json")
    parser.add_argument("--vision-max-age", type=float, default=0.2)
    parser.add_argument("--seconds", type=float, default=0.0,
                        help="run duration; zero means until interrupted")
    args = parser.parse_args()
    if (args.rate <= 0 or args.preview_span <= 0 or args.seconds < 0
            or not 0 < args.bend_alpha <= 1 or args.bend_deadband < 0
            or args.vision_max_age <= 0):
        parser.error("rates and spans must be positive; seconds must be nonnegative")
    if bool(args.vision_json) != bool(args.wrist_calibration):
        parser.error("--vision-json and --wrist-calibration must be used together")

    if args.strain_mode == "calibrated" or (args.strain_mode == "auto" and args.calibration.exists()):
        calibration = Calibration.load(args.calibration)
        if not isinstance(calibration, FingerCalibration) and 0 not in calibration.channels:
            parser.error("strain calibration must include F103 ADC slot 0 (middle finger)")
        strain_mode = "calibrated"
    else:
        calibration = PreviewCalibration(channel=0, span=args.preview_span)
        strain_mode = "preview"
    vision = LatestVision(args.vision_json, args.vision_max_age) if args.vision_json else None
    wrist = (WristRingTracker(RingCalibration.load(args.wrist_calibration))
             if args.wrist_calibration else None)
    camera_position = tuple(args.position)
    camera_sequence = None
    destination = (args.host, args.port)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    latest_strain = None
    sequence = 0
    sent = 0
    filtered_bend = None
    next_send = time.monotonic()
    last_report = next_send
    started = next_send

    print("strain_mode={}; IMU source=F103 IMUQ UART".format(strain_mode),
          file=sys.stderr)
    try:
        with StrainSerial(args.device) as strain:
            latest_strain = strain.read_frame(2.0)
            if args.calibrate_imu:
                strain.start_calibration()
                print("IMU calibration requested; keep the sensor stationary",
                      file=sys.stderr)
            last_strain_time = time.monotonic()
            while True:
                frames = strain.poll(0.0)
                if frames:
                    latest_strain = frames[-1]
                    last_strain_time = time.monotonic()

                pose = pose_from_frame(latest_strain) if latest_strain is not None else None

                now = time.monotonic()
                camera_valid = False
                if vision is not None:
                    camera = vision.poll(now)
                    if camera is not None and pose is not None:
                        estimate = wrist.update(camera.markers, pose["quaternion_wxyz"])
                        if estimate is not None:
                            camera_position = estimate.xyz_camera_m
                            camera_valid = True
                        camera_sequence = camera.sequence
                if now - last_strain_time > 0.5:
                    raise RuntimeError("No fresh strain frame for 0.5 s")
                if pose is not None and latest_strain is not None and now >= next_send:
                    filtered_bend = smooth_bend(filtered_bend,
                                                finger_bend(calibration, latest_strain.raw),
                                                args.bend_alpha, args.bend_deadband)
                    bend = tuple(int(round(value)) for value in filtered_bend)
                    udp.sendto(packet(sequence, pose["timestamp_us"],
                                      pose["quaternion_wxyz"], bend,
                                      camera_position, pose["acceleration_g"],
                                      pose["angular_velocity_rad_s"],
                                      reset=sequence == 0,
                                      camera_valid=camera_valid), destination)
                    sequence = (sequence + 1) & 0xffffffff
                    sent += 1
                    next_send += 1.0 / args.rate
                    if next_send < now - 1.0 / args.rate:
                        next_send = now

                if now - last_report >= 1.0:
                    print("sent={} imu_seq={} status=0x{:02x} camera_seq={} uart_rejected={}".format(
                        sent,
                        latest_strain.sequence if latest_strain else None,
                        latest_strain.status if latest_strain else 0,
                        camera_sequence,
                        strain.decoder.rejected), file=sys.stderr)
                    last_report = now
                if args.seconds and now - started >= args.seconds:
                    break
                time.sleep(0.0002)
    except KeyboardInterrupt:
        return 0
    finally:
        udp.close()


if __name__ == "__main__":
    main()

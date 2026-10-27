"""Read live board RGB565 snapshots over SSH; detect and preview on the PC.

Only reads the board's existing capture DDR. No bitstream load, register writes,
service changes or board-side image processing. Snapshots may contain tearing.
"""

import argparse
import getpass
import os
import json
from pathlib import Path
import shlex
import struct
import sys
import time

import cv2
import numpy as np

from marker_detection import (COLORS, DEFAULT_THRESHOLDS, colorize_classes,
                              detect_markers, draw_candidates, load_thresholds)
from rgb565 import load_rgb565, rgb565_bgr


MODULE_ROOT = Path(__file__).resolve().parents[2]

WINDOW = "Glove markers - PC color test"
HEADER = struct.Struct("<4sIQQI")
FRAME_BYTES = 1280 * 720 * 2


def remote_source(fps, count):
    # A read interval is not an exposure timestamp or a guaranteed complete frame.
    return f"""import mmap, os, struct, sys, time
fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
memory = mmap.mmap(fd, {FRAME_BYTES}, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0x1e000000)
output = sys.stdout.buffer
index = 0
try:
    while {count} == 0 or index < {count}:
        start = int(time.monotonic() * 1000000)
        payload = memory[:]
        end = int(time.monotonic() * 1000000)
        output.write(struct.pack('<4sIQQI', b'GLV1', index, start, end, len(payload)))
        output.write(payload)
        output.flush()
        index += 1
        time.sleep(max(0, 1 / {fps!r} - (time.monotonic() - start / 1000000)))
finally:
    memory.close()
    os.close(fd)
"""


def read_exact(stream, count):
    chunks = []
    remaining = count
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError(f"Image stream ended with {remaining} bytes missing")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def live_frames(args):
    import paramiko

    password = os.environ.get("VISION_SSH_PASSWORD")
    if password is None and not args.ssh_key:
        password = getpass.getpass("SSH password: ")
    sudo_password = os.environ.get("VISION_SUDO_PASSWORD")
    if sudo_password is None and not args.sudo_nopasswd:
        sudo_password = getpass.getpass("sudo password: ")
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    try:
        client.connect(args.host, username=args.user, password=password, key_filename=str(args.ssh_key) if args.ssh_key else None,
                       timeout=10, banner_timeout=10, auth_timeout=10)
        sudo = "sudo -n " if args.sudo_nopasswd else "sudo -S -p '' "
        command = sudo + "python3 -u -c " + shlex.quote(remote_source(args.fps, args.frames))
        stdin, stdout, stderr = client.exec_command(command, timeout=15)
        if not args.sudo_nopasswd:
            stdin.write(sudo_password + "\n")
            stdin.flush()
        stdin.channel.shutdown_write()
        while True:
            try:
                magic, sequence, start, end, length = HEADER.unpack(read_exact(stdout, HEADER.size))
                if magic != b"GLV1" or length != FRAME_BYTES:
                    raise ValueError("Invalid board image stream header")
                payload = read_exact(stdout, length)
            except EOFError:
                error = stderr.read().decode("utf-8", "replace")
                if stdout.channel.recv_exit_status() != 0:
                    raise RuntimeError(f"Board snapshot reader failed: {error}")
                return
            frame = np.frombuffer(payload, dtype="<u2").reshape(720, 1280)
            yield frame, dict(source="live_ddr_snapshot", snapshot_sequence=sequence,
                              board_read_start_us=start, board_read_end_us=end,
                              pc_receive_unix_ns=time.time_ns(), frame_consistency="unverified",
                              exposure_timestamp=None, source_frame_id=None)
    finally:
        client.close()


def process_frame(frame, thresholds):
    image = rgb565_bgr(frame)
    panels, candidates = [], {}
    start = time.perf_counter()
    for eye, eye_image in (("L", image[:, 640:]), ("R", image[:, :640])):
        points, classes, filtered = detect_markers(eye_image, thresholds[eye],
                                                  thresholds["min_area"], thresholds["max_area"])
        candidates[eye] = points
        annotated = draw_candidates(eye_image, points, eye)
        # Compact lower row shows color pixels and area-accepted components.
        masks = np.hstack((cv2.resize(colorize_classes(classes), (320, 360), interpolation=cv2.INTER_NEAREST),
                           cv2.resize(filtered, (320, 360), interpolation=cv2.INTER_NEAREST)))
        panels.append(np.vstack((annotated, masks)))
    elapsed = (time.perf_counter() - start) * 1000
    header = np.full((96, 1280, 3), 25, np.uint8)
    lines = [f"LEFT camera: {len(candidates['L'])} candidates    |    RIGHT camera: {len(candidates['R'])} candidates    |    PC detection {elapsed:.1f} ms",
             "COLOR ONLY: no roundness/stripe filter. Bottom per eye: color mask | area-accepted blobs. Labels are frame-local.",
             "S: save sample    T: save thresholds    Q / Esc: quit    Select eye (L=0,R=1), then color (R,Y,G,B=0,1,2,3)",
             "READ-ONLY SNAPSHOTS: possible tearing; no synchronized frame IDs, calibrated XYZ or exposure timestamp yet."]
    for index, line in enumerate(lines):
        cv2.putText(header, line, (10, 20 + index * 23), cv2.FONT_HERSHEY_SIMPLEX,
                    0.48, (220, 220, 220), 1, cv2.LINE_AA)
    return np.vstack((header, np.hstack(panels))), candidates, elapsed


def save_frame(output, stem, frame, preview, metadata):
    frame.astype("<u2", copy=False).tofile(str(output / f"{stem}.rgb565"))
    if not cv2.imwrite(str(output / f"{stem}_raw.png"), rgb565_bgr(frame)):
        raise OSError("Could not save raw image")
    if not cv2.imwrite(str(output / f"{stem}_preview.png"), preview):
        raise OSError("Could not save preview")
    (output / f"{stem}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def update_controls(thresholds, previous):
    selection = (cv2.getTrackbarPos("eye L0 R1", WINDOW), cv2.getTrackbarPos("color RYGB", WINDOW))
    eye, color = ("L", "R")[selection[0]], tuple(COLORS)[selection[1]]
    bounds = thresholds[eye][color]
    controls = {"H min": "h_min", "H max": "h_max", "min S": "s_min", "min V": "v_min"}
    if selection != previous:
        for control, key in controls.items():
            cv2.setTrackbarPos(control, WINDOW, bounds[key])
    else:
        for control, key in controls.items():
            bounds[key] = cv2.getTrackbarPos(control, WINDOW)
    thresholds["min_area"] = max(1, cv2.getTrackbarPos("min area", WINDOW))
    thresholds["max_area"] = max(thresholds["min_area"], cv2.getTrackbarPos("max area", WINDOW))
    return selection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="board address; required for live snapshots")
    parser.add_argument("--user", default="xilinx")
    parser.add_argument("--ssh-key", type=Path, help="SSH private key file")
    parser.add_argument("--sudo-nopasswd", action="store_true", help="use existing passwordless sudo")
    parser.add_argument("--input", type=Path, help="offline 1280x720 RGB565 or image")
    parser.add_argument("--fps", type=float, default=2, help="snapshot request rate, not camera FPS")
    parser.add_argument("--frames", type=int, default=0, help="0: until preview closed")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--output", type=Path, default=MODULE_ROOT / "data/raw/glove_preview")
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS,
                        help="per-eye, per-color HSV configuration")
    args = parser.parse_args()
    if not 0 < args.fps <= 10 or args.frames < 0:
        parser.error("Use fps > 0 and <= 10, frames >= 0")
    if args.headless and not args.input and args.frames == 0:
        parser.error("A headless live run needs --frames")
    if not args.input and not args.host:
        parser.error("Live snapshots require --host; use --input for offline processing")
    thresholds = load_thresholds(args.thresholds)
    args.output.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(1)
    stream = None
    selection = None
    try:
        if not args.headless:
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW, 1000, 780)
            for title, value, maximum in (("eye L0 R1", 0, 1), ("color RYGB", 0, 3),
                                           ("H min", 0, 179), ("H max", 179, 179),
                                           ("min S", 0, 255), ("min V", 0, 255),
                                           ("min area", thresholds["min_area"], max(1000, thresholds["min_area"])),
                                           ("max area", thresholds["max_area"], max(10000, thresholds["max_area"]))):
                cv2.createTrackbar(title, WINDOW, value, maximum, lambda _: None)
        if args.input:
            frame = load_rgb565(args.input)
            stream = iter([(frame, dict(source=str(args.input.resolve()), frame_consistency="unverified",
                                        exposure_timestamp=None, source_frame_id=None))])
        else:
            stream = live_frames(args)
        last_save = -float("inf")
        for frame, metadata in stream:
            while True:
                if not args.headless:
                    selection = update_controls(thresholds, selection)
                preview, candidates, elapsed = process_frame(frame, thresholds)
                metadata.update(thresholds=thresholds, candidates=candidates, detection_ms=elapsed,
                                identity_status="frame_local_candidates_only", calibration=None,
                                detector="per_eye_hsv_components_v2", shape_filter=False)
                now = time.monotonic()
                if args.headless or now - last_save >= 5:
                    save_frame(args.output, "latest", frame, preview, metadata)
                    last_save = now
                    if args.headless and not args.input:
                        save_frame(args.output, f"frame_{metadata['snapshot_sequence']:05d}", frame, preview, metadata)
                print(f"snapshot={metadata.get('snapshot_sequence', 'offline')} L={len(candidates['L'])} "
                      f"R={len(candidates['R'])} detection_ms={elapsed:.1f}", flush=True)
                if args.headless:
                    break
                cv2.imshow(WINDOW, preview)
                key = cv2.waitKey(50 if args.input else 1) & 255
                if key in (27, ord("q")) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    save_frame(args.output, "latest", frame, preview, metadata)
                    return
                if key == ord("s"):
                    stem = time.strftime("sample_%Y%m%d_%H%M%S") + f"_{time.time_ns() % 1000000000:09d}"
                    save_frame(args.output, stem, frame, preview, metadata)
                    print(f"Saved {args.output / stem}", flush=True)
                if key == ord("t"):
                    saved_thresholds = args.output / "thresholds.json"
                    saved_thresholds.write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
                    print(f"Saved thresholds: {saved_thresholds}", flush=True)
                if not args.input:
                    break
    finally:
        if hasattr(stream, "close"):
            stream.close()
        if not args.headless:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError) as error:
        raise SystemExit(f"Preview stopped: {error}")

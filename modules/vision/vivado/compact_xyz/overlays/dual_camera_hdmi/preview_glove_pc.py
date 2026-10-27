"""Read live board RGB565 snapshots over SSH; detect and preview on the PC.

Only reads the board's existing capture DDR. No bitstream load, register writes,
service changes or board-side image processing. Snapshots may contain tearing.
"""

import argparse
import json
from pathlib import Path
import shlex
import struct
import sys
import time

import cv2
import numpy as np

from marker_detection import (COLORS, DEFAULT_THRESHOLDS, colorize_classes,
                              draw_candidates, load_thresholds)
from glove_rle_reference import detect_rle_markers
from glove_fast_pc import ExactColorDetector, GEOMETRY_SPEC
from glove_test_metrics import timing_summary
from marker_stereo import match_markers
from calibrated_marker_stereo import CalibratedMarkerMatcher
from preview_downsample import load_rgb565, rgb565_bgr


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from board_ssh import HOST, PASSWORD, USER, paramiko

WINDOW = "Glove markers - RGB565 color detection"
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
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(args.host, username=USER, password=PASSWORD,
                       timeout=10, banner_timeout=10, auth_timeout=10)
        command = "sudo -S -p '' python3 -u -c " + shlex.quote(remote_source(args.fps, args.frames))
        stdin, stdout, stderr = client.exec_command(command, timeout=15)
        stdin.write(PASSWORD + "\n")
        stdin.flush()
        stdin.channel.shutdown_write()
        while True:
            read_started = time.perf_counter()
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
                              pc_receive_monotonic_s=time.perf_counter(),
                              receive_wait_ms=(time.perf_counter()-read_started)*1000,
                              exposure_timestamp=None, source_frame_id=None)
    finally:
        client.close()


def process_frame(frame, thresholds, rois=None, detector=None, timings=None, stereo=None, matcher=None):
    start = time.perf_counter()
    image = rgb565_bgr(frame)
    decode_ms = (time.perf_counter()-start)*1000
    detector_ms = 0.0
    panels, candidates = [], {}
    for eye, eye_image in (("L", image[:, 640:]), ("R", image[:, :640])):
        pixels = frame[:, 640:] if eye == "L" else frame[:, :640]
        roi = rois.get(eye) if rois else None
        detect = detect_rle_markers if detector is None else detector.detect
        detection_started = time.perf_counter()
        points, classes, statistics = detect(pixels, thresholds[eye],
                                            thresholds["min_area"], thresholds["max_area"], roi)
        detector_ms += (time.perf_counter()-detection_started)*1000
        candidates[eye] = points
        annotated = draw_candidates(eye_image, points, eye)
        if roi:
            x, y, w, h = roi
            cv2.rectangle(annotated, (x, y), (x+w-1, y+h-1), (255, 255, 255), 1)
        filtered = draw_candidates(np.zeros_like(eye_image), points, eye)
        statistics_text = (f"RLE runs {statistics['total_runs']} | components {statistics['components']}"
                           if detector is None else f"Exact LUT + native CCL | candidates {len(points)}")
        cv2.putText(filtered, statistics_text,
                    (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
        masks = np.hstack((cv2.resize(colorize_classes(classes), (320, 360), interpolation=cv2.INTER_NEAREST),
                           cv2.resize(filtered, (320, 360), interpolation=cv2.INTER_NEAREST)))
        panels.append(np.vstack((annotated, masks)))
    matching_started = time.perf_counter()
    if stereo is not None:
        stereo.update(match_markers(candidates['L'],candidates['R']) if matcher is None
                      else matcher.match(candidates['L'],candidates['R']))
    matching_ms = (time.perf_counter()-matching_started)*1000 if stereo is not None else 0.0
    elapsed = (time.perf_counter() - start) * 1000
    header = np.full((96, 1280, 3), 25, np.uint8)
    backend_text = "integer HSV + Python RLE" if detector is None else "exact RGB565 LUT + native CCL"
    shape_text = "loose width/height/aspect filter" if detector is not None and detector.geometry else "NO shape filter"
    lines = [f"LEFT: {len(candidates['L'])} candidates | RIGHT: {len(candidates['R'])} | detect {detector_ms:.1f} ms | PC {elapsed:.1f} ms",
             f"{backend_text}; {shape_text}. Bottom: color mask | candidate centers. IDs are frame-local.",
             "S: save  T: save thresholds  R: select glove ROI per eye  C: clear ROI  Q/Esc: quit. Sliders: eye + color.",
             ("EXPERIMENTAL XYZ: left camera optical frame, mm. Snapshot read timestamps; exposure synchronization unverified."
              if matcher is not None else
              "READ-ONLY SNAPSHOTS: possible tearing; no synchronized frame IDs, calibrated XYZ or exposure timestamp yet.")]
    for index, line in enumerate(lines):
        cv2.putText(header, line, (10, 20 + index * 23), cv2.FONT_HERSHEY_SIMPLEX,
                    0.48, (220, 220, 220), 1, cv2.LINE_AA)
    preview = np.vstack((header, np.hstack(panels)))
    if stereo is not None:
        for pair in stereo['pairs']:
            lu,lv=pair['left_uv'];ru,rv=pair['right_uv']
            first,second=(round(lu),round(lv)+96),(640+round(ru),round(rv)+96)
            color=COLORS[pair['color']]
            cv2.line(preview,first,second,color,1,cv2.LINE_AA)
            for point in (first,second):
                cv2.putText(preview,f"P{pair['pair_id']}",(point[0]+4,point[1]+15),
                            cv2.FONT_HERSHEY_SIMPLEX,.42,color,1)
        if matcher is not None:
            shown=stereo['pairs'][:16];rows=max(1,(len(shown)+1)//2)
            footer=np.full((34+rows*24,1280,3),25,np.uint8)
            cv2.putText(footer,'XYZ [mm] | LEFT optical center | X right, Y down, Z forward | experimental, frame-local IDs',
                        (8,20),cv2.FONT_HERSHEY_SIMPLEX,.48,(230,230,230),1)
            for index,pair in enumerate(shown):
                x,y,z=pair['xyz_mm'];col=index//rows;row=index%rows
                text=f"P{pair['pair_id']:02d} {pair['color']:6s} X {x:+8.1f}  Y {y:+8.1f}  Z {z:8.1f}"
                cv2.putText(footer,text,(8+col*640,44+24*row),cv2.FONT_HERSHEY_SIMPLEX,.48,COLORS[pair['color']],1)
            preview=np.vstack((preview,footer))
    elapsed = (time.perf_counter()-start)*1000
    if timings is not None:
        timings.update(decode_ms=decode_ms, detector_ms=detector_ms,
                       matching_ms=matching_ms,
                       render_ms=max(0.0, elapsed-decode_ms-detector_ms-matching_ms), processing_ms=elapsed)
    return preview, candidates, elapsed


def select_glove_rois(frame, rois):
    image = rgb565_bgr(frame)
    for eye, source in (("L", image[:, 640:]), ("R", image[:, :640])):
        title = f"Select {eye} glove: drag rectangle, Enter accept, Esc keep previous"
        box = tuple(int(value) for value in cv2.selectROI(title, source, showCrosshair=True))
        cv2.destroyWindow(title)
        if box[2] > 0 and box[3] > 0:
            rois[eye] = box


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
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--input", type=Path, help="offline 1280x720 RGB565 or image")
    parser.add_argument("--fps", type=float, default=2, help="snapshot request rate, not camera FPS")
    parser.add_argument("--frames", type=int, default=0, help="0: until preview closed")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--output", type=Path, help="new test directory; default: timestamped run")
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS,
                        help="per-eye, per-color HSV configuration")
    parser.add_argument("--backend", choices=("fast", "reference"), default="fast",
                        help="fast: exact LUT + native CCL; reference: integer HSV + Python RLE")
    parser.add_argument("--geometry", action=argparse.BooleanOptionalAction, default=None,
                        help="2:1 size/aspect checks; default on for fast backend; --no-geometry for comparison")
    parser.add_argument("--stereo", action="store_true", help="diagnostic sparse pairing; no calibrated XYZ")
    parser.add_argument("--calibration",type=Path,help="enable experimental XYZ using this stereo calibration NPZ")
    parser.add_argument("--save-every", type=int, default=0,
                        help="archive every N snapshots; 0: original headless/all or GUI/manual behavior")
    parser.add_argument("--warmup", type=int, default=2, help="exclude first N snapshots from stage percentiles")
    args = parser.parse_args()
    if args.geometry is None:
        args.geometry = args.backend == 'fast'
    if args.calibration:
        args.stereo=True
    if args.output is None:
        args.output = ROOT/'output/glove_preview'/('run_'+time.strftime('%Y%m%d_%H%M%S')+f'_{time.time_ns()%1000000000:09d}')
    if not 0 < args.fps <= 10 or args.frames < 0:
        parser.error("Use fps > 0 and <= 10, frames >= 0")
    if args.headless and not args.input and args.frames == 0:
        parser.error("A headless live run needs --frames")
    if args.geometry and args.backend != "fast":
        parser.error("--geometry requires --backend fast")
    if args.save_every < 0 or args.warmup < 0:
        parser.error("save-every and warmup must be nonnegative")
    if (args.output / 'metrics.jsonl').exists():
        parser.error("Output already has metrics.jsonl; select a new --output to preserve this test run")
    thresholds = load_thresholds(args.thresholds)
    args.output.mkdir(parents=True, exist_ok=True)
    print(f'Test output: {args.output.resolve()}', flush=True)
    cv2.setNumThreads(1)
    detector = ExactColorDetector(args.geometry) if args.backend == "fast" else None
    matcher = CalibratedMarkerMatcher(args.calibration) if args.calibration else None
    stream = None
    selection = None
    rois = {}
    records = []
    metrics_log = (args.output / 'metrics.jsonl').open('w', encoding='utf-8')
    last_snapshot = None
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
            received = metadata.get('pc_receive_monotonic_s', time.perf_counter())
            while True:
                if not args.headless:
                    selection = update_controls(thresholds, selection)
                stages = {}
                stereo = {} if args.stereo else None
                preview, candidates, elapsed = process_frame(frame, thresholds, rois, detector, stages, stereo, matcher)
                completed = time.perf_counter()
                metadata.update(thresholds=thresholds, candidates=candidates, detection_ms=elapsed,
                                identity_status="frame_local_candidates_only",
                                calibration=(dict(path=str(args.calibration.resolve()),sha256=matcher.sha256,
                                                  scope='user_accepted_PC_experiment',absolute_accuracy_certified=False)
                                             if matcher is not None else None),
                                detector=("exact_rgb565_lut_native_ccl" if detector is not None else "rgb565_integer_hsv_rle_ccl_v3"),
                                shape_filter=args.geometry, glove_rois=rois,
                                geometry_spec=GEOMETRY_SPEC if args.geometry else None,
                                stereo_matching=stereo)
                metadata['timings_ms'] = stages
                if stereo is not None:
                    stereo['timestamp_us']=metadata.get('board_read_start_us')
                    stereo['timestamp_kind']='board_snapshot_read_start_monotonic' if not args.input else 'offline_unknown'
                    for pair in stereo['pairs']:
                        pair['timestamp_us']=stereo['timestamp_us']
                        pair['timestamp_kind']=stereo['timestamp_kind']
                        pair['snapshot_sequence']=metadata.get('snapshot_sequence')
                last_snapshot = (frame, preview, json.loads(json.dumps(metadata)))
                now = time.monotonic()
                save_started = time.perf_counter()
                sequence = metadata.get('snapshot_sequence', 0)
                archive = (sequence % args.save_every == 0 if args.save_every else args.headless)
                if archive:
                    save_frame(args.output, f"frame_{sequence:05d}", frame, preview, metadata)
                if not args.headless and now - last_save >= 5:
                    save_frame(args.output, 'latest', frame, preview, metadata)
                    last_save = now
                if not args.input or not records:
                    record = dict(sequence=sequence, received_s=received, completed_s=completed,
                                  **stages, save_ms=(time.perf_counter()-save_started)*1000,
                                  receive_wait_ms=metadata.get('receive_wait_ms', 0),
                                  candidates={eye: len(points) for eye, points in candidates.items()},
                                  archived_stem=f'frame_{sequence:05d}' if archive else None,
                                  thresholds=json.loads(json.dumps(thresholds)), geometry=args.geometry,
                                  glove_rois=dict(rois), matched_pairs=len(stereo['pairs']) if stereo else None,
                                  xyz_points=stereo['pairs'] if matcher is not None else None)
                    records.append(record)
                    metrics_log.write(json.dumps(record, ensure_ascii=False)+'\n')
                    metrics_log.flush()
                    if len(records) % 20 == 0:
                        summary = timing_summary(records, args.warmup)
                        (args.output/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
                if len(records) >= 2 and records[-1]['received_s'] > records[0]['received_s']:
                    rx_hz = (len(records)-1)/(records[-1]['received_s']-records[0]['received_s'])
                    cv2.rectangle(preview, (780,0), (1279,26), (25,25,25), -1)
                    cv2.putText(preview, f'RX {rx_hz:.1f} Hz | detect {stages["detector_ms"]:.1f} ms',
                                (790,20), cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
                print(f"snapshot={metadata.get('snapshot_sequence', 'offline')} L={len(candidates['L'])} "
                      f"R={len(candidates['R'])} pairs={len(stereo['pairs']) if stereo else '-'} "
                      f"detector_ms={stages['detector_ms']:.1f} processing_ms={elapsed:.1f}", flush=True)
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
                if key == ord("r"):
                    select_glove_rois(frame, rois)
                if key == ord("c"):
                    rois.clear()
                if not args.input:
                    break
    finally:
        if hasattr(stream, "close"):
            stream.close()
        if not args.headless:
            cv2.destroyAllWindows()
        if last_snapshot is not None:
            save_frame(args.output, 'latest', *last_snapshot)
        metrics_log.close()
        summary = timing_summary(records, args.warmup)
        summary.update(backend=args.backend, geometry=args.geometry, requested_snapshot_hz=args.fps,
                       geometry_spec=GEOMETRY_SPEC if args.geometry else None, sparse_stereo=args.stereo,
                       calibrated_xyz=bool(matcher),
                       offline_input=bool(args.input))
        (args.output/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, paramiko.SSHException) as error:
        raise SystemExit(f"Preview stopped: {error}")

"""Display live middle-finger strain and dorsal-IMU data with the MANO hand."""

from __future__ import annotations

import argparse
from pathlib import Path
import time

from live_hand_udp import FirstBoardMapper, PORT, UdpSensorReceiver
from mano_controller import ManoController


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--seconds", type=float, default=0.0)
    parser.add_argument("--output", type=Path, help="save the final received pose as PNG")
    args = parser.parse_args()
    if args.seconds < 0:
        parser.error("seconds must be nonnegative")

    receiver = UdpSensorReceiver(args.bind, args.port)
    mapper = FirstBoardMapper()
    controller = ManoController()
    started = time.monotonic()
    latest = None
    print(f"listening udp://{args.bind}:{args.port}")
    try:
        if args.headless:
            while not args.seconds or time.monotonic() - started < args.seconds:
                packet = receiver.poll()
                if packet is not None:
                    latest = mapper.update(packet)
                if latest is not None:
                    controller.apply(latest)
                time.sleep(1.0 / 60.0)
        else:
            import mujoco.viewer
            with mujoco.viewer.launch_passive(controller.model, controller.data) as viewer:
                while viewer.is_running():
                    packet = receiver.poll()
                    if packet is not None:
                        latest = mapper.update(packet)
                    if latest is not None:
                        controller.apply(latest)
                    viewer.sync()
                    time.sleep(1.0 / 60.0)
    finally:
        if args.output is not None and latest is not None:
            import cv2
            args.output.parent.mkdir(parents=True, exist_ok=True)
            image = cv2.cvtColor(controller.render(), cv2.COLOR_RGB2BGR)
            if not cv2.imwrite(str(args.output), image):
                raise RuntimeError(f"cannot write {args.output}")
        receiver.close()
        controller.close()
    print(f"received={receiver.received} dropped={receiver.dropped} rejected={receiver.rejected}")
    if args.output is not None and latest is not None:
        print(f"preview={args.output.resolve()}")
    if args.headless and receiver.received == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

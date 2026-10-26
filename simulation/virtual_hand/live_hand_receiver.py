"""Display live middle-finger strain and dorsal-IMU data with the MANO hand."""

from __future__ import annotations

import argparse
import time

from live_hand_udp import FirstBoardMapper, PORT, UdpSensorReceiver
from mano_controller import ManoController


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--middle-open", type=float)
    parser.add_argument("--middle-fist", type=float)
    parser.add_argument("--middle-span", type=float, default=600.0,
                        help="signed raw change from open to fist when --middle-fist is omitted")
    args = parser.parse_args()

    import mujoco.viewer

    receiver = UdpSensorReceiver(args.bind, args.port)
    mapper = FirstBoardMapper(args.middle_open, args.middle_fist, args.middle_span)
    controller = ManoController()
    last_report = time.monotonic()
    latest = None
    print(f"listening udp://{args.bind}:{args.port}")
    try:
        with mujoco.viewer.launch_passive(controller.model, controller.data) as viewer:
            while viewer.is_running():
                packet = receiver.poll()
                if packet is not None:
                    latest = mapper.update(packet)
                if latest is not None:
                    controller.apply(latest)
                viewer.sync()

                now = time.monotonic()
                if now - last_report >= 1.0:
                    print(f"received={receiver.received} dropped={receiver.dropped} "
                          f"rejected={receiver.rejected} middle_open={mapper.middle_open}")
                    last_report = now
                time.sleep(1.0 / 60.0)
    finally:
        receiver.close()
        controller.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

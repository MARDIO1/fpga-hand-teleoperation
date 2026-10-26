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
    args = parser.parse_args()

    import mujoco.viewer

    receiver = UdpSensorReceiver(args.bind, args.port)
    mapper = FirstBoardMapper()
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
                          f"rejected={receiver.rejected}")
                    last_report = now
                time.sleep(1.0 / 60.0)
    finally:
        receiver.close()
        controller.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

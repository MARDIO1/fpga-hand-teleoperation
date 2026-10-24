"""Display C++ results with the existing hand model, poses and renderer.

Run after the C++ testbench. The replay includes one-finger and full marker loss.
No reconstruction algorithm is duplicated here.
"""
import argparse
import time
from pathlib import Path

import cv2
import mujoco
import numpy as np

from hand_simulation import HandSimulation, HandState, animated_pose, render_frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2] / "modules/fusion"
    parser.add_argument("--input", type=Path, default=root / "reconstruction.txt")
    parser.add_argument("--output", type=Path, help="save a video instead of opening a window")
    args = parser.parse_args()
    rows = np.loadtxt(args.input)
    simulation = HandSimulation()
    renderer = mujoco.Renderer(simulation.model, height=540, width=640)
    video = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), 60, (1280, 540)) if args.output else None
    labels = ("TRACKING", "PREDICT", "DAMP", "HOLD", "REACQUIRE")
    try:
        for row in rows:
            started = time.perf_counter()
            truth = animated_pose(row[0] * 1e-6)
            estimate = HandState(row[3:6], row[6:15].reshape(3, 3), row[15:20], row[20:25], np.zeros(5))
            simulation.apply_observation(truth)
            simulation.apply_reconstruction(estimate)
            mujoco.mj_forward(simulation.model, simulation.data)
            metrics = simulation.evaluate(truth, estimate)
            frame = render_frame(simulation, renderer, truth, estimate, metrics)
            cv2.putText(frame, f"C++ {labels[int(row[1])]} | measured mask {int(row[2]):02x}", (24, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (245, 245, 245), 1, cv2.LINE_AA)
            if video:
                video.write(frame)
            else:
                cv2.imshow("C++ hand reconstruction", frame)
                delay = max(1, round((1 / 60 - time.perf_counter() + started) * 1000))
                if cv2.waitKey(delay) & 0xFF in (27, ord("q")):
                    break
    finally:
        renderer.close()
        if video:
            video.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

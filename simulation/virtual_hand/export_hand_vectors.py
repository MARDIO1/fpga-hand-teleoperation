"""Export existing MuJoCo packets and reconstruction targets for the HLS testbench.

Run with uv from simulation/virtual_hand. Each row contains reset, timestamp, validity, XYZ,
five flex values, then position/rotation/bend/spread from the existing solver.
"""
from pathlib import Path

import mujoco
import numpy as np

from hand_simulation import FINGERS, PALM_MARKERS, HandSimulation, animated_pose, static_pose


def main() -> None:
    simulation = HandSimulation()
    rows = []
    poses = ("open", "fist", "spread", "point", "thumb", None)
    for pose in poses:
        simulation.last_spread.fill(0)
        for frame in range(360):
            truth = static_pose(pose) if pose else animated_pose(frame / 60)
            simulation.apply_observation(truth)
            mujoco.mj_forward(simulation.model, simulation.data)
            packet = simulation.read_sensor_packet(round(frame * 1_000_000 / 60))
            expected = simulation.reconstruct(packet)
            markers = np.stack([packet.markers[name] for name in (*PALM_MARKERS, *FINGERS)])
            values = [int(frame == 0), packet.timestamp_us, 511]
            values.extend(markers.ravel())
            values.extend(packet.flex_raw)
            values.extend(expected.palm_position)
            values.extend(expected.palm_rotation.ravel())
            values.extend(expected.bend)
            values.extend(expected.spread)
            rows.append(values)
    path = (
        Path(__file__).resolve().parents[2]
        / "modules/fusion/tests/data/packets.txt"
    )
    path.parent.mkdir(exist_ok=True)
    np.savetxt(path, rows, fmt="%.10g")
    print(f"Exported {len(rows)} packets: {path}")


if __name__ == "__main__":
    main()

"""Compare Mahony arithmetic against AHRS 0.4.0 and report local filter cost.

Run with ahrs and numpy installed; output is a JSON validation report.
"""
import json
import math
from pathlib import Path
import statistics
import sys
import time

import numpy as np
from ahrs.filters import Mahony

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"software/ps"))
from attitude import Attitude, Sample


def distance(q, r):
    dot = min(1.0, abs(sum(a*b for a, b in zip(q, r))))
    return math.degrees(2*math.acos(dot))


def main():
    estimator = Attitude(20)
    for i in range(20):
        estimator.update(Sample(i, i*2000, (0, 0, 8192), (0, 0, 0)))
    reference = Mahony(k_P=2.0, k_I=0.05)
    qr = np.array(estimator.q)
    raw_gyro = (1500, 750, 2250)
    omega = np.radians(np.array(raw_gyro)/65.5)
    rate = float(np.linalg.norm(omega))
    axis = omega/rate
    deviations, truth_errors, costs = [], [], []
    for n in range(1, 10001):
        t = n*0.002
        truth = [math.cos(rate*t/2), *(axis*math.sin(rate*t/2))]
        w, x, y, z = truth
        gravity = (2*(x*z-w*y), 2*(w*x+y*z), 1-2*(x*x+y*y))
        raw_accel = tuple(round(v*8192) for v in gravity)
        sample = Sample(n+19, (n+19)*2000, raw_accel, raw_gyro)
        start = time.perf_counter_ns()
        pose = estimator.update(sample)
        costs.append((time.perf_counter_ns()-start)/1000)
        # Match the documented preprocessing to isolate the Mahony equations.
        qr = reference.updateIMU(qr, gyr=omega, acc=np.array(estimator.accel_lp), dt=0.002)
        deviations.append(distance(pose["quaternion_wxyz"], qr))
        truth_errors.append(distance(pose["quaternion_wxyz"], truth))
    costs.sort()
    report = {"samples": len(costs), "reference": "ahrs==0.4.0 Mahony",
              "reference_max_error_deg": max(deviations),
              "analytic_trajectory_max_error_deg": max(truth_errors),
              "local_filter_us_median": statistics.median(costs),
              "local_filter_us_p99": costs[int(len(costs)*0.99)],
              "hardware_performance_claimed": False}
    print(json.dumps(report, indent=2))
    assert max(deviations) < 0.001, report
    assert max(truth_errors) < 2.0, report


if __name__ == "__main__":
    main()

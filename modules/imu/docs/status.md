# IMU prototype status — 2026-10-25

The user accepted the prototype as provisionally usable and requested migration
under the repository's module rules. Continuous low-latency transport remains
unfinished in the external experimental workspace and is deliberately excluded.

## Observed on hardware

- ACZ7015, MPU6050 at 3.3 V, SCL=H5 and SDA=H6, address 0x68.
- WHO_AM_I=0x68; original six-axis samples and temperature update as the module moves.
- A sleep-retention startup issue was diagnosed by register readback and fixed
  through a repeated wake write followed by PWR_MGMT_1 verification.
- The PL microsecond counter was checked against ARM elapsed time, ratio
  approximately 0.9999825. The PYNQ clock-frequency property alone was not used as
  proof of physical timer speed.
- A 60-second ARM/PC test received 29,526 raw frames and produced 28,527 pose
  frames, including the initial 1000-sample calibration interval. Steady output
  was 491.800 Hz; raw-frame reception 492.089 Hz. I2C errors and attitude resets
  were zero. There were 489 detected missed successful acquisition frames.
- Filter median/p99: 390.723/580.323 us. Processing p99: 1973.511 us. Sample age
  p99 at writeback: 3856 us, excluding sensor internal filtering and PC transport.
  This run wrote both raw and pose logs; it is not a zero-loss 500 Hz guarantee.
- The PC displayed live raw values, time, yaw/pitch/roll and angle curves while
  the user moved the module. These observations do not establish angle accuracy.

The 60-second result came from the external diagnostic overlay after a manual
wake command, with the same acquisition/packet path. The exported final hardware
adds automatic repeat-wake/readback. Its separate post-build probe and provenance
are recorded in the release manifest; do not conflate these validation stages.

The final exported bitstream was then loaded on the board without a manual wake
command: status=3, I2C errors=0, 2853 samples observed in the six-second probe,
with hardware acquisition measured at 499.947 Hz. This verifies automatic startup
and raw acquisition; the earlier 491.800 Hz result describes ARM pose throughput.

## Known limits

1. The viewer reads a buffered JSONL file with SSH tail polling and refreshes at
   10 Hz. Batching can delay the display. Closing it stops PC reception only.
2. Initialization requires a continuous stationary calibration interval. Motion
   can extend it. I2C recovery, timestamp discontinuity or a >20 ms capture gap
   restarts calibration, potentially producing several seconds without valid
   attitude. Raw capture can continue during that interval.
3. A preliminary 60-second test stopped at its explicit time limit; restarting
   introduced another calibration interval. Such test interruptions are not
   hardware communication failures.
4. Successful samples use latest-value registers rather than a history FIFO.
   Sequence gaps measure ARM missed acquisitions; they cannot reveal sensor
   samples overwritten before I2C reads.
5. MPU6050 has no magnetometer: yaw is relative and drifts. Euler pitch has the
   usual +/-90-degree singularity; JSON also retains a quaternion.
6. The timestamp marks PL burst-read launch, not sensor conversion, UTC or camera
   exposure. No shared sensor/camera timebase is validated.
7. The standalone design drains AXIS with TREADY=1; final integration must connect
   an actual receiver. ARM estimation/writeback is required for complete packets.
8. No simultaneous stereo/IMU test, absolute attitude calibration, long-term
   thermal test or direct continuous transport acceptance is claimed.

The next latency change should independently validate continuous transport,
bounded output buffering and how short scheduling gaps affect calibration. It
must not be represented as already included in this migrated release.

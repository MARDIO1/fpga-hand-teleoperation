"""Dependency-free MPU6050 calibration and Mahony IMU filter (sensor axes)."""
from typing import NamedTuple
import math


class Sample(NamedTuple):
    sequence: int
    timestamp_us: int
    accel: tuple  # raw +/-4 g: 8192 LSB/g
    gyro: tuple   # raw +/-500 deg/s: 65.5 LSB/(deg/s)
    temperature: int = 0
    errors: int = 0


def euler(q):
    w, x, y, z = q
    return (
        math.degrees(math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))),
        math.degrees(math.asin(max(-1.0, min(1.0, 2*(w*y-z*x))))),
        math.degrees(math.atan2(2*(w*x+y*z), 1-2*(x*x+y*y))),
    )


def tilt_quaternion(a):
    ax, ay, az = a
    roll = math.atan2(ay, az)
    pitch = math.atan2(-ax, math.hypot(ay, az))
    cr, sr = math.cos(roll/2), math.sin(roll/2)
    cp, sp = math.cos(pitch/2), math.sin(pitch/2)
    return (cr*cp, sr*cp, cr*sp, -sr*sp)


class Attitude:
    def __init__(self, calibration_samples=1000, kp=2.0, ki=0.05):
        if calibration_samples < 2 or not all(math.isfinite(v) and v >= 0 for v in (kp, ki)):
            raise ValueError("Need >=2 stationary samples and finite, nonnegative gains")
        self.calibration_samples = calibration_samples
        self.kp, self.ki = kp, ki
        self.bias = None
        self._reset_calibration()
        self.q = None
        self.integral = [0.0]*3
        self.accel_lp = None
        self.last_timestamp = None
        self.last_sequence = None
        self.dropped = 0

    def _reset_calibration(self):
        self.calibration_count = 0
        self.mean_accel = [0.0]*3
        self.mean_gyro = [0.0]*3
        self.m2_accel = [0.0]*3
        self.m2_gyro = [0.0]*3

    def update(self, sample):
        if len(sample.accel) != 3 or len(sample.gyro) != 3:
            raise ValueError("Expected three sensor axes")
        if not all(isinstance(v, int) and -32768 <= v <= 32767
                   for v in (*sample.accel, *sample.gyro)):
            raise ValueError("Sensor axes must be signed 16-bit integers")
        if not 0 <= sample.sequence <= 0xffffffff or not 0 <= sample.timestamp_us < 2**64:
            raise ValueError("Invalid sequence or timestamp")
        dt = None
        if self.last_timestamp is not None:
            delta = sample.timestamp_us-self.last_timestamp
            seq_delta = (sample.sequence-self.last_sequence) & 0xffffffff
            if delta <= 0 or delta > 20000 or seq_delta == 0 or seq_delta > 10:
                raise ValueError("Discontinuous IMU stream; restart stationary calibration")
            dt = delta/1e6
            self.dropped += seq_delta-1
            if self.bias is None and seq_delta != 1:
                self._reset_calibration()
        self.last_timestamp = sample.timestamp_us
        self.last_sequence = sample.sequence
        a = [v/8192.0 for v in sample.accel]
        g = [math.radians(v/65.5) for v in sample.gyro]
        norm = math.sqrt(sum(v*v for v in a))
        if self.bias is None:
            # Calibration assumes a physically stationary hand; do not calibrate in motion.
            if not 0.9 <= norm <= 1.1 or max(abs(v) for v in g) > math.radians(5):
                self._reset_calibration()
                return None
            # Welford updates avoid an O(N) latency spike at calibration completion.
            self.calibration_count += 1
            n = self.calibration_count
            for i in range(3):
                da, dg = a[i]-self.mean_accel[i], g[i]-self.mean_gyro[i]
                self.mean_accel[i] += da/n
                self.mean_gyro[i] += dg/n
                self.m2_accel[i] += da*(a[i]-self.mean_accel[i])
                self.m2_gyro[i] += dg*(g[i]-self.mean_gyro[i])
            if n < self.calibration_samples:
                return None
            if any(self.m2_gyro[i]/n > math.radians(0.5)**2
                   or self.m2_accel[i]/n > 0.02**2
                   for i in range(3)):
                self._reset_calibration()
                return None
            self.bias = self.mean_gyro[:]
            self.q = tilt_quaternion(self.mean_accel)
            self.accel_lp = self.mean_accel[:]
            self._reset_calibration()
        else:
            alpha = 1-math.exp(-2*math.pi*30*dt)
            self.accel_lp = [old+alpha*(new-old) for old, new in zip(self.accel_lp, a)]
            omega = [v-b for v, b in zip(g, self.bias)]
            w, x, y, z = self.q
            # Gravity predicted in sensor coordinates, q rotates sensor -> world.
            gravity = [2*(x*z-w*y), 2*(w*x+y*z), 1-2*(x*x+y*y)]
            lp_norm = math.sqrt(sum(v*v for v in self.accel_lp))
            if 0.85 <= norm <= 1.15 and lp_norm > 1e-9:
                ax, ay, az = [v/lp_norm for v in self.accel_lp]
                vx, vy, vz = gravity
                correction = [ay*vz-az*vy, az*vx-ax*vz, ax*vy-ay*vx]
                for i in range(3):
                    self.integral[i] = max(-0.1, min(0.1, self.integral[i]+self.ki*correction[i]*dt))
                    omega[i] += self.kp*correction[i]
            omega = [v+b for v, b in zip(omega, self.integral)]
            gx, gy, gz = omega
            q = [w+(-x*gx-y*gy-z*gz)*dt/2,
                 x+(w*gx+y*gz-z*gy)*dt/2,
                 y+(w*gy-x*gz+z*gx)*dt/2,
                 z+(w*gz+x*gy-y*gx)*dt/2]
            q_norm = math.sqrt(sum(v*v for v in q))
            self.q = tuple(v/q_norm for v in q)
        yaw, pitch, roll = euler(self.q)
        return {
            "schema": "mpu6050.attitude.v1", "sequence": sample.sequence,
            "timestamp_us": sample.timestamp_us, "yaw_deg": yaw,
            "pitch_deg": pitch, "roll_deg": roll, "quaternion_wxyz": self.q,
            "valid": True, "yaw_reference": "relative_drifting",
            "accel_correction": 0.85 <= norm <= 1.15,
            "dropped_samples": self.dropped, "i2c_errors": sample.errors,
            "raw_accel": sample.accel, "raw_gyro": sample.gyro,
            "raw_temperature": sample.temperature,
        }

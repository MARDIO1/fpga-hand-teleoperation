#include "imu_filter.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define PI_F 3.14159265358979323846f
#define DEG_TO_RAD (PI_F / 180.0f)

static uint32_t random_state = 0x13579bdfU;

static float deterministic_noise(float amplitude)
{
    float sum = 0.0f;
    uint32_t i;
    for (i = 0U; i < 6U; ++i)
    {
        random_state = random_state * 1664525U + 1013904223U;
        sum += (float)((random_state >> 8) & 0xffffU) / 65535.0f;
    }
    return (sum - 3.0f) * amplitude;
}

static void integrate_truth(float q[4], const float omega[3], float dt_s)
{
    const float qw = q[0];
    const float qx = q[1];
    const float qy = q[2];
    const float qz = q[3];
    const float half_dt = 0.5f * dt_s;

    q[0] += (-qx * omega[0] - qy * omega[1] - qz * omega[2]) * half_dt;
    q[1] += ( qw * omega[0] + qy * omega[2] - qz * omega[1]) * half_dt;
    q[2] += ( qw * omega[1] - qx * omega[2] + qz * omega[0]) * half_dt;
    q[3] += ( qw * omega[2] + qx * omega[1] - qy * omega[0]) * half_dt;
    imu_quaternion_normalize(q);
}

static void gravity_body(const float q[4], float gravity[3])
{
    gravity[0] = 9.80665f * 2.0f * (q[1] * q[3] - q[0] * q[2]);
    gravity[1] = 9.80665f * 2.0f * (q[0] * q[1] + q[2] * q[3]);
    gravity[2] = 9.80665f * (q[0] * q[0] - q[1] * q[1] -
                            q[2] * q[2] + q[3] * q[3]);
}

static int check(int condition, const char *message)
{
    if (!condition)
    {
        fprintf(stderr, "FAIL: %s\n", message);
        return 0;
    }
    return 1;
}

static int test_static_yaw_drift(void)
{
    const float dt = 0.002f;
    const uint32_t steps = (uint32_t)(300.0f / dt);
    const float calibrated_bias[3] = {0.0f, 0.0f, 0.0f};
    const float residual_bias[3] = {0.02f * DEG_TO_RAD,
                                    -0.015f * DEG_TO_RAD,
                                    0.006f * DEG_TO_RAD};
    ImuQuaternionEkf ekf;
    float accel[3];
    float gyro[3];
    float euler[3];
    uint32_t i;

    imu_ekf_init(&ekf, calibrated_bias);
    random_state = 0x10203040U;

    for (i = 0U; i < steps; ++i)
    {
        gyro[0] = residual_bias[0] + deterministic_noise(0.0010f);
        gyro[1] = residual_bias[1] + deterministic_noise(0.0010f);
        gyro[2] = residual_bias[2] + deterministic_noise(0.0010f);
        accel[0] = deterministic_noise(0.015f);
        accel[1] = deterministic_noise(0.015f);
        accel[2] = 9.80665f + deterministic_noise(0.015f);
        (void)imu_ekf_update(&ekf, gyro, accel, dt);
    }

    imu_quaternion_to_euler_deg(ekf.q, euler);
    printf("synthetic_static_5min: roll=% .3f pitch=% .3f yaw=% .3f deg\n",
           euler[0], euler[1], euler[2]);

    return check(fabsf(euler[2]) <= 2.0f,
                 "EKF yaw drift exceeded 2 degrees in five minutes") &&
           check(fabsf(euler[0]) <= 0.5f && fabsf(euler[1]) <= 0.5f,
                 "EKF roll/pitch failed to reject static gyro bias");
}

static int test_fast_full_turn(void)
{
    const float dt = 0.002f;
    const uint32_t steps = 250U; /* 720 deg/s for 0.5 s = 360 degrees. */
    const float calibrated_bias[3] = {0.0f, 0.0f, 0.0f};
    const float true_gyro[3] = {0.0f, 0.0f, 720.0f * DEG_TO_RAD};
    const float accel[3] = {0.0f, 0.0f, 9.80665f};
    float measured_gyro[3] = {0.0f, 0.0f, true_gyro[2] * 1.003f};
    float truth[4] = {1.0f, 0.0f, 0.0f, 0.0f};
    ImuQuaternionEkf ekf;
    float error;
    uint32_t i;

    imu_ekf_init(&ekf, calibrated_bias);
    for (i = 0U; i < steps; ++i)
    {
        integrate_truth(truth, true_gyro, dt);
        (void)imu_ekf_update(&ekf, measured_gyro, accel, dt);
    }

    error = imu_quaternion_error_deg(ekf.q, truth);
    printf("synthetic_fast_turn: error=% .3f deg\n", error);
    return check(error <= 2.0f,
                 "EKF fast 360-degree turn error exceeded 2 degrees");
}

static int test_dynamic_disturbance_comparison(void)
{
    const float dt = 0.002f;
    const uint32_t steps = (uint32_t)(30.0f / dt);
    const float calibration[3] = {0.0f, 0.0f, 0.003f};
    const float sensor_bias[3] = {0.020f, -0.015f, 0.003f};
    ImuComplementaryFilter simple;
    ImuQuaternionEkf ekf;
    float truth[4] = {1.0f, 0.0f, 0.0f, 0.0f};
    double simple_error_squared = 0.0;
    double ekf_error_squared = 0.0;
    uint32_t measured_samples = 0U;
    uint32_t i;

    imu_complementary_init(&simple, calibration, 2.0f);
    imu_ekf_init(&ekf, calibration);
    random_state = 0x2468ace0U;

    for (i = 0U; i < steps; ++i)
    {
        const float time_s = (float)i * dt;
        const float burst_phase = fmodf(time_s, 3.0f);
        float true_gyro[3];
        float measured_gyro[3];
        float accel[3];
        float simple_error;
        float ekf_error;

        true_gyro[0] = 0.55f * sinf(0.75f * time_s);
        true_gyro[1] = 0.40f * cosf(0.53f * time_s);
        true_gyro[2] = 0.35f * sinf(0.31f * time_s);
        integrate_truth(truth, true_gyro, dt);
        gravity_body(truth, accel);

        if (burst_phase > 1.0f && burst_phase < 1.45f)
        {
            accel[0] += 5.0f;
            accel[1] -= 2.0f;
        }

        accel[0] += deterministic_noise(0.025f);
        accel[1] += deterministic_noise(0.025f);
        accel[2] += deterministic_noise(0.025f);
        measured_gyro[0] = true_gyro[0] + sensor_bias[0] + deterministic_noise(0.0015f);
        measured_gyro[1] = true_gyro[1] + sensor_bias[1] + deterministic_noise(0.0015f);
        measured_gyro[2] = true_gyro[2] + sensor_bias[2] + deterministic_noise(0.0015f);

        imu_complementary_update(&simple, measured_gyro, accel, dt);
        (void)imu_ekf_update(&ekf, measured_gyro, accel, dt);

        if (time_s >= 2.0f)
        {
            simple_error = imu_quaternion_error_deg(simple.q, truth);
            ekf_error = imu_quaternion_error_deg(ekf.q, truth);
            simple_error_squared += (double)simple_error * simple_error;
            ekf_error_squared += (double)ekf_error * ekf_error;
            measured_samples++;
        }
    }

    {
        const float simple_rmse = (float)sqrt(simple_error_squared / measured_samples);
        const float ekf_rmse = (float)sqrt(ekf_error_squared / measured_samples);
        printf("synthetic_dynamic_disturbance: simple_rmse=% .3f ekf_rmse=% .3f deg "
               "accepted=%lu rejected=%lu\n",
               simple_rmse, ekf_rmse,
               (unsigned long)ekf.accel_update_count,
               (unsigned long)ekf.accel_reject_count);
        return check(ekf_rmse < simple_rmse * 0.60f,
                     "EKF did not improve dynamic RMSE by at least 40 percent");
    }
}

int main(void)
{
    int passed = 1;
    passed &= test_static_yaw_drift();
    passed &= test_fast_full_turn();
    passed &= test_dynamic_disturbance_comparison();

    if (!passed)
    {
        return EXIT_FAILURE;
    }

    puts("PASS: synthetic IMU filter acceptance and comparison tests");
    return EXIT_SUCCESS;
}

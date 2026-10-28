#ifndef IMU_FILTER_H
#define IMU_FILTER_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Quaternion convention: q = [w, x, y, z], body frame to world frame. */
typedef struct
{
    float q[4];
    float gyro_bias[3];
    float accel_gain;
} ImuComplementaryFilter;

/*
 * Error-state quaternion EKF.
 * Nominal state is quaternion + calibrated gyro bias.  The 6x6 covariance
 * tracks small attitude error and gyro-bias error.  The Z bias is deliberately
 * kept at its stored calibration value because gravity cannot observe yaw.
 */
typedef struct
{
    float q[4];
    float gyro_bias[3];
    float covariance[6][6];
    float gyro_noise;
    float bias_noise;
    float accel_noise;
    float gravity;
    float accel_gate;
    uint32_t predict_count;
    uint32_t accel_update_count;
    uint32_t accel_reject_count;
} ImuQuaternionEkf;

void imu_complementary_init(ImuComplementaryFilter *filter,
                            const float gyro_bias[3],
                            float accel_gain);

void imu_complementary_update(ImuComplementaryFilter *filter,
                              const float gyro_rad_s[3],
                              const float accel_m_s2[3],
                              float dt_s);

void imu_ekf_init(ImuQuaternionEkf *filter, const float gyro_bias[3]);

/* Returns 1 when the accelerometer update was accepted, otherwise 0. */
uint8_t imu_ekf_update(ImuQuaternionEkf *filter,
                       const float gyro_rad_s[3],
                       const float accel_m_s2[3],
                       float dt_s);

void imu_quaternion_normalize(float q[4]);
void imu_quaternion_to_euler_deg(const float q[4], float euler_deg[3]);
float imu_quaternion_error_deg(const float estimate[4], const float reference[4]);

#ifdef __cplusplus
}
#endif

#endif

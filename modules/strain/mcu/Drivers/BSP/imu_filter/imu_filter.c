#include "imu_filter.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

#define IMU_PI_F 3.14159265358979323846f
#define IMU_RAD_TO_DEG (180.0f / IMU_PI_F)
#define IMU_EPSILON 1.0e-9f

static float clampf(float value, float minimum, float maximum)
{
    if (value < minimum)
    {
        return minimum;
    }
    if (value > maximum)
    {
        return maximum;
    }
    return value;
}

void imu_quaternion_normalize(float q[4])
{
    float norm = sqrtf(q[0] * q[0] + q[1] * q[1] +
                       q[2] * q[2] + q[3] * q[3]);

    if (norm < IMU_EPSILON)
    {
        q[0] = 1.0f;
        q[1] = 0.0f;
        q[2] = 0.0f;
        q[3] = 0.0f;
        return;
    }

    q[0] /= norm;
    q[1] /= norm;
    q[2] /= norm;
    q[3] /= norm;
}

static void quaternion_integrate(float q[4], const float omega[3], float dt_s)
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

static void quaternion_apply_body_error(float q[4], const float delta[3])
{
    const float qw = q[0];
    const float qx = q[1];
    const float qy = q[2];
    const float qz = q[3];
    const float dx = 0.5f * delta[0];
    const float dy = 0.5f * delta[1];
    const float dz = 0.5f * delta[2];

    q[0] = qw - qx * dx - qy * dy - qz * dz;
    q[1] = qx + qw * dx + qy * dz - qz * dy;
    q[2] = qy + qw * dy - qx * dz + qz * dx;
    q[3] = qz + qw * dz + qx * dy - qy * dx;
    imu_quaternion_normalize(q);
}

/* Unit gravity vector expressed in the body frame. */
static void predicted_gravity_body(const float q[4], float gravity_body[3])
{
    gravity_body[0] = 2.0f * (q[1] * q[3] - q[0] * q[2]);
    gravity_body[1] = 2.0f * (q[0] * q[1] + q[2] * q[3]);
    gravity_body[2] = q[0] * q[0] - q[1] * q[1] -
                      q[2] * q[2] + q[3] * q[3];
}

void imu_complementary_init(ImuComplementaryFilter *filter,
                            const float gyro_bias[3],
                            float accel_gain)
{
    memset(filter, 0, sizeof(*filter));
    filter->q[0] = 1.0f;
    filter->gyro_bias[0] = gyro_bias[0];
    filter->gyro_bias[1] = gyro_bias[1];
    filter->gyro_bias[2] = gyro_bias[2];
    filter->accel_gain = accel_gain;
}

void imu_complementary_update(ImuComplementaryFilter *filter,
                              const float gyro_rad_s[3],
                              const float accel_m_s2[3],
                              float dt_s)
{
    float measured_gravity[3];
    float predicted_gravity[3];
    float correction[3] = {0.0f, 0.0f, 0.0f};
    float omega[3];
    float accel_norm;

    if (dt_s <= 0.0f)
    {
        return;
    }

    accel_norm = sqrtf(accel_m_s2[0] * accel_m_s2[0] +
                       accel_m_s2[1] * accel_m_s2[1] +
                       accel_m_s2[2] * accel_m_s2[2]);

    if (accel_norm > IMU_EPSILON)
    {
        measured_gravity[0] = accel_m_s2[0] / accel_norm;
        measured_gravity[1] = accel_m_s2[1] / accel_norm;
        measured_gravity[2] = accel_m_s2[2] / accel_norm;
        predicted_gravity_body(filter->q, predicted_gravity);

        /* measured x predicted gives the body-frame attitude correction. */
        correction[0] = measured_gravity[1] * predicted_gravity[2] -
                        measured_gravity[2] * predicted_gravity[1];
        correction[1] = measured_gravity[2] * predicted_gravity[0] -
                        measured_gravity[0] * predicted_gravity[2];
        correction[2] = measured_gravity[0] * predicted_gravity[1] -
                        measured_gravity[1] * predicted_gravity[0];
    }

    omega[0] = gyro_rad_s[0] - filter->gyro_bias[0] +
               filter->accel_gain * correction[0];
    omega[1] = gyro_rad_s[1] - filter->gyro_bias[1] +
               filter->accel_gain * correction[1];
    omega[2] = gyro_rad_s[2] - filter->gyro_bias[2] +
               filter->accel_gain * correction[2];
    quaternion_integrate(filter->q, omega, dt_s);
}

static uint8_t invert_3x3(const float matrix[3][3], float inverse[3][3])
{
    const float determinant =
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1]) -
        matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0]) +
        matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0]);

    if (fabsf(determinant) < IMU_EPSILON)
    {
        return 0U;
    }

    inverse[0][0] =  (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1]) / determinant;
    inverse[0][1] = -(matrix[0][1] * matrix[2][2] - matrix[0][2] * matrix[2][1]) / determinant;
    inverse[0][2] =  (matrix[0][1] * matrix[1][2] - matrix[0][2] * matrix[1][1]) / determinant;
    inverse[1][0] = -(matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0]) / determinant;
    inverse[1][1] =  (matrix[0][0] * matrix[2][2] - matrix[0][2] * matrix[2][0]) / determinant;
    inverse[1][2] = -(matrix[0][0] * matrix[1][2] - matrix[0][2] * matrix[1][0]) / determinant;
    inverse[2][0] =  (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0]) / determinant;
    inverse[2][1] = -(matrix[0][0] * matrix[2][1] - matrix[0][1] * matrix[2][0]) / determinant;
    inverse[2][2] =  (matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]) / determinant;
    return 1U;
}

void imu_ekf_init(ImuQuaternionEkf *filter, const float gyro_bias[3])
{
    uint32_t i;

    memset(filter, 0, sizeof(*filter));
    filter->q[0] = 1.0f;
    filter->gyro_bias[0] = gyro_bias[0];
    filter->gyro_bias[1] = gyro_bias[1];
    filter->gyro_bias[2] = gyro_bias[2];

    /* Conservative defaults for MPU6050 at 500 Hz EKF update rate. */
    filter->gyro_noise = 0.015f;
    filter->bias_noise = 0.00015f;
    filter->accel_noise = 0.035f;
    filter->gravity = 9.80665f;
    filter->accel_gate = 0.10f * filter->gravity;

    for (i = 0U; i < 3U; ++i)
    {
        filter->covariance[i][i] = 0.05f;
        filter->covariance[i + 3U][i + 3U] = 0.0025f;
    }

    /* Gravity cannot observe Z gyro bias; retain the stored calibration. */
    filter->covariance[5][5] = 1.0e-8f;
}

static void ekf_predict_covariance(ImuQuaternionEkf *filter,
                                   const float omega[3],
                                   float dt_s)
{
    float transition[6][6] = {{0.0f}};
    float intermediate[6][6] = {{0.0f}};
    float predicted[6][6] = {{0.0f}};
    uint32_t row;
    uint32_t col;
    uint32_t k;

    for (row = 0U; row < 6U; ++row)
    {
        transition[row][row] = 1.0f;
    }

    transition[0][1] =  omega[2] * dt_s;
    transition[0][2] = -omega[1] * dt_s;
    transition[1][0] = -omega[2] * dt_s;
    transition[1][2] =  omega[0] * dt_s;
    transition[2][0] =  omega[1] * dt_s;
    transition[2][1] = -omega[0] * dt_s;
    transition[0][3] = -dt_s;
    transition[1][4] = -dt_s;
    transition[2][5] = -dt_s;

    for (row = 0U; row < 6U; ++row)
    {
        for (col = 0U; col < 6U; ++col)
        {
            for (k = 0U; k < 6U; ++k)
            {
                intermediate[row][col] += transition[row][k] *
                                           filter->covariance[k][col];
            }
        }
    }

    for (row = 0U; row < 6U; ++row)
    {
        for (col = 0U; col < 6U; ++col)
        {
            for (k = 0U; k < 6U; ++k)
            {
                predicted[row][col] += intermediate[row][k] * transition[col][k];
            }
        }
    }

    for (row = 0U; row < 3U; ++row)
    {
        predicted[row][row] += filter->gyro_noise * filter->gyro_noise * dt_s;
        predicted[row + 3U][row + 3U] +=
            filter->bias_noise * filter->bias_noise * dt_s;
    }
    predicted[5][5] = 1.0e-8f;
    memcpy(filter->covariance, predicted, sizeof(predicted));
}

static uint8_t ekf_accelerometer_update(ImuQuaternionEkf *filter,
                                        const float accel_m_s2[3])
{
    float accel_norm;
    float measured[3];
    float predicted_gravity[3];
    float residual[3];
    float measurement[3][6] = {{0.0f}};
    float innovation[3][3] = {{0.0f}};
    float innovation_inverse[3][3];
    float normalized_innovation_squared = 0.0f;
    float gain[6][3] = {{0.0f}};
    float correction[6] = {0.0f};
    float kh[6][6] = {{0.0f}};
    float updated_covariance[6][6] = {{0.0f}};
    uint32_t row;
    uint32_t col;
    uint32_t k;

    accel_norm = sqrtf(accel_m_s2[0] * accel_m_s2[0] +
                       accel_m_s2[1] * accel_m_s2[1] +
                       accel_m_s2[2] * accel_m_s2[2]);
    if (accel_norm < IMU_EPSILON ||
        fabsf(accel_norm - filter->gravity) > filter->accel_gate)
    {
        filter->accel_reject_count++;
        return 0U;
    }

    measured[0] = accel_m_s2[0] / accel_norm;
    measured[1] = accel_m_s2[1] / accel_norm;
    measured[2] = accel_m_s2[2] / accel_norm;
    predicted_gravity_body(filter->q, predicted_gravity);
    residual[0] = measured[0] - predicted_gravity[0];
    residual[1] = measured[1] - predicted_gravity[1];
    residual[2] = measured[2] - predicted_gravity[2];

    /* H = [skew(predicted_gravity), 0]. */
    measurement[0][1] = -predicted_gravity[2];
    measurement[0][2] =  predicted_gravity[1];
    measurement[1][0] =  predicted_gravity[2];
    measurement[1][2] = -predicted_gravity[0];
    measurement[2][0] = -predicted_gravity[1];
    measurement[2][1] =  predicted_gravity[0];

    for (row = 0U; row < 3U; ++row)
    {
        for (col = 0U; col < 3U; ++col)
        {
            for (k = 0U; k < 6U; ++k)
            {
                uint32_t j;
                for (j = 0U; j < 6U; ++j)
                {
                    innovation[row][col] += measurement[row][k] *
                        filter->covariance[k][j] * measurement[col][j];
                }
            }
        }
        innovation[row][row] += filter->accel_noise * filter->accel_noise;
    }

    if (!invert_3x3(innovation, innovation_inverse))
    {
        filter->accel_reject_count++;
        return 0U;
    }

    /*
     * Chi-square gate for three acceleration measurements.  The magnitude
     * gate alone cannot detect every linear acceleration because a disturbed
     * vector can still have a norm close to 1 g.  Allow the first updates to
     * establish roll/pitch before enabling the innovation gate.
     */
    for (row = 0U; row < 3U; ++row)
    {
        for (col = 0U; col < 3U; ++col)
        {
            normalized_innovation_squared += residual[row] *
                innovation_inverse[row][col] * residual[col];
        }
    }
    if (filter->accel_update_count >= 50U &&
        normalized_innovation_squared > 16.27f)
    {
        filter->accel_reject_count++;
        return 0U;
    }

    for (row = 0U; row < 6U; ++row)
    {
        for (col = 0U; col < 3U; ++col)
        {
            float p_ht[3] = {0.0f, 0.0f, 0.0f};
            uint32_t measurement_row;
            for (measurement_row = 0U; measurement_row < 3U; ++measurement_row)
            {
                for (k = 0U; k < 6U; ++k)
                {
                    p_ht[measurement_row] += filter->covariance[row][k] *
                                              measurement[measurement_row][k];
                }
            }
            for (measurement_row = 0U; measurement_row < 3U; ++measurement_row)
            {
                gain[row][col] += p_ht[measurement_row] *
                                  innovation_inverse[measurement_row][col];
            }
        }
    }

    /* Keep the stored Z bias fixed: gravity has no absolute yaw information. */
    gain[5][0] = 0.0f;
    gain[5][1] = 0.0f;
    gain[5][2] = 0.0f;

    for (row = 0U; row < 6U; ++row)
    {
        for (col = 0U; col < 3U; ++col)
        {
            correction[row] += gain[row][col] * residual[col];
        }
    }

    quaternion_apply_body_error(filter->q, correction);
    filter->gyro_bias[0] += correction[3];
    filter->gyro_bias[1] += correction[4];

    for (row = 0U; row < 6U; ++row)
    {
        for (col = 0U; col < 6U; ++col)
        {
            for (k = 0U; k < 3U; ++k)
            {
                kh[row][col] += gain[row][k] * measurement[k][col];
            }
        }
    }

    for (row = 0U; row < 6U; ++row)
    {
        for (col = 0U; col < 6U; ++col)
        {
            for (k = 0U; k < 6U; ++k)
            {
                float identity_minus_kh = ((row == k) ? 1.0f : 0.0f) - kh[row][k];
                updated_covariance[row][col] += identity_minus_kh *
                                                filter->covariance[k][col];
            }
        }
    }

    for (row = 0U; row < 6U; ++row)
    {
        for (col = row; col < 6U; ++col)
        {
            float symmetric = 0.5f * (updated_covariance[row][col] +
                                      updated_covariance[col][row]);
            filter->covariance[row][col] = symmetric;
            filter->covariance[col][row] = symmetric;
        }
        if (filter->covariance[row][row] < 1.0e-9f)
        {
            filter->covariance[row][row] = 1.0e-9f;
        }
    }
    filter->covariance[5][5] = 1.0e-8f;
    filter->accel_update_count++;
    return 1U;
}

uint8_t imu_ekf_update(ImuQuaternionEkf *filter,
                       const float gyro_rad_s[3],
                       const float accel_m_s2[3],
                       float dt_s)
{
    float omega[3];

    if (dt_s <= 0.0f || dt_s > 0.02f)
    {
        return 0U;
    }

    omega[0] = gyro_rad_s[0] - filter->gyro_bias[0];
    omega[1] = gyro_rad_s[1] - filter->gyro_bias[1];
    omega[2] = gyro_rad_s[2] - filter->gyro_bias[2];
    quaternion_integrate(filter->q, omega, dt_s);
    ekf_predict_covariance(filter, omega, dt_s);
    filter->predict_count++;
    return ekf_accelerometer_update(filter, accel_m_s2);
}

void imu_quaternion_to_euler_deg(const float q[4], float euler_deg[3])
{
    const float sin_pitch = clampf(2.0f * (q[0] * q[2] - q[3] * q[1]),
                                   -1.0f, 1.0f);

    euler_deg[0] = atan2f(2.0f * (q[0] * q[1] + q[2] * q[3]),
                          1.0f - 2.0f * (q[1] * q[1] + q[2] * q[2])) * IMU_RAD_TO_DEG;
    euler_deg[1] = asinf(sin_pitch) * IMU_RAD_TO_DEG;
    euler_deg[2] = atan2f(2.0f * (q[0] * q[3] + q[1] * q[2]),
                          1.0f - 2.0f * (q[2] * q[2] + q[3] * q[3])) * IMU_RAD_TO_DEG;
}

float imu_quaternion_error_deg(const float estimate[4], const float reference[4])
{
    float dot = estimate[0] * reference[0] + estimate[1] * reference[1] +
                estimate[2] * reference[2] + estimate[3] * reference[3];
    dot = fabsf(clampf(dot, -1.0f, 1.0f));
    return 2.0f * acosf(dot) * IMU_RAD_TO_DEG;
}

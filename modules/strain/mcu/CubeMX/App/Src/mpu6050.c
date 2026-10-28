#include "mpu6050.h"

#define MPU6050_ADDRESS             (0x68U << 1)
#define MPU6050_REG_SMPLRT_DIV      0x19U
#define MPU6050_REG_CONFIG          0x1AU
#define MPU6050_REG_GYRO_CONFIG     0x1BU
#define MPU6050_REG_ACCEL_CONFIG    0x1CU
#define MPU6050_REG_INT_ENABLE      0x38U
#define MPU6050_REG_ACCEL_XOUT_H    0x3BU
#define MPU6050_REG_PWR_MGMT_1      0x6BU
#define MPU6050_REG_WHO_AM_I        0x75U

#define MPU6050_WHO_AM_I_VALUE      0x68U
#define MPU6050_TIMEOUT_MS          20U
#define MPU6050_GRAVITY_M_S2        9.80665f
#define MPU6050_ACCEL_LSB_PER_G     8192.0f
#define MPU6050_GYRO_LSB_PER_DPS    16.4f
#define MPU6050_DEG_TO_RAD          0.01745329251994329577f

static HAL_StatusTypeDef write_register(Mpu6050 *device, uint8_t reg, uint8_t value)
{
    return HAL_I2C_Mem_Write(device->i2c, device->address, reg,
                             I2C_MEMADD_SIZE_8BIT, &value, 1U,
                             MPU6050_TIMEOUT_MS);
}

static int16_t read_be_i16(const uint8_t *data)
{
    return (int16_t)(((uint16_t)data[0] << 8) | data[1]);
}

HAL_StatusTypeDef mpu6050_init(Mpu6050 *device, I2C_HandleTypeDef *i2c)
{
    uint8_t identity = 0U;

    if ((device == NULL) || (i2c == NULL))
    {
        return HAL_ERROR;
    }

    device->i2c = i2c;
    device->address = MPU6050_ADDRESS;

    if (HAL_I2C_Mem_Read(i2c, device->address, MPU6050_REG_WHO_AM_I,
                         I2C_MEMADD_SIZE_8BIT, &identity, 1U,
                         MPU6050_TIMEOUT_MS) != HAL_OK)
    {
        return HAL_ERROR;
    }
    if (identity != MPU6050_WHO_AM_I_VALUE)
    {
        return HAL_ERROR;
    }

    /* PLL clock, DLPF=2 (about 94 Hz), 500 Hz output, +-4 g, +-2000 dps. */
    if (write_register(device, MPU6050_REG_PWR_MGMT_1, 0x01U) != HAL_OK ||
        write_register(device, MPU6050_REG_CONFIG, 0x02U) != HAL_OK ||
        write_register(device, MPU6050_REG_SMPLRT_DIV, 0x01U) != HAL_OK ||
        write_register(device, MPU6050_REG_GYRO_CONFIG, 0x18U) != HAL_OK ||
        write_register(device, MPU6050_REG_ACCEL_CONFIG, 0x08U) != HAL_OK ||
        write_register(device, MPU6050_REG_INT_ENABLE, 0x01U) != HAL_OK)
    {
        return HAL_ERROR;
    }

    return HAL_OK;
}

HAL_StatusTypeDef mpu6050_read(Mpu6050 *device, Mpu6050Sample *sample)
{
    uint8_t raw[14];
    uint32_t axis;

    if ((device == NULL) || (sample == NULL))
    {
        return HAL_ERROR;
    }

    if (HAL_I2C_Mem_Read(device->i2c, device->address,
                         MPU6050_REG_ACCEL_XOUT_H, I2C_MEMADD_SIZE_8BIT,
                         raw, sizeof(raw), MPU6050_TIMEOUT_MS) != HAL_OK)
    {
        return HAL_ERROR;
    }

    sample->accel_raw[0] = read_be_i16(&raw[0]);
    sample->accel_raw[1] = read_be_i16(&raw[2]);
    sample->accel_raw[2] = read_be_i16(&raw[4]);
    sample->temperature_raw = read_be_i16(&raw[6]);
    sample->gyro_raw[0] = read_be_i16(&raw[8]);
    sample->gyro_raw[1] = read_be_i16(&raw[10]);
    sample->gyro_raw[2] = read_be_i16(&raw[12]);

    for (axis = 0U; axis < 3U; ++axis)
    {
        sample->accel_m_s2[axis] =
            ((float)sample->accel_raw[axis] / MPU6050_ACCEL_LSB_PER_G) *
            MPU6050_GRAVITY_M_S2;
        sample->gyro_rad_s[axis] =
            ((float)sample->gyro_raw[axis] / MPU6050_GYRO_LSB_PER_DPS) *
            MPU6050_DEG_TO_RAD;
    }

    return HAL_OK;
}

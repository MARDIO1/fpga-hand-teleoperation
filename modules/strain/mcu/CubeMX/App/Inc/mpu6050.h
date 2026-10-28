#ifndef MPU6050_H
#define MPU6050_H

#include "stm32f1xx_hal.h"

#include <stdint.h>

typedef struct
{
    int16_t accel_raw[3];
    int16_t temperature_raw;
    int16_t gyro_raw[3];
    float accel_m_s2[3];
    float gyro_rad_s[3];
} Mpu6050Sample;

typedef struct
{
    I2C_HandleTypeDef *i2c;
    uint16_t address;
} Mpu6050;

HAL_StatusTypeDef mpu6050_init(Mpu6050 *device, I2C_HandleTypeDef *i2c);
HAL_StatusTypeDef mpu6050_read(Mpu6050 *device, Mpu6050Sample *sample);

#endif

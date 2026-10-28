#include "app.h"

#include "imu_filter.h"
#include "main.h"
#include "mpu6050.h"

#include <string.h>

#define APP_IMU_PERIOD_MS          2U
#define APP_TELEMETRY_PERIOD_MS    10U
#define APP_CALIBRATION_SAMPLES    2500U
#define APP_PACKET_SIZE            46U
#define APP_MPU_RETRY_PERIOD_MS    500U
#define APP_MPU_MAX_INIT_ATTEMPTS  5U

#define STATUS_MPU_PRESENT         (1U << 0)
#define STATUS_SAMPLE_VALID        (1U << 1)
#define STATUS_CALIBRATING         (1U << 2)
#define STATUS_CALIBRATED          (1U << 3)
#define STATUS_TX_DROPPED          (1U << 4)
#define STATUS_MPU_INIT_ERROR      (1U << 5)

static ADC_HandleTypeDef *app_adc;
static UART_HandleTypeDef *app_uart;
static Mpu6050 app_mpu;
static Mpu6050Sample app_sample;
static ImuQuaternionEkf app_filter;

static volatile uint8_t app_imu_ready;
static volatile uint8_t app_uart_tx_busy;
static uint8_t app_uart_rx_byte;
static uint8_t app_status;
static uint32_t app_sequence;
static uint32_t app_last_imu_ms;
static uint32_t app_last_telemetry_ms;
static uint32_t app_last_mpu_retry_ms;
static uint8_t app_mpu_init_attempts;
static uint16_t app_adc_raw;
static uint8_t app_tx_buffer[APP_PACKET_SIZE];

static uint32_t app_calibration_count;
static float app_calibration_sum[3];

static void try_init_mpu(void)
{
    if (mpu6050_init(&app_mpu, app_mpu.i2c) == HAL_OK)
    {
        app_status |= STATUS_MPU_PRESENT;
        app_status &= (uint8_t)~STATUS_MPU_INIT_ERROR;
        app_imu_ready = 1U;
    }
    else
    {
        app_mpu_init_attempts++;
        app_status |= STATUS_MPU_INIT_ERROR;
    }
}

static uint16_t crc16_ccitt(const uint8_t *data, uint32_t length)
{
    uint16_t crc = 0xFFFFU;
    uint32_t index;
    uint8_t bit;

    for (index = 0U; index < length; ++index)
    {
        crc ^= (uint16_t)data[index] << 8;
        for (bit = 0U; bit < 8U; ++bit)
        {
            crc = (crc & 0x8000U) ? (uint16_t)((crc << 1) ^ 0x1021U)
                                  : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

static void put_u16_le(uint8_t *destination, uint16_t value)
{
    destination[0] = (uint8_t)value;
    destination[1] = (uint8_t)(value >> 8);
}

static void put_u32_le(uint8_t *destination, uint32_t value)
{
    destination[0] = (uint8_t)value;
    destination[1] = (uint8_t)(value >> 8);
    destination[2] = (uint8_t)(value >> 16);
    destination[3] = (uint8_t)(value >> 24);
}

static void put_float_le(uint8_t *destination, float value)
{
    uint32_t raw;
    memcpy(&raw, &value, sizeof(raw));
    put_u32_le(destination, raw);
}

static void start_calibration(void)
{
    if ((app_status & STATUS_MPU_PRESENT) == 0U)
    {
        return;
    }

    app_calibration_count = 0U;
    app_calibration_sum[0] = 0.0f;
    app_calibration_sum[1] = 0.0f;
    app_calibration_sum[2] = 0.0f;
    app_status |= STATUS_CALIBRATING;
    app_status &= (uint8_t)~STATUS_CALIBRATED;
}

static void update_calibration(void)
{
    float bias[3];
    uint32_t axis;

    if ((app_status & STATUS_CALIBRATING) == 0U)
    {
        return;
    }

    for (axis = 0U; axis < 3U; ++axis)
    {
        app_calibration_sum[axis] += app_sample.gyro_rad_s[axis];
    }
    app_calibration_count++;

    if (app_calibration_count < APP_CALIBRATION_SAMPLES)
    {
        return;
    }

    for (axis = 0U; axis < 3U; ++axis)
    {
        bias[axis] = app_calibration_sum[axis] /
                     (float)APP_CALIBRATION_SAMPLES;
    }
    imu_ekf_init(&app_filter, bias);
    app_status &= (uint8_t)~STATUS_CALIBRATING;
    app_status |= STATUS_CALIBRATED;
}

static void sample_adc(void)
{
    if (HAL_ADC_Start(app_adc) == HAL_OK)
    {
        if (HAL_ADC_PollForConversion(app_adc, 2U) == HAL_OK)
        {
            app_adc_raw = (uint16_t)HAL_ADC_GetValue(app_adc);
        }
        (void)HAL_ADC_Stop(app_adc);
    }
}

static void send_telemetry(uint32_t now_ms)
{
    uint32_t axis;
    uint16_t crc;

    if (app_uart_tx_busy != 0U)
    {
        app_status |= STATUS_TX_DROPPED;
        return;
    }

    app_tx_buffer[0] = 'I';
    app_tx_buffer[1] = 'M';
    app_tx_buffer[2] = 'U';
    app_tx_buffer[3] = 'Q';
    app_tx_buffer[4] = 1U;
    app_tx_buffer[5] = app_status;
    put_u16_le(&app_tx_buffer[6], APP_PACKET_SIZE);
    put_u32_le(&app_tx_buffer[8], app_sequence++);
    put_u32_le(&app_tx_buffer[12], now_ms * 1000U);

    for (axis = 0U; axis < 4U; ++axis)
    {
        put_float_le(&app_tx_buffer[16U + axis * 4U], app_filter.q[axis]);
    }

    /* Five reserved ADC slots. PA2/ADC1_IN2 currently occupies slot zero. */
    put_u16_le(&app_tx_buffer[32], app_adc_raw);
    for (axis = 1U; axis < 5U; ++axis)
    {
        put_u16_le(&app_tx_buffer[32U + axis * 2U], 0xFFFFU);
    }
    put_u16_le(&app_tx_buffer[42], (uint16_t)app_sample.temperature_raw);
    crc = crc16_ccitt(app_tx_buffer, APP_PACKET_SIZE - 2U);
    put_u16_le(&app_tx_buffer[44], crc);

    app_uart_tx_busy = 1U;
    app_status &= (uint8_t)~STATUS_TX_DROPPED;
    if (HAL_UART_Transmit_DMA(app_uart, app_tx_buffer, APP_PACKET_SIZE) != HAL_OK)
    {
        app_uart_tx_busy = 0U;
        app_status |= STATUS_TX_DROPPED;
    }
}

void app_init(ADC_HandleTypeDef *adc, I2C_HandleTypeDef *i2c,
              UART_HandleTypeDef *uart)
{
    const float zero_bias[3] = {0.0f, 0.0f, 0.0f};

    app_adc = adc;
    app_uart = uart;
    app_mpu.i2c = i2c;
    imu_ekf_init(&app_filter, zero_bias);

    (void)HAL_ADCEx_Calibration_Start(app_adc);
    try_init_mpu();

    HAL_NVIC_SetPriority(EXTI9_5_IRQn, 1U, 0U);
    HAL_NVIC_EnableIRQ(EXTI9_5_IRQn);
    (void)HAL_UART_Receive_IT(app_uart, &app_uart_rx_byte, 1U);
}

void app_process(void)
{
    uint32_t now_ms = HAL_GetTick();
    uint32_t imu_elapsed_ms = (uint32_t)(now_ms - app_last_imu_ms);

    if ((app_status & STATUS_MPU_PRESENT) == 0U &&
        app_mpu_init_attempts < APP_MPU_MAX_INIT_ATTEMPTS &&
        (uint32_t)(now_ms - app_last_mpu_retry_ms) >=
            APP_MPU_RETRY_PERIOD_MS)
    {
        app_last_mpu_retry_ms = now_ms;
        try_init_mpu();
    }

    if ((app_status & STATUS_MPU_PRESENT) != 0U &&
        imu_elapsed_ms > 0U &&
        (app_imu_ready != 0U || imu_elapsed_ms >= APP_IMU_PERIOD_MS))
    {
        float dt_s = (float)imu_elapsed_ms * 0.001f;

        app_imu_ready = 0U;
        app_last_imu_ms = now_ms;
        if (mpu6050_read(&app_mpu, &app_sample) == HAL_OK)
        {
            app_status |= STATUS_SAMPLE_VALID;
            update_calibration();
            (void)imu_ekf_update(&app_filter, app_sample.gyro_rad_s,
                                 app_sample.accel_m_s2, dt_s);
        }
        else
        {
            app_status &= (uint8_t)~STATUS_SAMPLE_VALID;
        }
    }

    if ((uint32_t)(now_ms - app_last_telemetry_ms) >=
        APP_TELEMETRY_PERIOD_MS)
    {
        app_last_telemetry_ms = now_ms;
        sample_adc();
        send_telemetry(now_ms);
    }
}

void HAL_GPIO_EXTI_Callback(uint16_t gpio_pin)
{
    if (gpio_pin == MPU_INT_Pin)
    {
        app_imu_ready = 1U;
    }
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *uart)
{
    if (uart == app_uart)
    {
        app_uart_tx_busy = 0U;
    }
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *uart)
{
    if (uart == app_uart)
    {
        if ((app_uart_rx_byte == 'C') || (app_uart_rx_byte == 'c'))
        {
            start_calibration();
        }
        (void)HAL_UART_Receive_IT(app_uart, &app_uart_rx_byte, 1U);
    }
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *uart)
{
    if (uart == app_uart)
    {
        app_uart_tx_busy = 0U;
        (void)HAL_UART_Receive_IT(app_uart, &app_uart_rx_byte, 1U);
    }
}

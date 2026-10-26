#include "sys.h"
#include "delay.h"
#include "uart1.h"
#include "adc.h"

#define FRAME_SIZE 28U
#define FRAME_PERIOD_MS 10U

extern UART_HandleTypeDef uart1_handle;

static void put_u16(uint8_t *bytes, uint16_t value)
{
    bytes[0] = (uint8_t)value;
    bytes[1] = (uint8_t)(value >> 8);
}

static void put_u32(uint8_t *bytes, uint32_t value)
{
    put_u16(bytes, (uint16_t)value);
    put_u16(bytes + 2, (uint16_t)(value >> 16));
}

static uint16_t crc16(const uint8_t *bytes, uint32_t size)
{
    uint16_t crc = 0xffff;
    uint32_t i;
    uint8_t bit;

    for (i = 0; i < size; ++i)
    {
        crc ^= (uint16_t)bytes[i] << 8;
        for (bit = 0; bit < 8; ++bit)
        {
            crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021)
                                 : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

int main(void)
{
    uint8_t frame[FRAME_SIZE] = {'S', 'T', 'R', 'N', 1, 0, FRAME_SIZE, 0};
    uint32_t sequence = 0;
    uint32_t next_ms;
    uint16_t adc;

    HAL_Init();
    stm32_clock_init(RCC_PLL_MUL9);     /* 72 MHz */

    uart1_init(115200);
    adc_init();
    next_ms = HAL_GetTick();

    while (1)
    {
        HAL_ADC_Start(&adc_handle);
        HAL_ADC_PollForConversion(&adc_handle, 10);
        adc = (uint16_t)HAL_ADC_GetValue(&adc_handle);
        HAL_ADC_Stop(&adc_handle);

        put_u32(frame + 8, sequence++);
        put_u32(frame + 12, HAL_GetTick() * 1000U);
        put_u16(frame + 16, 0);
        put_u16(frame + 18, 0);
        put_u16(frame + 20, adc);  /* middle finger: PA2 / ADC1_IN2 */
        put_u16(frame + 22, 0);
        put_u16(frame + 24, 0);
        put_u16(frame + 26, crc16(frame, 26));
        HAL_UART_Transmit(&uart1_handle, frame, FRAME_SIZE, 5);

        next_ms += FRAME_PERIOD_MS;
        while ((int32_t)(HAL_GetTick() - next_ms) < 0)
        {
        }
    }
}

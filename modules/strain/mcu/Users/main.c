#include "sys.h"
#include "delay.h"
#include "uart1.h"
#include "adc.h"
#include <stdio.h>

int main(void)
{
    uint32_t adc;
    uint32_t voltage_mv;

    HAL_Init();
    stm32_clock_init(RCC_PLL_MUL9);     /* 72 MHz */

    uart1_init(115200);
    adc_init();

    printf("\r\nADC1 IN2 (PA2) test\r\n");

    while (1)
    {
        HAL_ADC_Start(&adc_handle);
        HAL_ADC_PollForConversion(&adc_handle, 10);
        adc = HAL_ADC_GetValue(&adc_handle);
        HAL_ADC_Stop(&adc_handle);

        voltage_mv = adc * 3300 / 4095;

        printf("ADC=%u  Voltage=%u.%03u V\r\n",
               (unsigned int)adc,
               (unsigned int)(voltage_mv / 1000),
               (unsigned int)(voltage_mv % 1000));

        delay_ms(500);
    }
}

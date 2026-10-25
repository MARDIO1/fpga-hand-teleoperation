#include "adc.h"

ADC_HandleTypeDef adc_handle;

/* ADC1 + PA2(ADC1_IN2), polling mode */
void adc_init(void)
{
    ADC_ChannelConfTypeDef channel = {0};

    adc_handle.Instance = ADC1;
    adc_handle.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    adc_handle.Init.ScanConvMode = ADC_SCAN_DISABLE;
    adc_handle.Init.ContinuousConvMode = DISABLE;
    adc_handle.Init.NbrOfConversion = 1;
    adc_handle.Init.DiscontinuousConvMode = DISABLE;
    adc_handle.Init.NbrOfDiscConversion = 0;
    adc_handle.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    HAL_ADC_Init(&adc_handle);              /* calls HAL_ADC_MspInit() */

    channel.Channel = ADC_CHANNEL_2;
    channel.Rank = ADC_REGULAR_RANK_1;
    channel.SamplingTime = ADC_SAMPLETIME_239CYCLES_5;
    HAL_ADC_ConfigChannel(&adc_handle, &channel);

    HAL_ADCEx_Calibration_Start(&adc_handle);
}

/* Called by HAL_ADC_Init(): ADC clock + PA2 analog input */
void HAL_ADC_MspInit(ADC_HandleTypeDef *hadc)
{
    RCC_PeriphCLKInitTypeDef clk = {0};
    GPIO_InitTypeDef gpio = {0};

    if (hadc->Instance != ADC1)
    {
        return;
    }

    __HAL_RCC_ADC1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    clk.PeriphClockSelection = RCC_PERIPHCLK_ADC;
    clk.AdcClockSelection = RCC_ADCPCLK2_DIV6;   /* 72 MHz / 6 = 12 MHz */
    HAL_RCCEx_PeriphCLKConfig(&clk);

    gpio.Pin = GPIO_PIN_2;
    gpio.Mode = GPIO_MODE_ANALOG;
    HAL_GPIO_Init(GPIOA, &gpio);
}

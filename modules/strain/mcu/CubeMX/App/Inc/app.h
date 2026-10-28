#ifndef APP_H
#define APP_H

#include "stm32f1xx_hal.h"

void app_init(ADC_HandleTypeDef *adc, I2C_HandleTypeDef *i2c,
              UART_HandleTypeDef *uart);
void app_process(void);

#endif

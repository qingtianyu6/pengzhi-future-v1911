#ifndef GH_BOARD_H
#define GH_BOARD_H
#include <stdint.h>
#define REG(a) (*(volatile uint32_t *)(a))
#define GPIOA 0x40010800u
#define GPIOB 0x40010C00u
#define GPIOC 0x40011000u
extern volatile uint32_t gh_ms;
void board_init(void);
void board_outputs(uint8_t mask);
void uart_send(const char*data,unsigned n);
int uart_pop(void);
void oled_init(void);
void oled_show(const int32_t env[5],uint8_t mask,uint8_t manual);
#endif

#include "board.h"
#include "config.h"
volatile uint32_t gh_ms;
static volatile uint8_t ring[256];static volatile unsigned head,tail;
void SysTick_Handler(void){gh_ms++;}
void USART1_IRQHandler(void){
    uint32_t sr=REG(0x40013800u);uint8_t b=(uint8_t)REG(0x40013804u);
    if(sr&(1u<<5)){unsigned next=(head+1)&255u;if(next!=tail){ring[head]=b;head=next;}}
}
int uart_pop(void){if(head==tail)return -1;uint8_t b=ring[tail];tail=(tail+1)&255u;return b;}
void uart_send(const char*d,unsigned n){while(n--){while(!(REG(0x40013800u)&(1u<<7))){}REG(0x40013804u)=(uint8_t)*d++;}}
void board_outputs(uint8_t mask){
    uint32_t pins=GH_OUTPUTS_CONFIRMED?(mask&7u):0;
    REG(GPIOA+0x10u)=pins|((~pins&7u)<<16);
    /* Blue Pill PC13 LED is assumed active-low. */
    REG(GPIOC+0x10u)=(mask&8u)?(1u<<29):(1u<<13);
}
void board_init(void){
    /* Reset state HSI 8MHz, no PLL, APB2 8MHz. */
    REG(0x40021018u)|=(1u<<0)|(1u<<2)|(1u<<3)|(1u<<4)|(1u<<14);
    REG(GPIOA+0x10u)=7u<<16; /* preload inactive before output mode */
    REG(GPIOA)=(REG(GPIOA)&~0xFFFu)|0x222u; /* PA0/1/2: 2MHz push-pull */
    REG(GPIOA+4u)=(REG(GPIOA+4u)&~0xFF0u)|0x4B0u; /* PA9 TX AF, PA10 RX floating */
    REG(GPIOC+0x10u)=1u<<13;
    REG(GPIOC+4u)=(REG(GPIOC+4u)&~(15u<<20))|(2u<<20);
    REG(0x40013808u)=(GH_CLOCK+GH_BAUD/2u)/GH_BAUD;
    REG(0x4001380Cu)=(1u<<13)|(1u<<5)|(1u<<3)|(1u<<2);
    REG(0xE000E104u)=1u<<5; /* USART1 IRQ37 */
    REG(0xE000E014u)=GH_CLOCK/1000u-1u;REG(0xE000E018u)=0;REG(0xE000E010u)=7;
    board_outputs(0);
    /* Independent watchdog: LSI tolerance is hardware dependent; nominal ~2s. */
    REG(0x40003000u)=0xCCCC;REG(0x40003000u)=0x5555;REG(0x40003004u)=4;REG(0x40003008u)=1250;
    for(unsigned i=0;i<100000u && REG(0x4000300Cu);i++){}
    REG(0x40003000u)=0xAAAA;
}

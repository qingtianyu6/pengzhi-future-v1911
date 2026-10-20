#include <stdint.h>
extern uint32_t _estack,_sidata,_sdata,_edata,_sbss,_ebss;
extern int main(void);
void Reset_Handler(void){uint32_t*s=&_sidata,*d=&_sdata;while(d<&_edata)*d++=*s++;d=&_sbss;while(d<&_ebss)*d++=0;main();for(;;){}}
extern void board_outputs(uint8_t mask);
void Default_Handler(void){board_outputs(0);for(;;){}}
extern void SysTick_Handler(void);
extern void USART1_IRQHandler(void);
typedef void(*handler)(void);
__attribute__((section(".isr_vector"),used))
const handler vectors[76]={
    [0]=(handler)&_estack,[1]=Reset_Handler,[2]=Default_Handler,[3]=Default_Handler,
    [4]=Default_Handler,[5]=Default_Handler,[6]=Default_Handler,[11]=Default_Handler,
    [12]=Default_Handler,[14]=Default_Handler,[15]=SysTick_Handler,[16+37]=USART1_IRQHandler,
};

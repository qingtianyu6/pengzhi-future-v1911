#include "board.h"
#include "control.h"
static gh_state state;
int main(void){
    board_init();gh_init(&state,gh_ms);oled_init();
    char rx[GH_MAX_FRAME],tx[GH_MAX_FRAME];unsigned used=0;int overflow=0;
    uint32_t last_byte=0,display=0;
    for(;;){
        REG(0x40003000u)=0xAAAA; /* Feed only from main loop. */
        gh_watchdog(&state,gh_ms);board_outputs(state.mask);
        if(used && (uint32_t)(gh_ms-last_byte)>100){used=0;overflow=0;}
        int b;
        while((b=uart_pop())>=0){
            last_byte=gh_ms;
            if(!overflow){if(used<GH_MAX_FRAME)rx[used++]=(char)b;else overflow=1;}
            if(b=='\n'){
                if(!overflow){unsigned n=gh_process(&state,rx,used,tx,gh_ms);board_outputs(state.mask);if(n)uart_send(tx,n);}
                used=0;overflow=0;
            }
        }
        if((uint32_t)(gh_ms-display)>=1000){display=gh_ms;oled_show(state.env,state.mask,state.manual);}
    }
}

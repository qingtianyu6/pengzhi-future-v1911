/* Host-only protocol/safety test adapter. Never linked into MCU image. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "control.h"
int main(void){
    gh_state s;gh_init(&s,0);char line[300],tx[GH_MAX_FRAME];
    while(fgets(line,sizeof(line),stdin)){
        char*p=strchr(line,' ');if(!p)return 2;*p++=0;uint32_t now=(uint32_t)strtoul(line,0,10);
        unsigned n=gh_process(&s,p,(unsigned)strlen(p),tx,now);
        if(n)fwrite(tx,1,n,stdout);else puts("NO_RESPONSE");
    }
    return 0;
}

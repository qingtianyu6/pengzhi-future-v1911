#include "control.h"
static void zero(void *p,unsigned n) { uint8_t *b=p; while(n--) *b++=0; }
static int same(const char*a,const char*b) { while(*a && *a==*b){a++;b++;} return *a==*b; }
static void copy(char*a,const char*b) { while((*a++=*b++)){} }
static int number(const char *s,int32_t *v) {
    uint32_t n=0; int neg=0;
    if(*s=='-'){neg=1;s++;} if(!*s) return 0;
    while(*s){ if(*s<'0'||*s>'9'||n>214748364u) return 0;
        uint32_t digit=(uint32_t)(*s++-'0');
        if(n==214748364u && digit>7u) return 0;
        n=n*10u+digit; }
    *v=neg?-(int32_t)n:(int32_t)n; return 1;
}
static int hex(char c) { if(c>='0'&&c<='9')return c-'0'; if(c>='A'&&c<='F')return c-'A'+10; if(c>='a'&&c<='f')return c-'a'+10; return -1; }
static char *append(char*p,const char*s) { while(*s)*p++=*s++; return p; }
static char *decimal(char*p,uint32_t n) { char b[10];unsigned i=0; do{b[i++]=(char)('0'+n%10);n/=10;}while(n); while(i)*p++=b[--i];return p; }
static unsigned response(uint32_t seq,const char*kind,uint8_t mask,unsigned error,char*tx) {
    char *p=append(tx,"V1,"); p=decimal(p,seq); p=append(p,error?",ERR,":",ACK,");
    if(error)p=decimal(p,error);else {p=append(p,kind);*p++=',';p=decimal(p,mask);}
    uint8_t sum=0;for(char*q=tx;q<p;q++)sum^=(uint8_t)*q;
    *p++='*'; const char*h="0123456789ABCDEF"; *p++=h[sum>>4];*p++=h[sum&15];*p++='\n';*p=0;
    return (unsigned)(p-tx);
}
static void output(gh_state*s,uint8_t mask,uint32_t now,uint8_t reason) {
    if((s->mask^mask)&1) s->fan_changed=now;
    if((s->mask^mask)&4) s->lamp_changed=now;
    if((s->mask&2) && !(mask&2)) s->pump_off=now;
    if(!(s->mask&2) && (mask&2)) s->pump_since=now;
    if(mask!=s->mask){unsigned i=s->log_index++%16;s->logs[i].at=now;s->logs[i].mask=mask;s->logs[i].reason=reason;}
    s->mask=mask;
}
void gh_init(gh_state*s,uint32_t now) {
    zero(s,sizeof(*s));s->fan_changed=now-GH_SWITCH_MIN_MS;s->lamp_changed=now-GH_SWITCH_MIN_MS;
    s->pump_off=now-GH_PUMP_COOLDOWN_MS;
}
void gh_watchdog(gh_state*s,uint32_t now) {
    if(s->mask && (uint32_t)(now-s->last_set)>s->lease) output(s,0,now,1);
    if((s->mask&2) && (uint32_t)(now-s->pump_since)>=GH_PUMP_MAX_MS) output(s,s->mask&~2u,now,2);
}
unsigned gh_process(gh_state*s,const char*rx,unsigned size,char*tx,uint32_t now) {
    gh_watchdog(s,now);
    if(size<10||size>GH_MAX_FRAME||rx[size-1]!='\n'||rx[size-4]!='*') return 0;
    uint8_t sum=0;uint32_t hash=2166136261u;
    for(unsigned i=0;i<size-4;i++){sum^=(uint8_t)rx[i];hash=(hash^(uint8_t)rx[i])*16777619u;}
    int h=hex(rx[size-3]),l=hex(rx[size-2]);if(h<0||l<0||sum!=(h*16+l))return 0;
    char buf[GH_MAX_FRAME],*field[9];unsigned count=1;field[0]=buf;
    for(unsigned i=0;i<size-4;i++){buf[i]=rx[i];if(rx[i]==','){if(count>=9)return 0;buf[i]=0;field[count++]=buf+i+1;}}
    buf[size-4]=0;int32_t seq;
    if(count<3||!same(field[0],"V1")||!number(field[1],&seq)||seq<=0)return 0;
    const char*kind=field[2];if(!(same(kind,"ENV")||same(kind,"SET")||same(kind,"PING")||same(kind,"STOP")))return response((uint32_t)seq,kind,s->mask,1,tx);
    for(unsigned i=0;i<8;i++)if(s->cache[i].seq==(uint32_t)seq){
        if(s->cache[i].hash!=hash)return response((uint32_t)seq,kind,s->mask,5,tx);
        return response((uint32_t)seq,s->cache[i].kind,s->mask,s->cache[i].error,tx);
    }
    unsigned error=0;int32_t v[5];
    if(same(kind,"ENV")){
        if(count!=8)error=2;else {
            for(unsigned i=0;i<5;i++)if(!number(field[i+3],v+i))error=2;
            if(!error && (v[0]<-100||v[0]>600||v[1]<0||v[1]>1000||v[2]<-100||v[2]>600||v[3]<0||v[3]>1000||v[4]<0||v[4]>100000))error=2;
            if(!error)for(unsigned i=0;i<5;i++)s->env[i]=v[i];
        }
    }else if(same(kind,"SET")){
        if(count!=6||!number(field[3],v)||!number(field[4],v+1)||!number(field[5],v+2))error=2;
        else if(v[0]<0||v[0]>15||v[1]<100||v[1]>5000||v[2]<0||v[2]>1)error=2;
        else if(!GH_OUTPUTS_CONFIRMED && (v[0]&7))error=3;
        else if(((v[0]&2) && (((s->mask&2) && (uint32_t)(now-s->pump_since)>=GH_PUMP_MAX_MS) ||
                 (!(s->mask&2) && (uint32_t)(now-s->pump_off)<GH_PUMP_COOLDOWN_MS))) ||
                (((v[0]^s->mask)&1) && (uint32_t)(now-s->fan_changed)<GH_SWITCH_MIN_MS) ||
                (((v[0]^s->mask)&4) && (uint32_t)(now-s->lamp_changed)<GH_SWITCH_MIN_MS))error=4;
        else {output(s,(uint8_t)v[0],now,0);s->last_set=now;s->lease=(uint32_t)v[1];s->manual=(uint8_t)v[2];}
    }else if(same(kind,"STOP")){
        if(count!=3)error=2;else {output(s,0,now,3);s->manual=1;}
    }else if(count!=3)error=2;
    gh_cache*c=&s->cache[s->cache_index++%8];c->seq=(uint32_t)seq;c->hash=hash;copy(c->kind,kind);c->error=(uint8_t)error;
    return response((uint32_t)seq,kind,s->mask,error,tx);
}

/* Independent SSD1306 bit-banged open-drain I2C on PB6/PB7, address configurable.
 * No claim of physical validation. Missing device ACK aborts transfer promptly. */
#include "board.h"
#include "config.h"
static int available;
static void delay(void){for(volatile unsigned i=0;i<18;i++)__asm volatile("nop");}
static void scl(int hi){REG(GPIOB+0x10u)=1u<<(hi?6:22);delay();}
static void sda(int hi){REG(GPIOB+0x10u)=1u<<(hi?7:23);delay();}
static int clock_hi(void){scl(1);for(unsigned i=0;i<1000;i++)if(REG(GPIOB+8u)&(1u<<6))return 1;return 0;}
static void stop(void){sda(0);scl(1);sda(1);}
static int byte(uint8_t b){
    for(unsigned i=0;i<8;i++){scl(0);sda(b&128);if(!clock_hi())return 0;b<<=1;}
    scl(0);sda(1);if(!clock_hi())return 0;int ack=!(REG(GPIOB+8u)&(1u<<7));scl(0);return ack;
}
static int begin(uint8_t mode){sda(1);if(!clock_hi())return 0;sda(0);scl(0);return byte(GH_OLED_ADDRESS<<1)&&byte(mode);}
static int command(uint8_t c){int ok=begin(0)&&byte(c);stop();return ok;}
void oled_init(void){
    if(!GH_OLED_ENABLED)return;
    REG(GPIOB+0x10u)=(1u<<6)|(1u<<7);
    REG(GPIOB)=(REG(GPIOB)&0x00FFFFFFu)|0x66000000u; /* open-drain output */
    const uint8_t setup[]={0xAE,0xD5,0x80,0xA8,GH_OLED_HEIGHT-1,0xD3,0,0x40,0x8D,0x14,0x20,0x02,0xA1,0xC8,0xDA,0x12,0x81,0x7F,0xD9,0xF1,0xDB,0x40,0xA4,0xA6,0xAF};
    for(unsigned i=0;i<sizeof(setup);i++)if(!command(setup[i]))return;
    available=1;
}
static const char chars[]="0123456789AIRHSOLWTEUXMGPDN:.- ";
static const uint8_t font[][5]={
 {62,81,73,69,62},{0,66,127,64,0},{66,97,81,73,70},{33,65,69,75,49},{24,20,18,127,16},
 {39,69,69,69,57},{60,74,73,73,48},{1,113,9,5,3},{54,73,73,73,54},{6,73,73,41,30},
 {126,17,17,17,126},{0,65,127,65,0},{127,9,25,41,70},{127,8,8,8,127},{70,73,73,73,49},
 {62,65,65,65,62},{127,64,64,64,64},{63,64,56,64,63},{1,1,127,1,1},{127,73,73,73,65},
 {63,64,64,64,63},{99,20,8,20,99},{127,2,12,2,127},{62,65,73,73,122},{127,9,9,9,6},
 {127,65,65,34,28},{127,4,8,16,127},{0,54,54,0,0},{0,96,96,0,0},{8,8,8,8,8},{0,0,0,0,0}};
static void line(unsigned page,const char *text){
    if(page>=GH_OLED_HEIGHT/8u)return;
    if(!command(0xB0u+page)||!command(0)||!command(0x10)||!begin(0x40)){available=0;stop();return;}
    unsigned pos=0;
    while(*text && pos<126){unsigned j=0;while(chars[j]&&chars[j]!=*text)j++;if(!chars[j])j=30;
        for(unsigned x=0;x<5;x++){if(!byte(font[j][x])){available=0;stop();return;}pos++;}byte(0);pos++;text++;}
    while(pos++<128)byte(0);stop();
}
static char* num(char*p,int32_t n,int tenths){
    if(n<0){*p++='-';n=-n;}char b[10];unsigned i=0;int32_t whole=tenths?n/10:n;
    do{b[i++]=(char)('0'+whole%10);whole/=10;}while(whole);while(i)*p++=b[--i];
    if(tenths){*p++='.';*p++=(char)('0'+n%10);}*p=0;return p;
}
void oled_show(const int32_t env[5],uint8_t mask,uint8_t manual){
    if(!available)return;line(0,"SIM INPUT");
    const char*labels[]={"AIR ","RH ","SOIL ","WATER ","LUX "};
    for(unsigned i=0;i<5;i++){char text[22];char*p=text;const char*q=labels[i];while(*q)*p++=*q++;num(p,env[i],i<4);line(i+1,text);}
    char text[22]="GPIO ";num(text+5,mask,0);line(6,text);line(7,manual?"MODE MANUAL":"MODE AUTO");
}

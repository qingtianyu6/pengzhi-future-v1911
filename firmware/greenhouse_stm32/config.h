#ifndef GH_CONFIG_H
#define GH_CONFIG_H
/* Change only after checking wiring, active levels and external drivers. */
#ifndef GH_OUTPUTS_CONFIRMED
#define GH_OUTPUTS_CONFIRMED 0
#endif
#define GH_BAUD 115200u
#define GH_CLOCK 8000000u /* internal HSI: independent of unknown board crystal */
#define GH_OLED_ENABLED 1
#define GH_OLED_ADDRESS 0x3Cu
#define GH_OLED_HEIGHT 64u /* SSD1306 128x64 assumption; NOT hardware validated */
#define GH_MAX_FRAME 128u
#define GH_PUMP_MAX_MS 8000u
#define GH_PUMP_COOLDOWN_MS 12000u
#define GH_SWITCH_MIN_MS 4000u
#endif

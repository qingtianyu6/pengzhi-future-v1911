#ifndef GH_CONTROL_H
#define GH_CONTROL_H
#include <stdint.h>
#include "config.h"
typedef struct { uint32_t seq, hash; char kind[5]; uint8_t error; } gh_cache;
typedef struct {
    int32_t env[5];
    uint32_t last_set, lease, pump_since, pump_off, fan_changed, lamp_changed;
    uint8_t mask, manual, cache_index;
    gh_cache cache[8];
    struct { uint32_t at; uint8_t mask, reason; } logs[16];
    uint8_t log_index;
} gh_state;
void gh_init(gh_state *s, uint32_t now);
void gh_watchdog(gh_state *s, uint32_t now);
/* rx and tx are bounded to GH_MAX_FRAME; returns response size, or zero for corrupt frame. */
unsigned gh_process(gh_state *s, const char *rx, unsigned size, char *tx, uint32_t now);
#endif

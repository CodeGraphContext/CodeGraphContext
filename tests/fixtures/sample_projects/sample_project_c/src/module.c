#include "module.h"
#include "util.h"

static int s_secret = 42; // file-local static

void module_init(Mode m) {
    (void)m;
    s_secret = 42;
}

int module_compute(int base) {
#if ENABLE_STATS
    g_counter++;
#endif
    return clamp(base + s_secret, 0, 1000); // uses inline from util.h
}

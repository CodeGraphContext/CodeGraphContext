#ifndef UTIL_H
#define UTIL_H

#include <stddef.h>

extern int g_counter;          // extern variable
typedef struct { int x, y; } Point;
typedef int (*cmp_fn)(int, int); // function pointer typedef

int max_int(int a, int b);
static inline int clamp(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

#endif

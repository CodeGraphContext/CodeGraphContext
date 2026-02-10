#include <stdio.h>
#include "config.h"
#include "platform.h"
#include "util.h"
#include "math/vec.h"
#include "module.h"

static int cmp_desc(int a, int b) { return b - a; } // matches cmp_fn typedef shape

int main(void) {
    module_init(MODE_A);

    Point p = { .x = 3, .y = 4 };
    Vec3 v = {1,2,3}, w = {4,5,6};
    Vec3 sum = vec_add(v, w);

    int m = max_int(p.x, p.y);
    int r = module_compute(m);

#ifdef CGC_PLATFORM_WINDOWS
    printf("%s %s (win) r=%d sum=(%.0f,%.0f,%.0f)\n", APP_NAME, APP_VERSION, r, sum.x, sum.y, sum.z);
#else
    printf("%s %s (posix) r=%d sum=(%.0f,%.0f,%.0f)\n", APP_NAME, APP_VERSION, r, sum.x, sum.y, sum.z);
#endif

    // use function pointer typedef
    cmp_fn f = cmp_desc;
    return f(r, g_counter) < 0 ? 0 : 1;
}

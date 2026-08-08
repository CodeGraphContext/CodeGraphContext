#include <stdio.h>
#include "utils.h"

void process_entity(Entity* e, Callback cb) {
    printf("Processing entity %d: %s\n", e->id, e->name);
    if (cb) cb(e);
}

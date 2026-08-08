#include <stdio.h>
#include <string.h>
#include "utils.h"

void my_callback(Entity* e) {
    printf("Callback for %s executed.\n", e->name);
}

int main() {
    Entity e;
    e.id = 101;
    strcpy(e.name, "CGC-Entity");

    process_entity(&e, my_callback);
    return 0;
}

#ifndef UTILS_H
#define UTILS_H

typedef struct {
    int id;
    char name[50];
} Entity;

typedef void (*Callback)(Entity*);

void process_entity(Entity* e, Callback cb);

#endif

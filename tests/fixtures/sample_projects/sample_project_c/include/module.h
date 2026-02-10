#ifndef MODULE_H
#define MODULE_H
typedef enum { MODE_A=0, MODE_B=1 } Mode;
void module_init(Mode m);
int module_compute(int base);
#endif

#include <stdio.h>

/*
Tough Case 1: Macro-generated Function Definitions
Using the token pasting operator (##) to define functions.
A static indexer that doesn't expand macros will miss these definitions.
*/
#define DEFINE_HANDLER(name) \
    void handle_##name(int val) { \
        printf("Handler " #name " received %d\n", val); \
    }

DEFINE_HANDLER(input)
DEFINE_HANDLER(output)
DEFINE_HANDLER(error)

/*
Tough Case 2: Conditional Function Signatures
The number of arguments or the return type changes based on macros.
*/
#ifdef EXPERIMENTAL_MODE
int process_data(int x, int y, int z) {
    return x + y + z;
}
#else
int process_data(int x, int y) {
    return x + y;
}
#endif

/*
Tough Case 3: Function Pointer Indirection
Tracking calls through function pointers.
*/
typedef void (*callback_t)(int);

void my_callback(int x) {
    printf("Callback with %d\n", x);
}

void execute_callback(callback_t cb, int val) {
    cb(val); // This call should ideally link back to my_callback if tracked
}

/*
Tough Case 4: Variadic Macros and Functions
*/
#define LOG_MESSAGE(fmt, ...) printf("[LOG] " fmt "\n", ##__VA_ARGS__)

void test_variadic() {
    LOG_MESSAGE("Testing %d, %s", 1, "two");
}

/*
Tough Case 5: X-Macros (Code generation from lists)
This is a common pattern in low-level C (e.g., Linux kernel) to keep 
enums and string arrays in sync.
*/
#define COLOR_LIST \
    X(RED, "red") \
    X(GREEN, "green") \
    X(BLUE, "blue")

// Generate Enum
typedef enum {
#define X(name, str) COLOR_##name,
    COLOR_LIST
#undef X
} color_t;

// Generate String Array
const char* color_names[] = {
#define X(name, str) str,
    COLOR_LIST
#undef X
};

// Generate Switch Case Function
const char* get_color_name(color_t c) {
    switch(c) {
#define X(name, str) case COLOR_##name: return str;
/*
Tough Case 6: Recursive Macro Simulation (The "Impossible" Pattern)
C macros are not recursive, but can be made to "recurse" using multiple 
expansion passes (EVAL) and deferred tokens.
*/
#define EMPTY()
#define DEFER(id) id EMPTY()
#define OBSTRUCT(...) __VA_ARGS__ DEFER(EMPTY)()
#define EXPAND(...) __VA_ARGS__

#define EVAL(...)  EVAL1(EVAL1(EVAL1(__VA_ARGS__)))
#define EVAL1(...) EVAL2(EVAL2(EVAL2(__VA_ARGS__)))
#define EVAL2(...) EVAL3(EVAL3(EVAL3(__VA_ARGS__)))
#define EVAL3(...) __VA_ARGS__

#define RECURSE() RECURSE_INDIRECT
#define RECURSE_INDIRECT() RECURSE

// A macro that "counts down" by expanding itself multiple times
#define COUNTDOWN(n) \
    n \
    if (n > 0) { \
        OBSTRUCT(RECURSE)()(n - 1) \
    }

void test_recursion() {
    // This expands into a series of nested if-statements
    // It tests if the parser can handle deep macro expansion depth.
    EVAL(COUNTDOWN(3))
}

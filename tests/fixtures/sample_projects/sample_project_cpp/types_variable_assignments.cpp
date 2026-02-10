#include <iostream>
#include <string>
#include <vector>

// --- Demo class ---
class Demo {
public:
    int member;                  // non-static member
    static int static_member;     // static member
    const char* name = "Demo";

    void setMember(int value) { member = value; }
};

int Demo::static_member = 100;

// --- Point struct for structured bindings ---
struct Point {
    int x;
    int y;
};

// --- Global variable declarations ---
int global_int = 10;
double global_double(3.14);
std::string global_str = "Hello";
const int CONST_VAL = 42;
int *global_ptr = &global_int;
int global_arr[5] = {1, 2, 3, 4, 5};

// --- Function demonstrating variable declarations ---
void testVariables() {
    // Basic declarations
    int a = 5;
    float b = 2.5f;
    double c(9.81);
    bool flag = true;
    char ch = 'A';
    std::string s = "Tree-sitter";

    // Pointer and reference
    int x = 10;
    int *p = &x;
    int &ref = x;
    const int *const_ptr = &x;

    // Arrays
    int nums[3] = {1, 2, 3};
    char letters[] = {'a', 'b', 'c'};
    std::string words[2] = {"hello", "world"};

    // Vector and auto type
    std::vector<int> vec = {1, 2, 3, 4};
    auto val = vec[2];

    // Structured bindings (C++17)
    Point pt = {10, 20};
    auto [px, py] = pt;

    // Assignments and compound ops
    a = 10;
    a += 5;
    b *= 3.0f;
    c /= 2;
    flag = !flag;
    s += " test";
    x = a + b - c;

    // Expressions and function calls
    std::cout << "Sum: " << (a + b + c) << std::endl;

    // Dynamic allocation
    int *dyn = new int(99);
    delete dyn;

    // Static and const local variables
    static int counter = 0;
    const double PI = 3.14159;

    // Lambda with captured variable
    auto lambda = [=]() { return PI * a; };
    double result = lambda();

    // Object and member assignments
    Demo d;
    d.member = 50;
    d.setMember(25);
    Demo::static_member = 200;
}

int main() {
    testVariables();
    return 0;
}

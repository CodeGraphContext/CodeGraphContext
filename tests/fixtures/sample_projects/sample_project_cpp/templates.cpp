// Demonstrates templates and specialization
#include <iostream>

template<typename T>
T add(T a, T b) { return a + b; }

template<>
std::string add(std::string a, std::string b) { return a + " (specialized) " + b; }

void templateDemo() {
    std::cout << add(2, 3) << std::endl;
    std::cout << add(std::string("foo"), std::string("bar")) << std::endl;
}

// Demonstrates exception handling in C++
#include <iostream>
#include <stdexcept>

void exceptionDemo(int x) {
    try {
        if (x == 0) throw std::invalid_argument("zero");
        std::cout << 10 / x << std::endl;
    } catch (const std::invalid_argument& e) {
        std::cout << e.what() << std::endl;
    } catch (...) {
        std::cout << "Unknown error" << std::endl;
    }
}

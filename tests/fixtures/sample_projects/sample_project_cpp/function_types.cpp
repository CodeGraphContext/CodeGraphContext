#include <iostream>
#include <vector>
#include <algorithm>

// Regular function
int add(int a, int b) {
    return a + b;
}

// Templated function
template <typename T>
T multiply(T a, T b) {
    return a * b;
}

class Calculator {
public:
    // Static member function
    static int subtract(int a, int b) {
        return a - b;
    }

    // Method using a local lambda
    void printSum(const std::vector<int>& nums) {
        auto printer = [](int val) { std::cout << val << std::endl; };
        for (int n : nums) printer(n);
    }
};

int main() {
    Calculator calc;
    std::vector<int> numbers = {1, 2, 3};

    calc.printSum(numbers);

    // Standalone lambda
    auto lambda = [](int a, int b) { return a + b; };
    std::cout << "Lambda sum: " << lambda(3,4) << std::endl;

    // Regular function call
    std::cout << "Add: " << add(2,3) << std::endl;

    // Templated function call
    std::cout << "Multiply: " << multiply(2,3) << std::endl;

    // Static member function call
    std::cout << "Subtract: " << Calculator::subtract(5,2) << std::endl;

    return 0;
}

// Demonstrates function pointers and lambdas
#include <iostream>
#include <functional>

void callTwice(const std::function<void()>& f) {
    f(); f();
}

void functionChainDemo() {
    auto lambda = [](){ std::cout << "Hello from lambda\n"; };
    callTwice(lambda);
}

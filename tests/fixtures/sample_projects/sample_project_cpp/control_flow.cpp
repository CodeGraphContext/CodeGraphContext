// Demonstrates control flow constructs in C++
#include <iostream>

void controlFlow(int x) {
    if (x > 0) std::cout << "positive\n";
    else if (x == 0) std::cout << "zero\n";
    else std::cout << "negative\n";

    std::cout << ((x > 0) ? "pos" : "non-pos") << std::endl;

    for (int i = 0; i < 3; ++i) std::cout << i << ' ';
    std::cout << std::endl;
}

// ...existing code...

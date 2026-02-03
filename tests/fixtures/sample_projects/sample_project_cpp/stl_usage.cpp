// Demonstrates STL containers and algorithms
#include <iostream>
#include <vector>
#include <algorithm>

void stlDemo() {
    std::vector<int> v = {1, 2, 3};
    std::for_each(v.begin(), v.end(), [](int x){ std::cout << x << ' '; });
    std::cout << std::endl;
}

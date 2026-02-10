// Demonstrates file I/O in C++
#include <iostream>
#include <fstream>
#include "function_chain.h"


void fileIODemo() {
    std::ofstream out("out.txt");
    out << "Hello, file!" << std::endl;
    out.close();
    functionChainDemo();
    std::ifstream in("out.txt");
    std::string line;
    std::cout << line << std::endl;
}

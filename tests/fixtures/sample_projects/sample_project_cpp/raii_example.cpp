// Demonstrates RAII (Resource Acquisition Is Initialization)
#include <iostream>

class File {
public:
    File(const char* name) { std::cout << "Opening " << name << std::endl; }
    ~File() { std::cout << "Closing file" << std::endl; }
};

void raiiDemo() {
    File f("test.txt");
    std::cout << "Using file..." << std::endl;
}

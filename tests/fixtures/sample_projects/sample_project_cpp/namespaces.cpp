// Demonstrates namespaces and using directive
#include <iostream>

namespace foo {
    void bar() { std::cout << "foo::bar\n"; }
}

void namespaceDemo() {
    using namespace foo;
    bar();
}

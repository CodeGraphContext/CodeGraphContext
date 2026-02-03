#include <string>

// Tests for access specifiers
class AccessSpecifierTests {
public:
    AccessSpecifierTests() : publicData(10), protectedValue(20), privateData("default") {}

    void publicMethod() {/* ... */}

protected:
    int protectedValue;
    void protectedMethod() {/* ... */}

private:
    std::string privateData;
    void privateMethod() {/* ... */}

public:
    int publicData;
};

// Tests for constructors and destructors
class ConstructorDestructorTests {
public:
    ConstructorDestructorTests() : exampleData(100) {}
    ~ConstructorDestructorTests() {/* ... */}

    void exampleMethod() {/* ... */}

private:
    int exampleData;
};


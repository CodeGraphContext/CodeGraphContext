enum Color {
    RED = 0,
    GREEN = 1,
    BLUE = 2
};

enum class Direction {
    NORTH = 0,
    EAST = 1,
    SOUTH = 2,
    WEST = 3
};

struct MyStruct {
    int x = 5;
    float y = 3.14f;

    void doSomething();
};

void MyStruct::doSomething() {
    x += 1;
    y *= 2.0f;
}

union MyUnion {
    int intValue;
    float floatValue;
};

int main() {
    // enum
    Color color = RED;
    Direction dir = Direction::NORTH;

    // struct
    MyStruct s;
    s.doSomething();


    // union
    MyUnion u;
    u.intValue = 42;

    return 0;
}

// Demonstrates classes, inheritance, and polymorphism
#include <iostream>

class Animal {
public:
    virtual void speak() const { std::cout << "Animal sound\n"; }
    virtual ~Animal() = default;
};

class Dog : public Animal {
public:
    void speak() const override { std::cout << "Woof!\n"; }
};

void classDemo() {
    Animal* a = new Dog();
    a->speak();
    delete a;
}

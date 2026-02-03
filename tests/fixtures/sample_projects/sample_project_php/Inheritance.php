<?php
abstract class Animal {
    abstract public function sound();
}

class Dog extends Animal {
    public function sound() {
        return "Woof!";
    }
}

class Cat extends Animal {
    public function sound() {
        return "Meow!";
    }
}

$dog = new Dog();
$cat = new Cat();

echo $dog->sound() . "\n";
echo $cat->sound() . "\n";
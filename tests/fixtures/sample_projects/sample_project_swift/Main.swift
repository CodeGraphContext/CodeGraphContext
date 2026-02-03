import Foundation

// Main entry point
class Main {
    func run() {
        let user = User(name: "Shashank", age: 30)
        print(user.greet())
        
        let calculator = Calculator()
        print(calculator.add(a: 5, b: 10))
        
        let shape = Circle(radius: 5.0)
        print("Area: \(shape.area())")
    }
}

// Simple calculator class
class Calculator {
    func add(a: Int, b: Int) -> Int {
        return a + b
    }
    
    func subtract(a: Int, b: Int) -> Int {
        return a - b
    }
    
    func multiply(a: Int, b: Int) -> Int {
        return a * b
    }
}

// Entry point
let main = Main()
main.run()

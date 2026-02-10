import Foundation

// Protocol for greeting
protocol Greeter {
    func greet() -> String
}

// User struct conforming to Greeter protocol
struct User: Greeter {
    let name: String
    let age: Int
    
    func greet() -> String {
        return "Hello, my name is \(name) and I am \(age) years old."
    }
    
    func isAdult() -> Bool {
        return age >= 18
    }
}

// Extension to add additional functionality
extension User {
    func birthYear(currentYear: Int) -> Int {
        return currentYear - age
    }
}

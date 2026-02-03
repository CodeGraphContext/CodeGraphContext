import Foundation

// Protocol for shapes
protocol Shape {
    func area() -> Double
    func perimeter() -> Double
}

// Circle class implementing Shape
class Circle: Shape {
    let radius: Double
    
    init(radius: Double) {
        self.radius = radius
    }
    
    func area() -> Double {
        return Double.pi * radius * radius
    }
    
    func perimeter() -> Double {
        return 2 * Double.pi * radius
    }
}

// Rectangle struct implementing Shape
struct Rectangle: Shape {
    let width: Double
    let height: Double
    
    func area() -> Double {
        return width * height
    }
    
    func perimeter() -> Double {
        return 2 * (width + height)
    }
    
    func isSquare() -> Bool {
        return width == height
    }
}

// Triangle class implementing Shape
class Triangle: Shape {
    let base: Double
    let height: Double
    let sideA: Double
    let sideB: Double
    
    init(base: Double, height: Double, sideA: Double, sideB: Double) {
        self.base = base
        self.height = height
        self.sideA = sideA
        self.sideB = sideB
    }
    
    func area() -> Double {
        return 0.5 * base * height
    }
    
    func perimeter() -> Double {
        return base + sideA + sideB
    }
}

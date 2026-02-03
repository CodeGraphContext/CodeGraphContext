import Foundation

// Enum for different types of vehicles
enum VehicleType {
    case car
    case truck
    case motorcycle
    case bicycle
    
    func description() -> String {
        switch self {
        case .car:
            return "Four-wheeled vehicle"
        case .truck:
            return "Large cargo vehicle"
        case .motorcycle:
            return "Two-wheeled motorized vehicle"
        case .bicycle:
            return "Two-wheeled pedal vehicle"
        }
    }
}

// Enum with associated values
enum Result<T> {
    case success(T)
    case failure(Error)
    
    func getValue() -> T? {
        switch self {
        case .success(let value):
            return value
        case .failure:
            return nil
        }
    }
}

// Vehicle class
class Vehicle {
    let type: VehicleType
    var speed: Double
    
    init(type: VehicleType, speed: Double = 0.0) {
        self.type = type
        self.speed = speed
    }
    
    func accelerate(by amount: Double) {
        speed += amount
    }
    
    func brake(by amount: Double) {
        speed = max(0, speed - amount)
    }
    
    func getInfo() -> String {
        return "\(type.description()) traveling at \(speed) km/h"
    }
}

// Car class inheriting from Vehicle
class Car: Vehicle {
    let numberOfDoors: Int
    
    init(numberOfDoors: Int, speed: Double = 0.0) {
        self.numberOfDoors = numberOfDoors
        super.init(type: .car, speed: speed)
    }
    
    override func getInfo() -> String {
        return "\(numberOfDoors)-door car traveling at \(speed) km/h"
    }
}

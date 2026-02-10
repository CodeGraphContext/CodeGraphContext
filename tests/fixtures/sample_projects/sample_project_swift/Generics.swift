import Foundation

// Generic data structure
class Stack<T> {
    private var items: [T] = []
    
    func push(_ item: T) {
        items.append(item)
    }
    
    func pop() -> T? {
        return items.isEmpty ? nil : items.removeLast()
    }
    
    func peek() -> T? {
        return items.last
    }
    
    var count: Int {
        return items.count
    }
    
    var isEmpty: Bool {
        return items.isEmpty
    }
}

// Generic function
func swap<T>(_ a: inout T, _ b: inout T) {
    let temp = a
    a = b
    b = temp
}

// Protocol with associated type
protocol Container {
    associatedtype Item
    mutating func append(_ item: Item)
    var count: Int { get }
    subscript(i: Int) -> Item { get }
}

// Array extension conforming to Container
extension Array: Container {
    // Array already has append, count, and subscript
}

// Custom collection
struct IntCollection: Container {
    typealias Item = Int
    
    private var items: [Int] = []
    
    mutating func append(_ item: Int) {
        items.append(item)
    }
    
    var count: Int {
        return items.count
    }
    
    subscript(i: Int) -> Int {
        return items[i]
    }
}

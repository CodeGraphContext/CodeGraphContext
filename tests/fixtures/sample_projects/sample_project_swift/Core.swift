protocol Named {
    var name: String { get }
}

extension Named {
    func describe() -> String {
        return "My name is \(name)"
    }
}

struct Robot: Named {
    let name: String
    let model: String
}

class Supervisor<T: Named> {
    func announce(item: T) {
        print("Announcing: \(item.describe())")
    }
}

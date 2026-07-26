import Foundation

/**
 * Tough Case 1: Protocol Extensions with Default Implementations
 * This is a major source of missed relationships in Swift.
 */
protocol Workable {
    func doWork()
}

extension Workable {
    func doWork() {
        print("Default work implementation")
    }
    
    func extraHelp() {
        print("Helper available to all workers")
    }
}

class Manager: Workable {
    // Uses default implementation of doWork
}

class Developer: Workable {
    func doWork() {
        print("Developer coding...")
    }
}

func testProtocols() {
    let m = Manager()
    let d = Developer()
    
    m.doWork() // Should link to extension default
    d.doWork() // Should link to class override
    m.extraHelp() // Should link to extension helper
}

/**
 * Tough Case 2: Closures and Capture Lists
 */
class Controller {
    var title = "Main"
    
    func performAction() {
        let closure = { [weak self] in
            guard let self = self else { return }
            print("Action in \(self.title)")
        }
        closure()
    }
}

/**
 * Tough Case 3: Property Wrappers
 */
@propertyWrapper
struct Trimmed {
    private var value: String = ""
    var wrappedValue: String {
        get { value }
        set { value = newValue.trimmingCharacters(in: .whitespacesAndNewlines) }
    }
    
    init(wrappedValue: String) {
        self.wrappedValue = wrappedValue
    }
}

struct Profile {
    @Trimmed var username: String
}

/**
 * Tough Case 4: Opaque Return Types (some keyword)
 */
func getShape() -> some Equatable {
    return "Circle"
}

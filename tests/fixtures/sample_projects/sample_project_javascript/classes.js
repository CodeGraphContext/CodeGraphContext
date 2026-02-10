/**
 * Sample JavaScript file demonstrating class definitions and methods
 * This file tests class declarations, methods, static methods, and inheritance
 */

// Basic class declaration
class Person {
    constructor(name, age) {
        this.name = name;
        this.age = age;
    }

    // Instance method
    greet() {
        return `Hello, I'm ${this.name} and I'm ${this.age} years old`;
    }

    /**
     * Method with JSDoc documentation
     * @param {number} years - Number of years to add
     * @returns {void}
     */
    celebrateBirthday(years = 1) {
        this.age += years;
        console.log(`Happy birthday! Now ${this.age} years old`);
    }

    // Getter method
    get info() {
        return `${this.name} (${this.age})`;
    }

    // Setter method
    set info(value) {
        const [name, age] = value.split(' ');
        this.name = name;
        this.age = parseInt(age);
    }

    // Static method
    static createAdult(name) {
        return new Person(name, 18);
    }

    // Static method with parameters
    static compare(person1, person2) {
        return person1.age - person2.age;
    }
}

// Class inheritance
class Employee extends Person {
    constructor(name, age, jobTitle, salary) {
        super(name, age);
        this.jobTitle = jobTitle;
        this.salary = salary;
    }

    // Override parent method
    greet() {
        return `${super.greet()}. I work as a ${this.jobTitle}`;
    }

    // New method specific to Employee
    work() {
        console.log(`${this.name} is working as a ${this.jobTitle}`);
    }

    // Method with complex parameters
    updateSalary(newSalary, reason = 'performance review') {
        const oldSalary = this.salary;
        this.salary = newSalary;
        console.log(`Salary updated from ${oldSalary} to ${newSalary} due to ${reason}`);
    }

    // Static method in child class
    static createIntern(name, age) {
        return new Employee(name, age, 'Intern', 0);
    }
}

// Class with private fields (modern JavaScript)
class BankAccount {
    #balance = 0;
    #accountNumber;

    constructor(accountNumber, initialBalance = 0) {
        this.#accountNumber = accountNumber;
        this.#balance = initialBalance;
    }

    // Public method accessing private field
    deposit(amount) {
        if (amount > 0) {
            this.#balance += amount;
            return this.#balance;
        }
        throw new Error('Amount must be positive');
    }

    // Public method accessing private field
    withdraw(amount) {
        if (amount > 0 && amount <= this.#balance) {
            this.#balance -= amount;
            return this.#balance;
        }
        throw new Error('Invalid withdrawal amount');
    }

    // Getter for private field
    get balance() {
        return this.#balance;
    }

    // Private method
    #validateTransaction(amount) {
        return amount > 0 && amount <= this.#balance;
    }
}

// Class with static properties and methods
class MathUtils {
    static PI = 3.14159;
    static E = 2.71828;

    static add(a, b) {
        return a + b;
    }

    static multiply(a, b) {
        return a * b;
    }

    static circleArea(radius) {
        return MathUtils.PI * radius * radius;
    }
}

// Class expression assigned to variable
const AnonymousClass = class {
    constructor(value) {
        this.value = value;
    }

    getValue() {
        return this.value;
    }
};

// Mixin pattern using classes
const Flyable = (Base) => class extends Base {
    fly() {
        console.log(`${this.name} is flying!`);
    }
};

const Swimmable = (Base) => class extends Base {
    swim() {
        console.log(`${this.name} is swimming!`);
    }
};

// Class using mixins
class Duck extends Swimmable(Flyable(Person)) {
    constructor(name) {
        super(name, 0); // Ducks don't have human age
        this.species = 'Duck';
    }

    quack() {
        console.log(`${this.name} says: Quack!`);
    }
}

// Function that creates and uses class instances
function demonstrateClasses() {
    const person = new Person('Alice', 30);
    const employee = new Employee('Bob', 25, 'Developer', 75000);
    const account = new BankAccount('12345', 1000);
    const duck = new Duck('Donald');

    // Call various methods
    console.log(person.greet());
    console.log(employee.greet());
    employee.work();
    
    account.deposit(500);
    console.log('Balance:', account.balance);
    
    duck.quack();
    duck.fly();
    duck.swim();

    return {
        person,
        employee,
        account,
        duck
    };
}

// Export classes
export { Person, Employee, BankAccount, MathUtils, Duck };
export default demonstrateClasses;


/**
 * Classes and Inheritance
 * Demonstrates TypeScript's OOP features including classes, inheritance,
 * abstract classes, access modifiers, static members, and advanced patterns
 */

// ========== Basic Class Definition ==========
export class Person {
  // Public property (default)
  public name: string;
  
  // Private property (only accessible within this class)
  private _id: number;
  
  // Protected property (accessible in this class and subclasses)
  protected age: number;
  
  // Readonly property
  readonly birthDate: Date;
  
  // Static property
  static species: string = "Homo sapiens";
  
  // Static method
  static getSpecies(): string {
    return Person.species;
  }

  constructor(name: string, age: number, id: number) {
    this.name = name;
    this.age = age;
    this._id = id;
    this.birthDate = new Date();
  }

  // Public method
  public introduce(): string {
    return `Hello, I'm ${this.name} and I'm ${this.age} years old.`;
  }

  // Private method
  private validateAge(age: number): boolean {
    return age >= 0 && age <= 150;
  }

  // Protected method
  protected updateAge(newAge: number): void {
    if (this.validateAge(newAge)) {
      this.age = newAge;
    }
  }

  // Getter
  get id(): number {
    return this._id;
  }

  // Setter
  set id(value: number) {
    if (value > 0) {
      this._id = value;
    }
  }

  // Method with overloads
  greet(): string;
  greet(formal: boolean): string;
  greet(formal: boolean, title: string): string;
  greet(formal?: boolean, title?: string): string {
    const greeting = formal ? "Good day" : "Hi";
    const nameWithTitle = title ? `${title} ${this.name}` : this.name;
    return `${greeting}, ${nameWithTitle}!`;
  }
}

// ========== Inheritance ==========
export class Employee extends Person {
  private salary: number;
  public department: string;
  
  constructor(name: string, age: number, id: number, department: string, salary: number) {
    super(name, age, id); // Call parent constructor
    this.department = department;
    this.salary = salary;
  }

  // Override parent method
  public override introduce(): string {
    return `${super.introduce()} I work in ${this.department}.`;
  }

  // New method specific to Employee
  public work(): string {
    return `${this.name} is working in the ${this.department} department.`;
  }

  // Access protected member from parent
  public celebrateBirthday(): void {
    this.updateAge(this.age + 1);
    console.log(`Happy birthday! Now ${this.age} years old.`);
  }

  // Getter for private property
  get monthlySalary(): number {
    return this.salary;
  }

  // Setter with validation
  set monthlySalary(value: number) {
    if (value >= 0) {
      this.salary = value;
    } else {
      throw new Error("Salary cannot be negative");
    }
  }
}

// ========== Abstract Classes ==========
export abstract class Animal {
  protected name: string;
  protected age: number;
  
  constructor(name: string, age: number) {
    this.name = name;
    this.age = age;
  }

  // Concrete method
  public sleep(): string {
    return `${this.name} is sleeping.`;
  }

  // Abstract method (must be implemented by subclasses)
  abstract makeSound(): string;
  
  // Abstract method with parameters
  abstract move(distance: number): string;
}

// ========== Concrete Implementation of Abstract Class ==========
export class Dog extends Animal {
  private breed: string;
  
  constructor(name: string, age: number, breed: string) {
    super(name, age);
    this.breed = breed;
  }

  // Implementation of abstract method
  public makeSound(): string {
    return `${this.name} the ${this.breed} says: Woof! Woof!`;
  }

  // Implementation of abstract method
  public move(distance: number): string {
    return `${this.name} runs ${distance} meters.`;
  }

  // Additional method specific to Dog
  public fetch(): string {
    return `${this.name} fetches the ball!`;
  }
}

export class Cat extends Animal {
  private indoor: boolean;
  
  constructor(name: string, age: number, indoor: boolean = true) {
    super(name, age);
    this.indoor = indoor;
  }

  public makeSound(): string {
    return `${this.name} says: Meow!`;
  }

  public move(distance: number): string {
    const verb = this.indoor ? "walks" : "prowls";
    return `${this.name} ${verb} ${distance} meters.`;
  }

  public climb(): string {
    return `${this.name} climbs up high.`;
  }
}

// ========== Interface Implementation ==========
interface Flyable {
  fly(height: number): string;
  land(): string;
}

interface Swimmable {
  swim(depth: number): string;
  surface(): string;
}

export class Duck extends Animal implements Flyable, Swimmable {
  constructor(name: string, age: number) {
    super(name, age);
  }

  public makeSound(): string {
    return `${this.name} says: Quack! Quack!`;
  }

  public move(distance: number): string {
    return `${this.name} waddles ${distance} meters.`;
  }

  // Implement Flyable
  public fly(height: number): string {
    return `${this.name} flies at ${height} meters high.`;
  }

  public land(): string {
    return `${this.name} lands gracefully.`;
  }

  // Implement Swimmable
  public swim(depth: number): string {
    return `${this.name} swims at ${depth} meters deep.`;
  }

  public surface(): string {
    return `${this.name} surfaces from the water.`;
  }
}

// ========== Generic Classes ==========
export class Container<T> {
  private items: T[] = [];

  public add(item: T): void {
    this.items.push(item);
  }

  public remove(item: T): boolean {
    const index = this.items.indexOf(item);
    if (index > -1) {
      this.items.splice(index, 1);
      return true;
    }
    return false;
  }

  public getAll(): readonly T[] {
    return [...this.items];
  }

  public size(): number {
    return this.items.length;
  }

  public clear(): void {
    this.items = [];
  }
}

// Generic class with constraints
export class NumberContainer<T extends number> extends Container<T> {
  public sum(): T {
    return this.getAll().reduce((sum, item) => (sum + item) as T, 0 as T);
  }

  public average(): number {
    const items = this.getAll();
    return items.length > 0 ? this.sum() / items.length : 0;
  }
}

// ========== Singleton Pattern ==========
export class Database {
  private static instance: Database;
  private connections: number = 0;

  private constructor() {
    // Private constructor prevents instantiation
  }

  public static getInstance(): Database {
    if (!Database.instance) {
      Database.instance = new Database();
    }
    return Database.instance;
  }

  public connect(): string {
    this.connections++;
    return `Connected to database. Total connections: ${this.connections}`;
  }

  public disconnect(): string {
    if (this.connections > 0) {
      this.connections--;
      return `Disconnected from database. Remaining connections: ${this.connections}`;
    }
    return "No active connections to disconnect.";
  }
}

// ========== Static Class Pattern ==========
export class MathUtils {
  // Prevent instantiation
  private constructor() {}

  public static PI: number = Math.PI;
  
  public static calculateCircleArea(radius: number): number {
    return MathUtils.PI * radius * radius;
  }

  public static calculateDistance(x1: number, y1: number, x2: number, y2: number): number {
    return Math.sqrt(Math.pow(x2 - x1, 2) + Math.pow(y2 - y1, 2));
  }

  public static clamp(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), max);
  }
}

// ========== Mixins Pattern ==========
type Constructor<T = {}> = new (...args: any[]) => T;

// Mixin function
export function Timestamped<TBase extends Constructor>(Base: TBase) {
  return class extends Base {
    timestamp = Date.now();
    
    getTimestamp(): number {
      return this.timestamp;
    }
  };
}

export function Activatable<TBase extends Constructor>(Base: TBase) {
  return class extends Base {
    isActive = false;
    
    activate(): void {
      this.isActive = true;
    }
    
    deactivate(): void {
      this.isActive = false;
    }
  };
}

// Base class for mixins
export class BaseUser {
  constructor(public name: string) {}
}

// Apply mixins
export const TimestampedUser = Timestamped(BaseUser);
export const ActivatableUser = Activatable(BaseUser);
export const EnhancedUser = Timestamped(Activatable(BaseUser));

// ========== Usage Examples ==========
export const classExamples = {
  // Basic usage
  person: new Person("John Doe", 30, 123),
  employee: new Employee("Jane Smith", 28, 456, "Engineering", 75000),
  
  // Animals
  dog: new Dog("Buddy", 3, "Golden Retriever"),
  cat: new Cat("Whiskers", 2, true),
  duck: new Duck("Quackers", 1),
  
  // Generic containers
  stringContainer: new Container<string>(),
  numberContainer: new NumberContainer<number>(),
  
  // Singleton
  database: Database.getInstance(),
  
  // Mixins
  timestampedUser: new TimestampedUser("Alice"),
  enhancedUser: new EnhancedUser("Bob")
};

// Initialize some examples
classExamples.stringContainer.add("Hello");
classExamples.stringContainer.add("World");

classExamples.numberContainer.add(10);
classExamples.numberContainer.add(20);
classExamples.numberContainer.add(30);
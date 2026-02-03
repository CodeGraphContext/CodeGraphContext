/**
 * Main Entry Point
 * Imports and demonstrates usage of all TypeScript modules in the sample project
 * This file serves as the primary entry point and integration test for all features
 */

// Import all modules to demonstrate the complete TypeScript feature set
import * as TypesInterfaces from './types-interfaces';
import * as ClassesInheritance from './classes-inheritance';
import * as FunctionsGenerics from './functions-generics';
import * as AsyncPromises from './async-promises';
import * as DecoratorsMetadata from './decorators-metadata';
import * as ModulesNamespaces from './modules-namespaces';
import * as AdvancedTypes from './advanced-types';
import * as ErrorValidation from './error-validation';
import * as UtilitiesHelpers from './utilities-helpers';

// Import specific examples for demonstration
import { User, Shape, calculateArea } from './types-interfaces';
import { Person, Employee, Dog } from './classes-inheritance';
import { Stack, Queue, memoize } from './functions-generics';
import { EventEmitter, PromisePool } from './async-promises';
import { ValidationError, Result, Ok, Err } from './error-validation';
import { StringUtils, ArrayUtils, ObjectUtils } from './utilities-helpers';

/**
 * Main application class demonstrating all TypeScript features
 */
export class TypeScriptShowcase {
  private eventEmitter = new EventEmitter<{ action: string; data: any }>();
  private promisePool = new PromisePool(5);
  private userCache = new Map<number, User>();

  constructor() {
    this.initializeEventHandlers();
    console.log('TypeScript Showcase initialized');
  }

  /**
   * Demonstrates basic types and interfaces
   */
  public demonstrateBasicTypes(): void {
    console.log('\n=== Demonstrating Basic Types ===');
    
    // Create a user with proper typing
    const user: User = {
      id: 1,
      name: "Alice Johnson",
      email: "alice@example.com",
      createdAt: new Date(),
      preferences: {
        theme: "dark",
        notifications: true,
        language: "en"
      }
    };

    // Demonstrate shape calculation with discriminated unions
    const shapes: Shape[] = [
      { kind: "circle", radius: 5 },
      { kind: "rectangle", width: 10, height: 6 },
      { kind: "triangle", base: 8, height: 4 }
    ];

    const areas = shapes.map(calculateArea);
    console.log('User:', user.name, user.email);
    console.log('Shape areas:', areas);

    // Cache the user
    this.userCache.set(user.id, user);
  }

  /**
   * Demonstrates classes and inheritance
   */
  public demonstrateClassesInheritance(): void {
    console.log('\n=== Demonstrating Classes & Inheritance ===');

    // Create instances of different classes
    const person = new Person("John Doe", 30, 123);
    const employee = new Employee("Jane Smith", 28, 456, "Engineering", 75000);
    const dog = new Dog("Buddy", 3, "Golden Retriever");

    console.log(person.introduce());
    console.log(employee.introduce()); // Uses overridden method
    console.log(employee.work());
    console.log(dog.makeSound());
    console.log(dog.move(10));

    // Demonstrate polymorphism
    const animals = [dog];
    animals.forEach(animal => {
      console.log(animal.sleep()); // Inherited method
    });

    // Use static methods
    console.log('Species:', Person.getSpecies());
  }

  /**
   * Demonstrates functions and generics
   */
  public demonstrateFunctionsGenerics(): void {
    console.log('\n=== Demonstrating Functions & Generics ===');

    // Generic data structures
    const stringStack = new Stack<string>();
    const numberQueue = new Queue<number>();

    stringStack.push("Hello");
    stringStack.push("World");
    numberQueue.enqueue(1);
    numberQueue.enqueue(2);
    numberQueue.enqueue(3);

    console.log('Stack peek:', stringStack.peek());
    console.log('Queue dequeue:', numberQueue.dequeue());
    console.log('Queue size:', numberQueue.size());

    // Memoized function
    const memoizedFib = memoize((n: number): number => {
      if (n <= 1) return n;
      return memoizedFib(n - 1) + memoizedFib(n - 2);
    });

    console.log('Fibonacci(10):', memoizedFib(10));
  }

  /**
   * Demonstrates async programming patterns
   */
  public async demonstrateAsyncPatterns(): Promise<void> {
    console.log('\n=== Demonstrating Async Patterns ===');

    // Event emitter example
    this.eventEmitter.emit({ action: 'user_login', data: { userId: 1 } });

    // Promise pool example
    const tasks = Array.from({ length: 10 }, (_, i) => 
      () => this.simulateAsyncTask(`Task ${i + 1}`)
    );

    tasks.forEach(task => this.promisePool.add(task));
    const results = await this.promisePool.execute();
    
    console.log(`Completed ${results.results.length} tasks, ${results.errors.length} errors`);

    // Async generator example
    console.log('Processing async stream:');
    for await (const item of this.asyncGenerator(3)) {
      console.log('  Generated:', item);
    }
  }

  /**
   * Demonstrates error handling and validation
   */
  public demonstrateErrorHandling(): void {
    console.log('\n=== Demonstrating Error Handling ===');

    // Result pattern example
    const validationResult = this.validateUserData({
      id: "123",
      name: "John Doe",
      email: "john@example.com",
      age: "30"
    });

    if (validationResult.success) {
      console.log('Validation succeeded:', validationResult.data.name);
    } else {
      console.log('Validation failed:', validationResult.error.map(e => e.message));
    }

    // Error handling with custom errors
    try {
      this.riskyOperation();
    } catch (error) {
      if (error instanceof ValidationError) {
        console.log('Caught validation error:', error.message);
      }
    }
  }

  /**
   * Demonstrates utility functions
   */
  public demonstrateUtilities(): void {
    console.log('\n=== Demonstrating Utilities ===');

    // String utilities
    const camelCased = StringUtils.camelCase("hello-world-example");
    const kebabCased = StringUtils.kebabCase("HelloWorldExample");
    console.log('CamelCase:', camelCased);
    console.log('KebabCase:', kebabCased);

    // Array utilities
    const chunked = ArrayUtils.chunk([1, 2, 3, 4, 5, 6, 7], 3);
    const unique = ArrayUtils.unique([1, 2, 2, 3, 3, 3, 4]);
    console.log('Chunked:', chunked);
    console.log('Unique:', unique);

    // Object utilities
    const deepValue = ObjectUtils.get(
      { user: { profile: { name: 'Deep Value' } } },
      'user.profile.name'
    );
    console.log('Deep value:', deepValue);

    // Grouped data
    const grouped = ArrayUtils.groupBy(
      [
        { type: 'fruit', name: 'apple' },
        { type: 'fruit', name: 'banana' },
        { type: 'vegetable', name: 'carrot' }
      ],
      item => item.type
    );
    console.log('Grouped:', grouped);
  }

  /**
   * Demonstrates advanced types
   */
  public demonstrateAdvancedTypes(): void {
    console.log('\n=== Demonstrating Advanced Types ===');

    // Using advanced type utilities
    const userPaths: AdvancedTypes.Paths<User>[] = [
      "name",
      "email",
      "preferences.theme",
      "preferences.notifications"
    ];

    console.log('Available user paths:', userPaths);

    // Branded types example
    const userId = AdvancedTypes.createUserId(123);
    const email = AdvancedTypes.createEmail("user@example.com");
    
    console.log('Branded types created:', { userId, email });

    // Template literal types
    const apiUrl: AdvancedTypes.ApiUrl<"users", "GET"> = "GET /api/users";
    console.log('API URL:', apiUrl);
  }

  /**
   * Demonstrates decorator usage (if decorators are enabled)
   */
  public demonstrateDecorators(): void {
    console.log('\n=== Demonstrating Decorators ===');

    // Create decorated user instance
    const decoratedUser = new DecoratorsMetadata.User(1, "decorated_user", "user@example.com", 25);
    decoratedUser.currentUserRole = "admin";

    // This will use caching decorator
    console.log('User info (cached):', decoratedUser.getInfo());
    console.log('User info (from cache):', decoratedUser.getInfo());

    // This will use validation decorator
    try {
      decoratedUser.updateAge(30);
      console.log('Age updated successfully');
    } catch (error) {
      console.log('Age update failed:', error);
    }
  }

  /**
   * Demonstrates module and namespace usage
   */
  public demonstrateModulesNamespaces(): void {
    console.log('\n=== Demonstrating Modules & Namespaces ===');

    // Using namespace utilities
    const vector2D = new ModulesNamespaces.MathUtils.Vector2D(3, 4);
    const magnitude = vector2D.magnitude();
    console.log(`Vector magnitude: ${magnitude}`);

    // Using nested namespaces
    const binaryTree = new ModulesNamespaces.DataStructures.Trees.BinaryTree<number>();
    binaryTree.insert(5);
    binaryTree.insert(3);
    binaryTree.insert(7);
    console.log('Binary tree created and populated');

    // Constants from nested namespace
    console.log('Golden ratio:', ModulesNamespaces.MathUtils.Constants.GOLDEN_RATIO);
  }

  /**
   * Runs all demonstrations
   */
  public async runAllDemonstrations(): Promise<void> {
    console.log('🚀 Starting TypeScript Feature Showcase\n');

    try {
      this.demonstrateBasicTypes();
      this.demonstrateClassesInheritance();
      this.demonstrateFunctionsGenerics();
      await this.demonstrateAsyncPatterns();
      this.demonstrateErrorHandling();
      this.demonstrateUtilities();
      this.demonstrateAdvancedTypes();
      this.demonstrateDecorators();
      this.demonstrateModulesNamespaces();

      console.log('\n✅ All TypeScript features demonstrated successfully!');
    } catch (error) {
      console.error('❌ Error during demonstration:', error);
    }
  }

  // Private helper methods
  private initializeEventHandlers(): void {
    this.eventEmitter.subscribe((event) => {
      console.log(`Event: ${event.action}`, event.data);
    });
  }

  private async simulateAsyncTask(name: string): Promise<string> {
    await new Promise(resolve => setTimeout(resolve, Math.random() * 100));
    return `${name} completed`;
  }

  private async* asyncGenerator(count: number): AsyncGenerator<string> {
    for (let i = 0; i < count; i++) {
      await new Promise(resolve => setTimeout(resolve, 50));
      yield `Item ${i + 1}`;
    }
  }

  private validateUserData(data: any): Result<any, ValidationError[]> {
    // Simple validation for demonstration
    const errors: ValidationError[] = [];
    
    if (!data.name || data.name.length < 2) {
      errors.push(new ValidationError("Name must be at least 2 characters", "name", data.name));
    }
    
    if (!data.email || !data.email.includes('@')) {
      errors.push(new ValidationError("Invalid email format", "email", data.email));
    }

    return errors.length === 0 ? Ok(data) : Err(errors);
  }

  private riskyOperation(): void {
    // Simulate a risky operation that might throw
    if (Math.random() > 0.5) {
      throw new ValidationError("Random validation failure");
    }
  }
}

// Main execution
async function main(): Promise<void> {
  const showcase = new TypeScriptShowcase();
  await showcase.runAllDemonstrations();

  // Additional integration examples
  console.log('\n=== Integration Examples ===');

  // Complex type usage
  type UserUpdate = AdvancedTypes.DeepPartial<User>;
  const userUpdate: UserUpdate = {
    preferences: {
      theme: "light"
    }
  };
  console.log('User update:', userUpdate);

  // Utility function chaining
  const processedText = StringUtils.camelCase(
    StringUtils.truncate("hello-world-example-text", 15)
  );
  console.log('Processed text:', processedText);

  // Error handling with utilities
  const parseResult = ErrorValidation.safeParseInt("42");
  if (ErrorValidation.isOk(parseResult)) {
    console.log('Parsed number:', parseResult.data);
  }
}

// Export everything for external usage
export * from './types-interfaces';
export * from './classes-inheritance';
export * from './functions-generics';
export * from './async-promises';
export * from './decorators-metadata';
export * from './modules-namespaces';
export * from './advanced-types';
export * from './error-validation';
export * from './utilities-helpers';

// Run the main function if this is the entry point
if (require.main === module) {
  main().catch(console.error);
}

export default TypeScriptShowcase;
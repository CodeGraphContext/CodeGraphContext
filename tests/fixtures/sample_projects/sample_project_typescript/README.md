# TypeScript Sample Project

A comprehensive TypeScript sample project for testing code analysis and indexing tools. This project covers major TypeScript language features, patterns, and best practices across approximately 10 files.

## Project Overview

This sample project is designed to demonstrate and test TypeScript's capabilities for:
- Code analysis tools
- Code indexing systems
- Graph database population
- Understanding TypeScript language features
- Reference implementation for TypeScript patterns

## Files Overview

### 1. `src/types-interfaces.ts`
Demonstrates TypeScript's core type system including:
- ✅ **Primitive Types**: string, number, boolean, null, undefined, symbol, bigint
- ✅ **Array and Tuple Types**: typed arrays, named tuples, readonly arrays
- ✅ **Object Types**: inline object types, optional properties
- ✅ **Interface Definitions**: basic interfaces, inheritance, index signatures
- ✅ **Type Aliases**: union types, intersection types, generic aliases
- ✅ **Union Types**: discriminated unions, type guards, exhaustive checks
- ✅ **Intersection Types**: combining types, complex compositions
- ✅ **Conditional Types**: type-level conditionals, infer keyword
- ✅ **Template Literal Types**: string manipulation at type level
- ✅ **Utility Types**: Pick, Omit, Partial, Required, etc.

### 2. `src/classes-inheritance.ts`
Covers object-oriented programming features:
- ✅ **Basic Classes**: constructors, properties, methods
- ✅ **Access Modifiers**: public, private, protected, readonly
- ✅ **Static Members**: static properties and methods
- ✅ **Inheritance**: extends keyword, super calls, method overriding
- ✅ **Abstract Classes**: abstract methods and properties
- ✅ **Interface Implementation**: implementing multiple interfaces
- ✅ **Generic Classes**: class-level generics, constraints
- ✅ **Design Patterns**: Singleton, Factory, Mixin patterns
- ✅ **Getters and Setters**: property accessors
- ✅ **Method Overloads**: multiple function signatures

### 3. `src/functions-generics.ts`
Explores function types and generic programming:
- ✅ **Function Types**: basic functions, arrow functions, optional parameters
- ✅ **Function Overloads**: multiple signatures for same function
- ✅ **Generic Functions**: type parameters, constraints, inference
- ✅ **Higher-Order Functions**: functions returning functions
- ✅ **Utility Functions**: memoization, debouncing, throttling
- ✅ **Generic Constraints**: extends keyword, keyof operator
- ✅ **Generic Data Structures**: Stack, Queue, PriorityQueue
- ✅ **Function Composition**: pipe, compose patterns
- ✅ **Currying**: partial application, function currying

### 4. `src/async-promises.ts`
Demonstrates asynchronous programming patterns:
- ✅ **Promises**: creating, chaining, error handling
- ✅ **Async/Await**: modern async syntax, error handling
- ✅ **Promise Combinators**: Promise.all, Promise.race, custom combinators
- ✅ **Async Iterators**: async generators, for-await-of
- ✅ **Observable Patterns**: EventEmitter, subscription management
- ✅ **Concurrency Control**: Promise pools, semaphores, rate limiting
- ✅ **Async Cache**: TTL-based caching, async operations
- ✅ **Error Handling**: retry patterns, timeout handling
- ✅ **Stream Processing**: batch processing, async pipelines

### 5. `src/decorators-metadata.ts`
Showcases TypeScript decorator system:
- ✅ **Class Decorators**: @Entity, @Injectable, @Component
- ✅ **Method Decorators**: @Log, @Cache, @Validate, @Retry
- ✅ **Property Decorators**: @Column, @Required, @SerializableProperty
- ✅ **Parameter Decorators**: @Inject, @ValidateParam
- ✅ **Metadata Reflection**: using reflect-metadata
- ✅ **Decorator Factories**: parameterized decorators
- ✅ **Custom Decorators**: role-based access, validation
- ✅ **Metadata Readers**: utility classes for metadata access

### 6. `src/modules-namespaces.ts`
Covers module system and organization:
- ✅ **Basic Exports**: named exports, default exports, re-exports
- ✅ **Namespace Declarations**: nested namespaces, namespace merging
- ✅ **Module Augmentation**: extending existing types globally
- ✅ **Ambient Declarations**: declaring external libraries
- ✅ **Dynamic Imports**: code splitting, conditional loading
- ✅ **Module Factories**: configurable modules, dependency injection
- ✅ **Barrel Exports**: index files, re-export patterns
- ✅ **Triple-Slash Directives**: type references, library references

### 7. `src/advanced-types.ts`
Advanced type system features:
- ✅ **Mapped Types**: transforming object types, key transformation
- ✅ **Conditional Types**: type-level logic, distributive conditionals
- ✅ **Template Literal Types**: string manipulation, path building
- ✅ **Recursive Types**: deeply nested type operations
- ✅ **Branded Types**: nominal typing patterns, type safety
- ✅ **Tuple Utilities**: head, tail, reverse operations
- ✅ **String Manipulation**: uppercase, lowercase, split, join
- ✅ **Type Predicates**: union detection, type guards
- ✅ **Higher-Kinded Types**: functor simulation, HKT patterns

### 8. `src/error-validation.ts`
Error handling and validation patterns:
- ✅ **Custom Error Classes**: structured error hierarchies
- ✅ **Result Pattern**: functional error handling
- ✅ **Type Guards**: runtime type checking, assertion functions
- ✅ **Validation Schemas**: rule-based validation, transformers
- ✅ **Error Boundaries**: centralized error handling
- ✅ **Safe Parsing**: result-based parsing functions
- ✅ **Assertion Functions**: type-narrowing assertions
- ✅ **Try-Catch Utilities**: functional try-catch patterns

### 9. `src/utilities-helpers.ts`
Common utility functions and type helpers:
- ✅ **String Utilities**: case conversion, truncation, normalization
- ✅ **Array Utilities**: chunking, grouping, shuffling, sampling
- ✅ **Object Utilities**: deep cloning, merging, property access
- ✅ **Function Utilities**: debouncing, throttling, memoization
- ✅ **Date Utilities**: formatting, arithmetic, comparisons
- ✅ **Number Utilities**: clamping, rounding, formatting
- ✅ **Validation Helpers**: email, URL, UUID, password validation
- ✅ **Color Utilities**: hex/RGB conversion, color manipulation
- ✅ **Performance Utilities**: timing, batching, measurement

### 10. `src/index.ts` (Entry Point)
Main entry point that imports and demonstrates usage of all modules.

## Project Structure

```
sample_project_typescript/
├── package.json                 # Dependencies and scripts
├── tsconfig.json               # TypeScript configuration
├── README.md                   # This documentation
└── src/
    ├── index.ts               # Main entry point
    ├── types-interfaces.ts    # Core type system
    ├── classes-inheritance.ts # OOP features
    ├── functions-generics.ts  # Functions and generics
    ├── async-promises.ts      # Async programming
    ├── decorators-metadata.ts # Decorators system
    ├── modules-namespaces.ts  # Module organization
    ├── advanced-types.ts      # Advanced type features
    ├── error-validation.ts    # Error handling
    └── utilities-helpers.ts   # Common utilities
```

## Installation and Setup

### Prerequisites
- Node.js (v16 or higher)
- npm or yarn package manager

### Installation
```bash
# Install dependencies
npm install

# Or with yarn
yarn install
```

### Available Scripts

```bash
# Compile TypeScript
npm run build

# Compile and watch for changes
npm run build:watch

# Run compiled JavaScript
npm start

# Run with ts-node (development)
npm run dev

# Run tests
npm test

# Run tests in watch mode
npm run test:watch

# Lint code
npm run lint

# Fix lint issues
npm run lint:fix

# Clean build artifacts
npm run clean
```

## TypeScript Configuration

The project uses strict TypeScript settings for maximum type safety:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "strict": true,
    "experimentalDecorators": true,
    "emitDecoratorMetadata": true,
    "exactOptionalPropertyTypes": true,
    "noUncheckedIndexedAccess": true,
    // ... other strict settings
  }
}
```

## Key Features Demonstrated

### Type Safety
- Strict null checks
- Exact optional properties
- No unchecked indexed access
- Comprehensive type annotations

### Modern TypeScript
- Latest ES features (ES2020 target)
- Experimental decorators
- Advanced type manipulations
- Template literal types

### Best Practices
- Proper error handling patterns
- Functional programming concepts
- Design pattern implementations
- Performance optimization techniques

### Real-World Patterns
- Dependency injection
- Validation frameworks
- Async operation management
- Utility library patterns

## Usage Examples

### Basic Type Usage
```typescript
import { User, createUser } from './types-interfaces';

const user: User = {
  id: 1,
  name: "John Doe",
  email: "john@example.com",
  createdAt: new Date(),
  preferences: {
    theme: "dark",
    notifications: true,
    language: "en"
  }
};
```

### Class Inheritance
```typescript
import { Employee, Person } from './classes-inheritance';

const employee = new Employee("Jane Smith", 28, 456, "Engineering", 75000);
console.log(employee.introduce()); // Uses overridden method
employee.celebrateBirthday(); // Accesses protected members
```

### Async Operations
```typescript
import { PromisePool, AsyncCache } from './async-promises';

const pool = new PromisePool(3);
const cache = new AsyncCache(60000);

// Use promise pool for concurrent operations
userIds.forEach(id => {
  pool.add(() => fetchUserData(id));
});

const results = await pool.execute();
```

### Advanced Types
```typescript
import { DeepPartial, Paths, Get } from './advanced-types';

type UserUpdate = DeepPartial<User>;
type UserPaths = Paths<User>; // "name" | "email" | "preferences.theme" | etc.

function getValue<T, K extends Paths<T>>(obj: T, path: K): Get<T, K> {
  // Type-safe nested property access
}
```

### Error Handling
```typescript
import { Result, Ok, Err, validateUser } from './error-validation';

const result = validateUser(userData);

if (result.success) {
  // result.data is properly typed
  console.log(result.data.name);
} else {
  // result.error contains validation errors
  console.error(result.error);
}
```

## Testing with Code Analysis Tools

This project is specifically designed to test various code analysis scenarios:

### Dependency Analysis
- Import/export relationships
- Module dependencies
- Circular dependency detection

### Type Analysis
- Type inference testing
- Generic resolution
- Complex type relationships

### Pattern Recognition
- Design pattern detection
- Common TypeScript idioms
- Best practice validation

### Complexity Metrics
- Cyclomatic complexity
- Type complexity
- Inheritance hierarchies

## Integration with Graph Databases

The project structure supports graph database population for:

### Node Types
- **Files**: Source files, test files, configuration files
- **Classes**: Regular classes, abstract classes, interfaces
- **Functions**: Methods, static methods, constructors
- **Types**: Interfaces, type aliases, enums
- **Variables**: Properties, parameters, local variables

### Relationship Types
- **IMPORTS**: File import relationships
- **EXTENDS**: Class/interface inheritance
- **IMPLEMENTS**: Interface implementation
- **CALLS**: Function call relationships
- **USES**: Type usage relationships
- **CONTAINS**: Containment relationships

### Properties
- **Language Features**: decorators, generics, async/await
- **Access Modifiers**: public, private, protected
- **Type Information**: parameter types, return types
- **Metadata**: JSDoc comments, decorator metadata

## Contributing

When adding new TypeScript features or patterns:

1. Create focused examples in the appropriate file
2. Include comprehensive type annotations
3. Add JSDoc comments for documentation
4. Update this README with new features
5. Ensure examples are realistic and practical

## Language Features Coverage

| Feature Category | Coverage | File Location |
|-----------------|----------|---------------|
| Basic Types | ✅ Complete | `types-interfaces.ts` |
| Classes & OOP | ✅ Complete | `classes-inheritance.ts` |
| Functions & Generics | ✅ Complete | `functions-generics.ts` |
| Async Programming | ✅ Complete | `async-promises.ts` |
| Decorators | ✅ Complete | `decorators-metadata.ts` |
| Modules & Namespaces | ✅ Complete | `modules-namespaces.ts` |
| Advanced Types | ✅ Complete | `advanced-types.ts` |
| Error Handling | ✅ Complete | `error-validation.ts` |
| Utilities | ✅ Complete | `utilities-helpers.ts` |

## Use Cases

This sample project is ideal for:

### Development Tools
- **IDEs**: Testing IntelliSense, refactoring, navigation
- **Linters**: ESLint rule validation, custom rule testing
- **Formatters**: Prettier configuration testing

### Code Analysis
- **Static Analysis**: Type checking, unused code detection
- **Dependency Analysis**: Import graph construction
- **Complexity Analysis**: Metrics calculation

### Learning & Training
- **TypeScript Education**: Comprehensive feature examples
- **Best Practices**: Real-world pattern demonstration
- **Code Reviews**: Reference implementation examples

### Testing & QA
- **Type System Testing**: Edge case coverage
- **Tool Validation**: Ensuring tools handle complex TypeScript
- **Performance Testing**: Large-scale TypeScript compilation

## Versioning

This project follows semantic versioning:
- **Major**: Breaking changes to file structure or major feature additions
- **Minor**: New TypeScript features, enhanced examples
- **Patch**: Bug fixes, documentation improvements, minor updates

Current version: **1.0.0**

## License

MIT License - feel free to use this project for testing, education, or as a reference implementation.

---

*This TypeScript sample project provides comprehensive coverage of modern TypeScript features and patterns, making it an ideal testing ground for code analysis tools, educational purposes, and development tool validation.*
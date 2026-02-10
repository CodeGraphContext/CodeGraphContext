# Sample C# Project for CodeGraphContext

This is a sample C# project used for testing the CodeGraphContext C# parser.

## Project Structure

```
sample_project_csharp/
├── src/
│   └── Example.App/
│       ├── Program.cs                    # Main entry point
│       ├── OuterClass.cs                 # Nested class example
│       ├── Models/
│       │   ├── User.cs                   # User class
│       │   ├── Role.cs                   # Role enum
│       │   ├── Person.cs                 # Record types
│       │   └── Point.cs                  # Struct types
│       ├── Services/
│       │   ├── IGreetingService.cs       # Interface
│       │   ├── GreetingService.cs        # Service implementation
│       │   └── LegacyService.cs          # Service with attributes
│       ├── Utils/
│       │   ├── CollectionHelper.cs       # Collection utilities
│       │   └── FileHelper.cs             # File I/O utilities
│       └── Attributes/
│           └── CustomAttributes.cs       # Custom attribute definitions
└── README.md                             # This file
```

## Features Demonstrated

### Language Constructs
- **Classes**: Regular classes with constructors, methods, and properties
- **Interfaces**: Interface definitions and implementations
- **Enums**: Enumeration types
- **Records**: C# 9.0+ record types with inheritance
- **Structs**: Value types including readonly structs
- **Nested Classes**: Inner classes with access to outer class members
- **Static Classes**: Utility classes with static methods

### Advanced Features
- **Custom Attributes**: Attribute definitions and usage
- **Generics**: Generic collections (IEnumerable<T>)
- **LINQ**: Language Integrated Query operations
- **Properties**: Auto-properties and computed properties
- **Operator Overloading**: Custom operators for structs
- **Pattern Matching**: Switch expressions
- **Namespaces**: Organized code structure

### Method Types
- Constructors (default and parameterized)
- Instance methods
- Static methods
- Private helper methods
- Methods with attributes

### Dependencies
- System namespaces (System, System.Collections.Generic, System.IO, System.Linq)
- Internal project references

## Purpose

This project is designed to test the C# parser's ability to:
1. Parse class, interface, struct, enum, and record declarations
2. Extract method signatures and parameters
3. Identify using directives and imports
4. Track method calls and object creation
5. Handle nested classes and namespaces
6. Recognize custom attributes
7. Build accurate code graphs for C# projects

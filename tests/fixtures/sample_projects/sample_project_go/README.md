# Go Sample Project

This is a comprehensive Go sample project for testing code analysis and indexing tools. It covers major Go language features and patterns.

## Files Overview

### 1. `basic_functions.go`
- Basic function definitions
- Multiple return values
- Named returns
- Variadic functions
- Higher-order functions
- Closures
- Recursion
- Defer, panic, and recover
- Init functions

### 2. `structs_methods.go`
- Struct definitions
- Value and pointer receivers
- Constructor functions
- Embedded structs
- Method chaining
- Private and public fields

### 3. `interfaces.go`
- Interface definitions
- Interface implementations
- Interface embedding
- Type assertions
- Type switches
- Empty interfaces
- Polymorphism

### 4. `goroutines_channels.go`
- Goroutines
- Channels (buffered and unbuffered)
- Select statements
- Worker pools
- Mutexes (sync.Mutex, sync.RWMutex)
- Wait groups
- Pipeline patterns
- Fan-out/Fan-in patterns
- Singleton with sync.Once

### 5. `error_handling.go`
- Basic error returns
- Custom error types
- Error wrapping (Go 1.13+)
- Sentinel errors
- Error type assertions
- errors.Is and errors.As
- Validation errors
- Panic to error conversion
- Deferred error handling

### 6. `generics.go`
- Generic functions
- Generic types (Stack, Queue, Cache)
- Type constraints
- Generic data structures
- Map/Filter/Reduce with generics
- Generic linked lists

### 7. `embedded_composition.go`
- Struct embedding
- Method promotion
- Multiple embedding
- Interface embedding
- Composition over inheritance
- Name conflict resolution

### 8. `advanced_types.go`
- Custom types
- Type aliases
- Enum patterns
- Maps and nested maps
- Slices and 2D slices
- Arrays
- Struct tags
- Anonymous structs
- Function types
- Channel types
- Sortable types (sort.Interface)
- Bit flags

### 9. `packages_imports.go`
- Standard library imports
- Aliased imports
- Blank imports
- Package initialization (init)
- Multiple package usage
- Common stdlib packages: fmt, strings, math, time, os, io, net/http

### 10. `util/helpers.go` (subpackage)
- Utility types and functions
- String utilities
- Math utilities
- Slice utilities
- Validators
- Logger implementation
- Package-level helper functions

## Features Covered

- ✅ Basic syntax and functions
- ✅ Structs and methods
- ✅ Interfaces and polymorphism
- ✅ Concurrency (goroutines, channels, sync)
- ✅ Error handling patterns
- ✅ Generics (Go 1.18+)
- ✅ Embedding and composition
- ✅ Advanced types (maps, slices, custom types)
- ✅ Package organization
- ✅ Standard library usage
- ✅ Common patterns and idioms

## Building and Running

```bash
# Initialize module
go mod init github.com/example/sample_project_go

# Download dependencies
go mod tidy

# Run individual files
go run basic_functions.go
go run structs_methods.go
# ... etc

# Build all
go build ./...

# Run tests (if tests are added)
go test ./...
```

## Use Cases

This sample project is designed for:
- Testing code analysis tools
- Demonstrating Go best practices
- Code indexing and graph database population
- Understanding Go language features
- Reference implementation for Go patterns


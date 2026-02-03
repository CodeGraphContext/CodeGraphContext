# Rust Sample Project

A comprehensive Rust sample project for testing code analysis and indexing tools. This project covers major Rust language features and patterns.

## Project Structure

```
sample_project_rust/
├── Cargo.toml
├── README.md
└── src/
    ├── lib.rs                    # Main library file
    ├── basic_functions.rs        # Basic Rust patterns
    ├── structs_enums.rs          # Structs and enums
    ├── traits.rs                 # Traits and implementations
    ├── error_handling.rs         # Error handling patterns
    ├── lifetimes_references.rs   # Lifetimes and borrowing
    ├── generics.rs               # Generic types and functions
    ├── concurrency.rs            # Threading and sync
    ├── iterators_closures.rs     # Iterators and closures
    ├── smart_pointers.rs         # Smart pointers (Box, Rc, Arc)
    └── modules.rs                # Module organization
```

## Files Overview

### 1. `basic_functions.rs`
- Function definitions and patterns
- Ownership and borrowing
- Multiple return values (tuples)
- Result and Option types
- Lifetimes in functions
- Generic functions with trait bounds
- Higher-order functions
- Closures and function returns
- Recursion

### 2. `structs_enums.rs`
- Struct definitions (regular, tuple, unit)
- Methods (impl blocks)
- Associated functions (constructors)
- Embedded structs
- Enums with data
- Pattern matching
- Display trait implementations

### 3. `traits.rs`
- Trait definitions
- Trait implementations
- Default implementations
- Associated types and constants
- Trait bounds and where clauses
- Trait objects (dyn Trait)
- Operator overloading
- Blanket implementations

### 4. `error_handling.rs`
- Custom error types
- Result and Option handling
- Error propagation (? operator)
- Error conversion (From trait)
- Multiple error types
- Validation patterns
- Error combinators (map, and_then)

### 5. `lifetimes_references.rs`
- Explicit lifetime annotations
- Lifetime elision rules
- Structs with lifetimes
- Multiple lifetime parameters
- Static lifetimes
- Higher-ranked trait bounds
- Lifetime bounds

### 6. `generics.rs`
- Generic functions
- Generic structs and enums
- Trait bounds on generics
- Where clauses
- Associated types
- Generic collections (Stack, Queue, LinkedList)
- Const generics
- Generic closures

### 7. `concurrency.rs`
- Thread spawning
- Arc and Mutex for shared state
- RwLock for read-heavy workloads
- Channels (mpsc)
- Thread pools
- Barriers and atomic operations
- sync::Once for initialization
- Scoped threads

### 8. `iterators_closures.rs`
- Custom iterators
- Iterator adapters (map, filter, fold)
- Closure types (Fn, FnMut, FnOnce)
- Iterator chains
- Lazy evaluation
- Infinite iterators
- Peekable iterators

### 9. `smart_pointers.rs`
- Box for heap allocation
- Rc for reference counting
- Arc for thread-safe counting
- RefCell for interior mutability
- Weak references
- Cow (Clone on Write)
- Custom smart pointers
- Drop trait

### 10. `modules.rs`
- Module organization
- Nested modules
- Public/private visibility
- Re-exports (pub use)
- Module paths
- Prelude pattern

## Features Covered

- ✅ **Ownership & Borrowing**: Move semantics, references, lifetimes
- ✅ **Type System**: Structs, enums, traits, generics
- ✅ **Error Handling**: Result, Option, custom errors
- ✅ **Concurrency**: Threads, Arc, Mutex, channels
- ✅ **Functional Programming**: Iterators, closures, combinators
- ✅ **Smart Pointers**: Box, Rc, Arc, RefCell, Weak
- ✅ **Module System**: Visibility, re-exports, organization
- ✅ **Pattern Matching**: Match expressions, if let
- ✅ **Trait System**: Implementations, bounds, objects
- ✅ **Advanced Features**: Lifetimes, const generics, HRTBs

## Building and Testing

```bash
# Build the project
cargo build

# Run tests
cargo test

# Check without building
cargo check

# Build documentation
cargo doc --open

# Run clippy for lints
cargo clippy
```

## Use Cases

This sample project is designed for:
- Testing Rust code analysis tools
- Demonstrating Rust best practices
- Code indexing and graph database population
- Understanding Rust ownership model
- Reference implementation for Rust patterns
- Compiler and IDE testing

## Rust Concepts Demonstrated

### Ownership
- Move semantics
- Borrowing (immutable and mutable)
- References and dereferencing
- Lifetime annotations

### Type System
- Zero-cost abstractions
- Type inference
- Algebraic data types (enums)
- Pattern matching exhaustiveness

### Memory Safety
- No null pointers (Option instead)
- No data races (enforced by type system)
- RAII (Resource Acquisition Is Initialization)
- Automatic memory management

### Concurrency
- Fearless concurrency (no data races)
- Message passing (channels)
- Shared state (Arc + Mutex)
- Thread safety guaranteed by type system

## Integration with CodeGraphContext

This project can be used to test:
- Function call resolution across modules
- Trait implementation tracking
- Lifetime relationship analysis
- Generic type instantiation
- Module dependency graphs
- Concurrent code patterns
- Smart pointer usage patterns


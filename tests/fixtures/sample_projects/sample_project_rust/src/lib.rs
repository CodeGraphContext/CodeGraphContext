// lib.rs - Main library file for Rust sample project

pub mod basic_functions;
pub mod structs_enums;
pub mod traits;
pub mod error_handling;
pub mod lifetimes_references;
pub mod generics;
pub mod concurrency;
pub mod iterators_closures;
pub mod smart_pointers;
pub mod modules;

// Re-exports for convenience
pub use basic_functions::*;
pub use structs_enums::{Person, Status};
pub use traits::{Describable, Area};

/// Library-level documentation
/// 
/// This is a comprehensive Rust sample project demonstrating:
/// - Basic and advanced function patterns
/// - Structs, enums, and their implementations
/// - Traits and trait implementations
/// - Error handling with Result and custom errors
/// - Lifetimes and references
/// - Generics and type parameters
/// - Concurrency with threads and channels
/// - Iterators and closures
/// - Smart pointers (Box, Rc, Arc, RefCell)
/// - Module organization

#[cfg(test)]
mod integration_tests {
    use super::*;

    #[test]
    fn test_basic_workflow() {
        let result = simple_function(5);
        assert_eq!(result, 10);

        let person = Person::new("Alice".to_string(), 30);
        assert_eq!(person.name, "Alice");
    }
}


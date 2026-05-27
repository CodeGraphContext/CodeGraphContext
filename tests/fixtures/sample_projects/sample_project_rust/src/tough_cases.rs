use std::fmt::Display;

/*
Tough Case 1: Blanket Trait Implementations
This trait is implemented for ANY type that implements Display.
Tests if the indexer can resolve calls to 'tough_print' for a String or i32.
*/
pub trait ToughPrinter {
    fn tough_print(&self);
}

impl<T: Display> ToughPrinter for T {
    fn tough_print(&self) {
        println!("Tough: {}", self);
    }
}

pub fn test_blanket_impl() {
    let s = String::from("hello");
    s.tough_print(); // Should link to the blanket impl above
}

/*
Tough Case 2: Complex Module Nesting and Shadowing
*/
pub mod outer {
    pub fn action() { println!("outer action"); }

    pub mod inner {
        pub fn action() { println!("inner action"); }
        
        pub fn call_both() {
            super::action(); // Explicit parent call
            action();        // Local call
        }
    }
}

/*
Tough Case 3: Foreign Function Interface (FFI)
External C functions often represent the "edge" of the graph.
*/
extern "C" {
    pub fn snappy_compress(
        input: *const u8,
        input_length: usize,
        compressed: *mut u8,
        compressed_length: *mut usize,
    ) -> i32;
}

/*
Tough Case 4: Deref Trait and Smart Pointers
Relationships through Deref can be invisible to simple indexers.
*/
use std::ops::Deref;

pub struct Wrapper<T>(T);

impl<T> Deref for Wrapper<T> {
    type Target = T;
    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

pub struct Target;
impl Target {
    pub fn target_method(&self) { println!("Target reached"); }
}

pub fn test_deref() {
    let w = Wrapper(Target);
    w.target_method(); // Should resolve to Target::target_method via Deref
}

/*
Tough Case 5: Async Trait Methods (Simulated)
*/
/*
Tough Case 6: Overlapping Blanket Implementations and Specialization
This tests how the indexer handles traits when multiple implementations
might apply, but only one is valid due to specific bounds.
*/
pub trait AdvancedTrait {
    fn specialized_action(&self);
}

// Impl 1: Generic for all T
impl<T> AdvancedTrait for T {
    default fn specialized_action(&self) {
        println!("Generic implementation");
    }
}

// Impl 2: Only for types that also implement Display
impl<T: std::fmt::Display> AdvancedTrait for T {
    fn specialized_action(&self) {
        println!("Specialized Display implementation: {}", self);
    }
}

pub fn test_specialization() {
    let x = 42;
    x.specialized_action(); // Should resolve to Impl 2
}

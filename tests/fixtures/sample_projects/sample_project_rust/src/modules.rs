// modules.rs - Demonstrates Rust module system and organization

// Nested modules
pub mod geometry {
    pub mod shapes {
        pub struct Circle {
            pub radius: f64,
        }

        pub struct Rectangle {
            pub width: f64,
            pub height: f64,
        }

        impl Circle {
            pub fn new(radius: f64) -> Self {
                Self { radius }
            }

            pub fn area(&self) -> f64 {
                std::f64::consts::PI * self.radius * self.radius
            }
        }

        impl Rectangle {
            pub fn new(width: f64, height: f64) -> Self {
                Self { width, height }
            }

            pub fn area(&self) -> f64 {
                self.width * self.height
            }
        }
    }

    pub mod calculations {
        use super::shapes::{Circle, Rectangle};

        pub fn total_area(circle: &Circle, rectangle: &Rectangle) -> f64 {
            circle.area() + rectangle.area()
        }
    }
}

// Module with private items
pub mod data {
    pub struct PublicStruct {
        pub public_field: i32,
        private_field: i32,
    }

    impl PublicStruct {
        pub fn new(public_field: i32, private_field: i32) -> Self {
            Self {
                public_field,
                private_field,
            }
        }

        pub fn get_private(&self) -> i32 {
            self.private_field
        }
    }

    pub fn public_function() -> i32 {
        private_function() + 10
    }

    fn private_function() -> i32 {
        42
    }
}

// Re-exports
pub mod utils {
    pub use super::geometry::shapes::Circle;
    pub use super::geometry::shapes::Rectangle;

    pub fn create_default_circle() -> Circle {
        Circle::new(1.0)
    }
}

// Module with use statements
pub mod operations {
    use std::collections::HashMap;

    pub fn create_map() -> HashMap<String, i32> {
        let mut map = HashMap::new();
        map.insert("one".to_string(), 1);
        map.insert("two".to_string(), 2);
        map
    }
}

// Glob imports (use with caution)
pub mod prelude {
    pub use super::geometry::shapes::*;
    pub use super::data::*;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_circle_area() {
        let circle = geometry::shapes::Circle::new(5.0);
        let area = circle.area();
        assert!((area - 78.54).abs() < 0.01);
    }

    #[test]
    fn test_public_struct() {
        let s = data::PublicStruct::new(10, 20);
        assert_eq!(s.public_field, 10);
        assert_eq!(s.get_private(), 20);
    }
}


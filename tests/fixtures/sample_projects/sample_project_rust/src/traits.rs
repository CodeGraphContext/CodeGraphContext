// traits.rs - Demonstrates Rust traits and trait implementations
use std::fmt;
use std::ops::Add;

/// Basic trait definition
pub trait Describable {
    fn describe(&self) -> String;
}

/// Trait with default implementation
pub trait Greetable {
    fn greet(&self) -> String {
        "Hello!".to_string()
    }

    fn formal_greet(&self) -> String;
}

/// Trait with associated types
pub trait Container {
    type Item;

    fn add(&mut self, item: Self::Item);
    fn get(&self, index: usize) -> Option<&Self::Item>;
    fn len(&self) -> usize;
    
    fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

/// Trait with associated constants
pub trait MathConstants {
    const PI: f64;
    const E: f64;
}

/// Trait for conversion
pub trait FromString {
    fn from_string(s: &str) -> Result<Self, String>
    where
        Self: Sized;
}

/// Marker trait (empty trait)
pub trait Serializable {}

// Struct definitions

#[derive(Debug, Clone)]
pub struct Rectangle {
    pub width: f64,
    pub height: f64,
}

#[derive(Debug, Clone)]
pub struct Circle {
    pub radius: f64,
}

#[derive(Debug, Clone)]
pub struct Triangle {
    pub a: f64,
    pub b: f64,
    pub c: f64,
}

#[derive(Debug)]
pub struct Student {
    pub name: String,
    pub grade: u32,
}

#[derive(Debug)]
pub struct Teacher {
    pub name: String,
    pub subject: String,
}

// Trait implementations

impl Describable for Rectangle {
    fn describe(&self) -> String {
        format!("Rectangle with width {} and height {}", self.width, self.height)
    }
}

impl Describable for Circle {
    fn describe(&self) -> String {
        format!("Circle with radius {}", self.radius)
    }
}

impl Describable for Triangle {
    fn describe(&self) -> String {
        format!("Triangle with sides {}, {}, {}", self.a, self.b, self.c)
    }
}

impl Greetable for Student {
    fn formal_greet(&self) -> String {
        format!("Good day, student {}", self.name)
    }
}

impl Greetable for Teacher {
    fn greet(&self) -> String {
        format!("Hello, I'm {}", self.name)
    }

    fn formal_greet(&self) -> String {
        format!("Good day, Professor {}", self.name)
    }
}

// Trait for area calculation
pub trait Area {
    fn area(&self) -> f64;
}

impl Area for Rectangle {
    fn area(&self) -> f64 {
        self.width * self.height
    }
}

impl Area for Circle {
    fn area(&self) -> f64 {
        std::f64::consts::PI * self.radius * self.radius
    }
}

impl Area for Triangle {
    fn area(&self) -> f64 {
        // Heron's formula
        let s = (self.a + self.b + self.c) / 2.0;
        (s * (s - self.a) * (s - self.b) * (s - self.c)).sqrt()
    }
}

// Trait for perimeter calculation
pub trait Perimeter {
    fn perimeter(&self) -> f64;
}

impl Perimeter for Rectangle {
    fn perimeter(&self) -> f64 {
        2.0 * (self.width + self.height)
    }
}

impl Perimeter for Circle {
    fn perimeter(&self) -> f64 {
        2.0 * std::f64::consts::PI * self.radius
    }
}

impl Perimeter for Triangle {
    fn perimeter(&self) -> f64 {
        self.a + self.b + self.c
    }
}

// Generic functions using traits

/// Function accepting any type implementing Describable
pub fn print_description<T: Describable>(item: &T) {
    println!("{}", item.describe());
}

/// Function with multiple trait bounds
pub fn print_area_and_perimeter<T: Area + Perimeter>(shape: &T) {
    println!("Area: {}, Perimeter: {}", shape.area(), shape.perimeter());
}

/// Function with where clause
pub fn compare_areas<T, U>(shape1: &T, shape2: &U) -> bool
where
    T: Area,
    U: Area,
{
    shape1.area() > shape2.area()
}

/// Function returning impl Trait
pub fn create_circle(radius: f64) -> impl Area + Perimeter {
    Circle { radius }
}

/// Generic struct with trait bounds
#[derive(Debug)]
pub struct Pair<T> {
    first: T,
    second: T,
}

impl<T> Pair<T> {
    pub fn new(first: T, second: T) -> Self {
        Self { first, second }
    }
}

impl<T: PartialOrd> Pair<T> {
    pub fn max(&self) -> &T {
        if self.first > self.second {
            &self.first
        } else {
            &self.second
        }
    }
}

impl<T: Clone> Pair<T> {
    pub fn clone_first(&self) -> T {
        self.first.clone()
    }
}

// Trait with supertraits
pub trait Shape: Area + Perimeter + fmt::Display {
    fn name(&self) -> &str;
}

impl fmt::Display for Rectangle {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Rectangle({}x{})", self.width, self.height)
    }
}

impl Shape for Rectangle {
    fn name(&self) -> &str {
        "Rectangle"
    }
}

// Trait object example
pub fn total_area(shapes: &[&dyn Area]) -> f64 {
    shapes.iter().map(|s| s.area()).sum()
}

// Associated type example
pub struct VecContainer<T> {
    items: Vec<T>,
}

impl<T> Container for VecContainer<T> {
    type Item = T;

    fn add(&mut self, item: Self::Item) {
        self.items.push(item);
    }

    fn get(&self, index: usize) -> Option<&Self::Item> {
        self.items.get(index)
    }

    fn len(&self) -> usize {
        self.items.len()
    }
}

// Operator overloading using traits
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Point {
    pub x: i32,
    pub y: i32,
}

impl Add for Point {
    type Output = Point;

    fn add(self, other: Point) -> Point {
        Point {
            x: self.x + other.x,
            y: self.y + other.y,
        }
    }
}

// Trait for custom equality
pub trait CustomEq {
    fn custom_eq(&self, other: &Self) -> bool;
}

impl CustomEq for Rectangle {
    fn custom_eq(&self, other: &Self) -> bool {
        (self.width * self.height - other.width * other.height).abs() < 0.001
    }
}

// Blanket implementations
pub trait Summary {
    fn summarize(&self) -> String;
}

impl<T: Describable> Summary for T {
    fn summarize(&self) -> String {
        format!("Summary: {}", self.describe())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rectangle_area() {
        let rect = Rectangle { width: 10.0, height: 5.0 };
        assert_eq!(rect.area(), 50.0);
    }

    #[test]
    fn test_circle_area() {
        let circle = Circle { radius: 5.0 };
        let area = circle.area();
        assert!((area - 78.54).abs() < 0.01);
    }

    #[test]
    fn test_point_add() {
        let p1 = Point { x: 1, y: 2 };
        let p2 = Point { x: 3, y: 4 };
        let p3 = p1 + p2;
        assert_eq!(p3, Point { x: 4, y: 6 });
    }
}


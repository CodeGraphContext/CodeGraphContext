// structs_enums.rs - Demonstrates Rust structs and enums
use std::fmt;

/// Basic struct with public fields
#[derive(Debug, Clone, PartialEq)]
pub struct Person {
    pub name: String,
    pub age: u32,
}

/// Struct with private fields
#[derive(Debug)]
pub struct BankAccount {
    balance: f64,
    account_number: String,
}

/// Tuple struct
#[derive(Debug, Clone, Copy)]
pub struct Point(pub i32, pub i32);

/// Unit struct
#[derive(Debug)]
pub struct Unit;

/// Struct with lifetime parameter
#[derive(Debug)]
pub struct BookReference<'a> {
    title: &'a str,
    author: &'a str,
}

/// Generic struct
#[derive(Debug)]
pub struct Container<T> {
    value: T,
}

impl Person {
    /// Constructor function (associated function)
    pub fn new(name: String, age: u32) -> Self {
        Self { name, age }
    }

    /// Method with immutable self
    pub fn greet(&self) -> String {
        format!("Hello, my name is {} and I'm {} years old", self.name, self.age)
    }

    /// Method with mutable self
    pub fn have_birthday(&mut self) {
        self.age += 1;
    }

    /// Method consuming self
    pub fn into_name(self) -> String {
        self.name
    }

    /// Method returning reference
    pub fn get_name(&self) -> &str {
        &self.name
    }

    /// Associated function
    pub fn default_person() -> Self {
        Self {
            name: String::from("Unknown"),
            age: 0,
        }
    }

    /// Method with additional parameters
    pub fn is_older_than(&self, other: &Person) -> bool {
        self.age > other.age
    }
}

impl BankAccount {
    pub fn new(account_number: String, initial_balance: f64) -> Self {
        Self {
            balance: initial_balance,
            account_number,
        }
    }

    pub fn deposit(&mut self, amount: f64) -> Result<(), String> {
        if amount <= 0.0 {
            return Err("Deposit amount must be positive".to_string());
        }
        self.balance += amount;
        Ok(())
    }

    pub fn withdraw(&mut self, amount: f64) -> Result<(), String> {
        if amount <= 0.0 {
            return Err("Withdrawal amount must be positive".to_string());
        }
        if amount > self.balance {
            return Err("Insufficient funds".to_string());
        }
        self.balance -= amount;
        Ok(())
    }

    pub fn get_balance(&self) -> f64 {
        self.balance
    }
}

impl Point {
    pub fn new(x: i32, y: i32) -> Self {
        Point(x, y)
    }

    pub fn distance_from_origin(&self) -> f64 {
        ((self.0.pow(2) + self.1.pow(2)) as f64).sqrt()
    }

    pub fn translate(&mut self, dx: i32, dy: i32) {
        self.0 += dx;
        self.1 += dy;
    }
}

impl<T> Container<T> {
    pub fn new(value: T) -> Self {
        Self { value }
    }

    pub fn get(&self) -> &T {
        &self.value
    }

    pub fn set(&mut self, value: T) {
        self.value = value;
    }

    pub fn into_inner(self) -> T {
        self.value
    }
}

// Enums

/// Simple enum
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Status {
    Active,
    Inactive,
    Pending,
}

/// Enum with data
#[derive(Debug, Clone, PartialEq)]
pub enum Message {
    Quit,
    Move { x: i32, y: i32 },
    Write(String),
    ChangeColor(u8, u8, u8),
}

/// Result-like enum
#[derive(Debug)]
pub enum MyResult<T, E> {
    Ok(T),
    Err(E),
}

/// Option-like enum
#[derive(Debug)]
pub enum MyOption<T> {
    Some(T),
    None,
}

/// Enum with methods
#[derive(Debug, Clone)]
pub enum TrafficLight {
    Red,
    Yellow,
    Green,
}

impl TrafficLight {
    pub fn duration(&self) -> u32 {
        match self {
            TrafficLight::Red => 60,
            TrafficLight::Yellow => 10,
            TrafficLight::Green => 50,
        }
    }

    pub fn next(&self) -> TrafficLight {
        match self {
            TrafficLight::Red => TrafficLight::Green,
            TrafficLight::Yellow => TrafficLight::Red,
            TrafficLight::Green => TrafficLight::Yellow,
        }
    }
}

impl Message {
    pub fn call(&self) {
        match self {
            Message::Quit => println!("Quitting"),
            Message::Move { x, y } => println!("Moving to ({}, {})", x, y),
            Message::Write(text) => println!("Writing: {}", text),
            Message::ChangeColor(r, g, b) => println!("Changing color to RGB({}, {}, {})", r, g, b),
        }
    }
}

/// Pattern matching with enums
pub fn process_message(msg: Message) -> String {
    match msg {
        Message::Quit => "Quit command".to_string(),
        Message::Move { x, y } if x > 0 && y > 0 => format!("Moving to positive quadrant: ({}, {})", x, y),
        Message::Move { x, y } => format!("Moving to: ({}, {})", x, y),
        Message::Write(text) => format!("Text: {}", text),
        Message::ChangeColor(r, g, b) => format!("Color: RGB({}, {}, {})", r, g, b),
    }
}

/// Enum with tuple variants
#[derive(Debug)]
pub enum IpAddr {
    V4(u8, u8, u8, u8),
    V6(String),
}

impl IpAddr {
    pub fn is_loopback(&self) -> bool {
        match self {
            IpAddr::V4(127, 0, 0, 1) => true,
            IpAddr::V6(s) if s == "::1" => true,
            _ => false,
        }
    }
}

impl fmt::Display for Person {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Person {{ name: {}, age: {} }}", self.name, self.age)
    }
}

impl fmt::Display for Status {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Status::Active => write!(f, "Active"),
            Status::Inactive => write!(f, "Inactive"),
            Status::Pending => write!(f, "Pending"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_person_creation() {
        let person = Person::new("Alice".to_string(), 30);
        assert_eq!(person.name, "Alice");
        assert_eq!(person.age, 30);
    }

    #[test]
    fn test_person_birthday() {
        let mut person = Person::new("Bob".to_string(), 25);
        person.have_birthday();
        assert_eq!(person.age, 26);
    }

    #[test]
    fn test_message_matching() {
        let msg = Message::Move { x: 10, y: 20 };
        let result = process_message(msg);
        assert!(result.contains("Moving"));
    }
}


// error_handling.rs - Demonstrates Rust error handling patterns
use std::error::Error;
use std::fmt;
use std::fs::File;
use std::io::{self, Read};

/// Custom error type
#[derive(Debug, Clone)]
pub struct CustomError {
    pub code: u32,
    pub message: String,
}

impl fmt::Display for CustomError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "Error {}: {}", self.code, self.message)
    }
}

impl Error for CustomError {}

impl CustomError {
    pub fn new(code: u32, message: String) -> Self {
        Self { code, message }
    }
}

/// Validation error
#[derive(Debug)]
pub struct ValidationError {
    pub field: String,
    pub value: String,
    pub reason: String,
}

impl fmt::Display for ValidationError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(
            f,
            "Validation failed for field '{}' with value '{}': {}",
            self.field, self.value, self.reason
        )
    }
}

impl Error for ValidationError {}

/// Multiple error types enum
#[derive(Debug)]
pub enum AppError {
    Io(io::Error),
    Parse(std::num::ParseIntError),
    Custom(CustomError),
    Validation(ValidationError),
}

impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            AppError::Io(err) => write!(f, "IO error: {}", err),
            AppError::Parse(err) => write!(f, "Parse error: {}", err),
            AppError::Custom(err) => write!(f, "Custom error: {}", err),
            AppError::Validation(err) => write!(f, "Validation error: {}", err),
        }
    }
}

impl Error for AppError {}

impl From<io::Error> for AppError {
    fn from(err: io::Error) -> Self {
        AppError::Io(err)
    }
}

impl From<std::num::ParseIntError> for AppError {
    fn from(err: std::num::ParseIntError) -> Self {
        AppError::Parse(err)
    }
}

impl From<CustomError> for AppError {
    fn from(err: CustomError) -> Self {
        AppError::Custom(err)
    }
}

// Basic Result usage

/// Simple function returning Result
pub fn divide(a: i32, b: i32) -> Result<i32, String> {
    if b == 0 {
        Err("Division by zero".to_string())
    } else {
        Ok(a / b)
    }
}

/// Function with multiple error conditions
pub fn validate_age(age: i32) -> Result<i32, String> {
    if age < 0 {
        return Err("Age cannot be negative".to_string());
    }
    if age > 150 {
        return Err("Age is unrealistic".to_string());
    }
    Ok(age)
}

/// Using custom error type
pub fn validate_username(username: &str) -> Result<String, CustomError> {
    if username.is_empty() {
        return Err(CustomError::new(400, "Username cannot be empty".to_string()));
    }
    if username.len() < 3 {
        return Err(CustomError::new(400, "Username too short".to_string()));
    }
    if username.len() > 20 {
        return Err(CustomError::new(400, "Username too long".to_string()));
    }
    Ok(username.to_string())
}

/// Error propagation with ? operator
pub fn read_file_contents(filename: &str) -> Result<String, io::Error> {
    let mut file = File::open(filename)?;
    let mut contents = String::new();
    file.read_to_string(&mut contents)?;
    Ok(contents)
}

/// Chaining operations with ?
pub fn parse_and_double(s: &str) -> Result<i32, std::num::ParseIntError> {
    let num: i32 = s.parse()?;
    Ok(num * 2)
}

/// Multiple error types with ?
pub fn read_and_parse(filename: &str) -> Result<i32, AppError> {
    let mut file = File::open(filename)?;
    let mut contents = String::new();
    file.read_to_string(&mut contents)?;
    let num: i32 = contents.trim().parse()?;
    Ok(num)
}

/// Custom validation with ValidationError
pub fn validate_email(email: &str) -> Result<String, ValidationError> {
    if !email.contains('@') {
        return Err(ValidationError {
            field: "email".to_string(),
            value: email.to_string(),
            reason: "Must contain @ symbol".to_string(),
        });
    }
    if !email.contains('.') {
        return Err(ValidationError {
            field: "email".to_string(),
            value: email.to_string(),
            reason: "Must contain domain extension".to_string(),
        });
    }
    Ok(email.to_string())
}

/// Using match for error handling
pub fn process_result(result: Result<i32, String>) -> i32 {
    match result {
        Ok(value) => value,
        Err(e) => {
            println!("Error occurred: {}", e);
            0
        }
    }
}

/// Using unwrap_or
pub fn safe_divide(a: i32, b: i32) -> i32 {
    divide(a, b).unwrap_or(0)
}

/// Using unwrap_or_else
pub fn safe_divide_with_default(a: i32, b: i32, default: i32) -> i32 {
    divide(a, b).unwrap_or_else(|_| default)
}

/// Using map and and_then
pub fn parse_and_validate(s: &str) -> Result<i32, String> {
    s.parse::<i32>()
        .map_err(|e| format!("Parse error: {}", e))
        .and_then(|num| {
            if num >= 0 {
                Ok(num)
            } else {
                Err("Number must be non-negative".to_string())
            }
        })
}

/// Error recovery pattern
pub fn try_parse_or_default(s: &str, default: i32) -> i32 {
    s.parse().unwrap_or(default)
}

/// Multiple validation steps
pub fn validate_user(name: &str, age: i32, email: &str) -> Result<User, Vec<String>> {
    let mut errors = Vec::new();

    if name.is_empty() {
        errors.push("Name cannot be empty".to_string());
    }
    if age < 18 {
        errors.push("Must be 18 or older".to_string());
    }
    if !email.contains('@') {
        errors.push("Invalid email".to_string());
    }

    if errors.is_empty() {
        Ok(User {
            name: name.to_string(),
            age,
            email: email.to_string(),
        })
    } else {
        Err(errors)
    }
}

#[derive(Debug)]
pub struct User {
    name: String,
    age: i32,
    email: String,
}

/// Panic for unrecoverable errors
pub fn must_succeed(value: Option<i32>) -> i32 {
    value.expect("This should never be None")
}

/// Option to Result conversion
pub fn find_user(id: u32) -> Option<String> {
    if id > 0 {
        Some(format!("User {}", id))
    } else {
        None
    }
}

pub fn get_user_or_error(id: u32) -> Result<String, String> {
    find_user(id).ok_or_else(|| "User not found".to_string())
}

/// Combining Results
pub fn validate_and_parse(s: &str) -> Result<i32, String> {
    if s.is_empty() {
        return Err("Input is empty".to_string());
    }
    s.parse::<i32>()
        .map_err(|e| format!("Failed to parse: {}", e))
}

/// Early return pattern
pub fn process_input(input: &str) -> Result<i32, String> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return Err("Empty input".to_string());
    }

    let num: i32 = trimmed.parse().map_err(|_| "Invalid number".to_string())?;

    if num < 0 {
        return Err("Negative number".to_string());
    }

    Ok(num * 2)
}

/// Collecting Results
pub fn parse_numbers(strings: Vec<&str>) -> Result<Vec<i32>, String> {
    strings
        .iter()
        .map(|s| s.parse::<i32>().map_err(|e| e.to_string()))
        .collect()
}

/// Result with Box<dyn Error>
pub fn flexible_error_handling(input: &str) -> Result<i32, Box<dyn Error>> {
    let num: i32 = input.parse()?;
    if num < 0 {
        return Err(Box::new(CustomError::new(400, "Negative number".to_string())));
    }
    Ok(num)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_divide_success() {
        assert_eq!(divide(10, 2), Ok(5));
    }

    #[test]
    fn test_divide_error() {
        assert!(divide(10, 0).is_err());
    }

    #[test]
    fn test_validate_age() {
        assert!(validate_age(25).is_ok());
        assert!(validate_age(-1).is_err());
        assert!(validate_age(200).is_err());
    }

    #[test]
    fn test_validate_username() {
        assert!(validate_username("john_doe").is_ok());
        assert!(validate_username("ab").is_err());
        assert!(validate_username("").is_err());
    }
}


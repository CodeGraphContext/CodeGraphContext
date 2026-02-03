// basic_functions.rs - Demonstrates basic Rust function patterns and ownership
use std::fmt;

/// Simple function with single return value
pub fn simple_function(x: i32) -> i32 {
    x * 2
}

/// Multiple return values using tuple
pub fn multiple_returns(a: i32, b: i32) -> (i32, i32, i32) {
    (a + b, a - b, a * b)
}

/// Function with Result return type for error handling
pub fn divide(a: i32, b: i32) -> Result<i32, String> {
    if b == 0 {
        Err("Division by zero".to_string())
    } else {
        Ok(a / b)
    }
}

/// Function with Option return type
pub fn find_first_even(numbers: &[i32]) -> Option<i32> {
    for &num in numbers {
        if num % 2 == 0 {
            return Some(num);
        }
    }
    None
}

/// Function demonstrating ownership transfer
pub fn take_ownership(s: String) -> usize {
    let len = s.len();
    println!("Taking ownership of: {}", s);
    len
}

/// Function borrowing immutably
pub fn borrow_read(s: &String) -> usize {
    s.len()
}

/// Function borrowing mutably
pub fn borrow_write(s: &mut String) {
    s.push_str(" - modified");
}

/// Function returning borrowed reference with lifetime
pub fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() {
        x
    } else {
        y
    }
}

/// Generic function with trait bound
pub fn print_it<T: fmt::Display>(item: T) {
    println!("Item: {}", item);
}

/// Generic function with multiple trait bounds
pub fn compare_and_print<T: PartialOrd + fmt::Display>(a: T, b: T) {
    if a > b {
        println!("{} is greater than {}", a, b);
    } else {
        println!("{} is less than or equal to {}", a, b);
    }
}

/// Higher-order function taking closure
pub fn apply_twice<F>(f: F, x: i32) -> i32
where
    F: Fn(i32) -> i32,
{
    f(f(x))
}

/// Function returning closure
pub fn make_multiplier(factor: i32) -> impl Fn(i32) -> i32 {
    move |x| x * factor
}

/// Recursive function
pub fn factorial(n: u32) -> u32 {
    match n {
        0 | 1 => 1,
        _ => n * factorial(n - 1),
    }
}

/// Fibonacci using recursion
pub fn fibonacci(n: u32) -> u32 {
    match n {
        0 => 0,
        1 => 1,
        _ => fibonacci(n - 1) + fibonacci(n - 2),
    }
}

/// Function with slice parameter
pub fn sum_slice(numbers: &[i32]) -> i32 {
    numbers.iter().sum()
}

/// Function with vector parameter (takes ownership)
pub fn sort_vector(mut vec: Vec<i32>) -> Vec<i32> {
    vec.sort();
    vec
}

/// Function demonstrating early return
pub fn validate_age(age: i32) -> Result<i32, String> {
    if age < 0 {
        return Err("Age cannot be negative".to_string());
    }
    if age > 150 {
        return Err("Age is unrealistic".to_string());
    }
    Ok(age)
}

/// Function with default parameters using Option
pub fn greet(name: &str, title: Option<&str>) -> String {
    match title {
        Some(t) => format!("Hello, {} {}", t, name),
        None => format!("Hello, {}", name),
    }
}

/// Variadic-like function using slice
pub fn sum_all(numbers: &[i32]) -> i32 {
    numbers.iter().sum()
}

/// Function with multiple lifetimes
pub fn first_word<'a, 'b>(s1: &'a str, s2: &'b str) -> &'a str {
    s1.split_whitespace().next().unwrap_or(s1)
}

/// Associated function (like static method)
pub fn from_string(s: String) -> Result<i32, std::num::ParseIntError> {
    s.parse()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_function() {
        assert_eq!(simple_function(5), 10);
    }

    #[test]
    fn test_multiple_returns() {
        let (sum, diff, prod) = multiple_returns(10, 3);
        assert_eq!(sum, 13);
        assert_eq!(diff, 7);
        assert_eq!(prod, 30);
    }

    #[test]
    fn test_divide() {
        assert_eq!(divide(10, 2), Ok(5));
        assert!(divide(10, 0).is_err());
    }

    #[test]
    fn test_factorial() {
        assert_eq!(factorial(5), 120);
    }
}


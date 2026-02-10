// iterators_closures.rs - Demonstrates Rust iterators and closures
use std::collections::HashMap;

// Closure examples

/// Function taking closure as parameter
pub fn apply<F>(f: F, x: i32) -> i32
where
    F: Fn(i32) -> i32,
{
    f(x)
}

/// Function returning closure
pub fn make_adder(n: i32) -> impl Fn(i32) -> i32 {
    move |x| x + n
}

/// Closure capturing environment
pub fn closure_capture() {
    let factor = 5;
    let multiply = |x| x * factor;
    println!("Result: {}", multiply(10));
}

/// Closure with move
pub fn closure_move() -> Box<dyn Fn(i32) -> i32> {
    let factor = 5;
    Box::new(move |x| x * factor)
}

/// FnOnce closure (consumes captured values)
pub fn call_once<F>(f: F)
where
    F: FnOnce(),
{
    f();
}

/// FnMut closure (mutates captured values)
pub fn call_mut<F>(mut f: F)
where
    F: FnMut(),
{
    f();
    f();
}

// Iterator examples

/// Custom iterator
pub struct Counter {
    count: u32,
    max: u32,
}

impl Counter {
    pub fn new(max: u32) -> Self {
        Self { count: 0, max }
    }
}

impl Iterator for Counter {
    type Item = u32;

    fn next(&mut self) -> Option<Self::Item> {
        if self.count < self.max {
            self.count += 1;
            Some(self.count)
        } else {
            None
        }
    }
}

/// Range iterator wrapper
pub struct Range {
    start: i32,
    end: i32,
    current: i32,
}

impl Range {
    pub fn new(start: i32, end: i32) -> Self {
        Self {
            start,
            end,
            current: start,
        }
    }
}

impl Iterator for Range {
    type Item = i32;

    fn next(&mut self) -> Option<Self::Item> {
        if self.current < self.end {
            let result = self.current;
            self.current += 1;
            Some(result)
        } else {
            None
        }
    }
}

// Iterator adapter patterns

/// Map pattern
pub fn double_numbers(numbers: Vec<i32>) -> Vec<i32> {
    numbers.iter().map(|&x| x * 2).collect()
}

/// Filter pattern
pub fn filter_evens(numbers: Vec<i32>) -> Vec<i32> {
    numbers.into_iter().filter(|&x| x % 2 == 0).collect()
}

/// Filter and map combined
pub fn process_numbers(numbers: Vec<i32>) -> Vec<i32> {
    numbers
        .into_iter()
        .filter(|&x| x > 0)
        .map(|x| x * 2)
        .collect()
}

/// Fold/reduce pattern
pub fn sum_numbers(numbers: &[i32]) -> i32 {
    numbers.iter().fold(0, |acc, &x| acc + x)
}

/// Find pattern
pub fn find_first_even(numbers: &[i32]) -> Option<i32> {
    numbers.iter().find(|&&x| x % 2 == 0).copied()
}

/// Any and all
pub fn has_negative(numbers: &[i32]) -> bool {
    numbers.iter().any(|&x| x < 0)
}

pub fn all_positive(numbers: &[i32]) -> bool {
    numbers.iter().all(|&x| x > 0)
}

/// Take and skip
pub fn take_first_n(numbers: Vec<i32>, n: usize) -> Vec<i32> {
    numbers.into_iter().take(n).collect()
}

pub fn skip_first_n(numbers: Vec<i32>, n: usize) -> Vec<i32> {
    numbers.into_iter().skip(n).collect()
}

/// Chain iterators
pub fn chain_vectors(v1: Vec<i32>, v2: Vec<i32>) -> Vec<i32> {
    v1.into_iter().chain(v2.into_iter()).collect()
}

/// Zip iterators
pub fn zip_vectors(v1: Vec<i32>, v2: Vec<i32>) -> Vec<(i32, i32)> {
    v1.into_iter().zip(v2.into_iter()).collect()
}

/// Enumerate
pub fn enumerate_items(items: Vec<String>) -> Vec<(usize, String)> {
    items.into_iter().enumerate().collect()
}

/// Flat map
pub fn flat_map_example(nested: Vec<Vec<i32>>) -> Vec<i32> {
    nested.into_iter().flat_map(|v| v.into_iter()).collect()
}

/// Partition
pub fn partition_numbers(numbers: Vec<i32>) -> (Vec<i32>, Vec<i32>) {
    numbers.into_iter().partition(|&x| x % 2 == 0)
}

// Complex iterator chains

/// Multiple operations
pub fn complex_pipeline(numbers: Vec<i32>) -> i32 {
    numbers
        .into_iter()
        .filter(|&x| x > 0)
        .map(|x| x * 2)
        .filter(|&x| x < 100)
        .fold(0, |acc, x| acc + x)
}

/// Group by pattern (using HashMap)
pub fn group_by_parity(numbers: Vec<i32>) -> HashMap<bool, Vec<i32>> {
    let mut map = HashMap::new();
    for num in numbers {
        let is_even = num % 2 == 0;
        map.entry(is_even).or_insert_with(Vec::new).push(num);
    }
    map
}

/// Max and min
pub fn find_extremes(numbers: &[i32]) -> (Option<i32>, Option<i32>) {
    let max = numbers.iter().max().copied();
    let min = numbers.iter().min().copied();
    (max, min)
}

/// Collect into different types
pub fn collect_examples(numbers: Vec<i32>) -> (Vec<i32>, String) {
    let vec: Vec<i32> = numbers.iter().map(|&x| x * 2).collect();
    let string: String = numbers
        .iter()
        .map(|x| x.to_string())
        .collect::<Vec<String>>()
        .join(", ");
    (vec, string)
}

// Custom iterator adapters

pub struct StepBy {
    iter: std::vec::IntoIter<i32>,
    step: usize,
}

impl StepBy {
    pub fn new(vec: Vec<i32>, step: usize) -> Self {
        Self {
            iter: vec.into_iter(),
            step,
        }
    }
}

impl Iterator for StepBy {
    type Item = i32;

    fn next(&mut self) -> Option<Self::Item> {
        let result = self.iter.next()?;
        for _ in 0..self.step - 1 {
            self.iter.next();
        }
        Some(result)
    }
}

// Lazy evaluation demonstration

pub struct LazyMap<I, F> {
    iter: I,
    f: F,
}

impl<I, F, T, U> Iterator for LazyMap<I, F>
where
    I: Iterator<Item = T>,
    F: FnMut(T) -> U,
{
    type Item = U;

    fn next(&mut self) -> Option<Self::Item> {
        self.iter.next().map(|x| (self.f)(x))
    }
}

// Infinite iterators

pub fn fibonacci_iterator() -> impl Iterator<Item = u64> {
    let mut a = 0;
    let mut b = 1;
    std::iter::from_fn(move || {
        let result = a;
        let next = a + b;
        a = b;
        b = next;
        Some(result)
    })
}

/// Take from infinite iterator
pub fn first_n_fibonacci(n: usize) -> Vec<u64> {
    fibonacci_iterator().take(n).collect()
}

// Peekable iterator
pub fn peek_example(numbers: Vec<i32>) -> Vec<i32> {
    let mut iter = numbers.into_iter().peekable();
    let mut result = Vec::new();

    while let Some(&next) = iter.peek() {
        if next % 2 == 0 {
            result.push(iter.next().unwrap());
        } else {
            iter.next();
        }
    }

    result
}

// Cycle iterator
pub fn cycle_example(items: Vec<i32>, count: usize) -> Vec<i32> {
    items.into_iter().cycle().take(count).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_counter() {
        let counter = Counter::new(5);
        let result: Vec<u32> = counter.collect();
        assert_eq!(result, vec![1, 2, 3, 4, 5]);
    }

    #[test]
    fn test_double_numbers() {
        let numbers = vec![1, 2, 3, 4, 5];
        let doubled = double_numbers(numbers);
        assert_eq!(doubled, vec![2, 4, 6, 8, 10]);
    }

    #[test]
    fn test_filter_evens() {
        let numbers = vec![1, 2, 3, 4, 5, 6];
        let evens = filter_evens(numbers);
        assert_eq!(evens, vec![2, 4, 6]);
    }

    #[test]
    fn test_sum_numbers() {
        let numbers = vec![1, 2, 3, 4, 5];
        assert_eq!(sum_numbers(&numbers), 15);
    }

    #[test]
    fn test_make_adder() {
        let add_five = make_adder(5);
        assert_eq!(add_five(10), 15);
    }

    #[test]
    fn test_fibonacci() {
        let fibs = first_n_fibonacci(10);
        assert_eq!(fibs, vec![0, 1, 1, 2, 3, 5, 8, 13, 21, 34]);
    }
}


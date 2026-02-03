// generics.rs - Demonstrates Rust generics and type parameters
use std::cmp::PartialOrd;
use std::fmt::{Debug, Display};
use std::ops::Add;

/// Generic function with single type parameter
pub fn first<T>(list: &[T]) -> Option<&T> {
    list.first()
}

/// Generic function with trait bound
pub fn largest<T: PartialOrd>(list: &[T]) -> Option<&T> {
    if list.is_empty() {
        return None;
    }

    let mut largest = &list[0];
    for item in list {
        if item > largest {
            largest = item;
        }
    }
    Some(largest)
}

/// Generic function with multiple type parameters
pub fn pair<T, U>(first: T, second: U) -> (T, U) {
    (first, second)
}

/// Generic function with multiple trait bounds
pub fn print_pair<T: Display, U: Display>(first: T, second: U) {
    println!("First: {}, Second: {}", first, second);
}

/// Generic function with where clause
pub fn complex_function<T, U>(t: T, u: U) -> String
where
    T: Display + Clone,
    U: Display + Debug,
{
    format!("T: {}, U: {:?}", t, u)
}

// Generic structs

/// Simple generic struct
#[derive(Debug, Clone)]
pub struct Point<T> {
    pub x: T,
    pub y: T,
}

impl<T> Point<T> {
    pub fn new(x: T, y: T) -> Self {
        Self { x, y }
    }

    pub fn x(&self) -> &T {
        &self.x
    }

    pub fn y(&self) -> &T {
        &self.y
    }
}

impl<T: Add<Output = T> + Copy> Point<T> {
    pub fn add(&self, other: &Point<T>) -> Point<T> {
        Point {
            x: self.x + other.x,
            y: self.y + other.y,
        }
    }
}

/// Generic struct with multiple type parameters
#[derive(Debug)]
pub struct Pair<T, U> {
    pub first: T,
    pub second: U,
}

impl<T, U> Pair<T, U> {
    pub fn new(first: T, second: U) -> Self {
        Self { first, second }
    }

    pub fn swap(self) -> Pair<U, T> {
        Pair {
            first: self.second,
            second: self.first,
        }
    }
}

impl<T: Clone, U: Clone> Pair<T, U> {
    pub fn clone_first(&self) -> T {
        self.first.clone()
    }

    pub fn clone_second(&self) -> U {
        self.second.clone()
    }
}

// Generic collections

/// Generic stack
#[derive(Debug)]
pub struct Stack<T> {
    items: Vec<T>,
}

impl<T> Stack<T> {
    pub fn new() -> Self {
        Self { items: Vec::new() }
    }

    pub fn push(&mut self, item: T) {
        self.items.push(item);
    }

    pub fn pop(&mut self) -> Option<T> {
        self.items.pop()
    }

    pub fn peek(&self) -> Option<&T> {
        self.items.last()
    }

    pub fn is_empty(&self) -> bool {
        self.items.is_empty()
    }

    pub fn len(&self) -> usize {
        self.items.len()
    }
}

/// Generic queue
#[derive(Debug)]
pub struct Queue<T> {
    items: Vec<T>,
}

impl<T> Queue<T> {
    pub fn new() -> Self {
        Self { items: Vec::new() }
    }

    pub fn enqueue(&mut self, item: T) {
        self.items.push(item);
    }

    pub fn dequeue(&mut self) -> Option<T> {
        if self.items.is_empty() {
            None
        } else {
            Some(self.items.remove(0))
        }
    }

    pub fn peek(&self) -> Option<&T> {
        self.items.first()
    }

    pub fn len(&self) -> usize {
        self.items.len()
    }
}

/// Generic linked list node
#[derive(Debug)]
pub struct Node<T> {
    pub value: T,
    pub next: Option<Box<Node<T>>>,
}

impl<T> Node<T> {
    pub fn new(value: T) -> Self {
        Self { value, next: None }
    }
}

/// Generic linked list
#[derive(Debug)]
pub struct LinkedList<T> {
    head: Option<Box<Node<T>>>,
    size: usize,
}

impl<T> LinkedList<T> {
    pub fn new() -> Self {
        Self {
            head: None,
            size: 0,
        }
    }

    pub fn push(&mut self, value: T) {
        let new_node = Box::new(Node {
            value,
            next: self.head.take(),
        });
        self.head = Some(new_node);
        self.size += 1;
    }

    pub fn pop(&mut self) -> Option<T> {
        self.head.take().map(|node| {
            self.head = node.next;
            self.size -= 1;
            node.value
        })
    }

    pub fn len(&self) -> usize {
        self.size
    }

    pub fn is_empty(&self) -> bool {
        self.size == 0
    }
}

// Generic enums

/// Generic Option-like enum
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Maybe<T> {
    Just(T),
    Nothing,
}

impl<T> Maybe<T> {
    pub fn is_just(&self) -> bool {
        matches!(self, Maybe::Just(_))
    }

    pub fn unwrap(self) -> T {
        match self {
            Maybe::Just(value) => value,
            Maybe::Nothing => panic!("Called unwrap on Nothing"),
        }
    }

    pub fn unwrap_or(self, default: T) -> T {
        match self {
            Maybe::Just(value) => value,
            Maybe::Nothing => default,
        }
    }

    pub fn map<U, F>(self, f: F) -> Maybe<U>
    where
        F: FnOnce(T) -> U,
    {
        match self {
            Maybe::Just(value) => Maybe::Just(f(value)),
            Maybe::Nothing => Maybe::Nothing,
        }
    }
}

/// Generic Result-like enum
#[derive(Debug, Clone, PartialEq)]
pub enum Outcome<T, E> {
    Success(T),
    Failure(E),
}

impl<T, E> Outcome<T, E> {
    pub fn is_success(&self) -> bool {
        matches!(self, Outcome::Success(_))
    }

    pub fn map<U, F>(self, f: F) -> Outcome<U, E>
    where
        F: FnOnce(T) -> U,
    {
        match self {
            Outcome::Success(value) => Outcome::Success(f(value)),
            Outcome::Failure(err) => Outcome::Failure(err),
        }
    }

    pub fn and_then<U, F>(self, f: F) -> Outcome<U, E>
    where
        F: FnOnce(T) -> Outcome<U, E>,
    {
        match self {
            Outcome::Success(value) => f(value),
            Outcome::Failure(err) => Outcome::Failure(err),
        }
    }
}

// Generic trait implementations

/// Generic wrapper type
#[derive(Debug, Clone)]
pub struct Wrapper<T> {
    value: T,
}

impl<T> Wrapper<T> {
    pub fn new(value: T) -> Self {
        Self { value }
    }

    pub fn into_inner(self) -> T {
        self.value
    }

    pub fn get(&self) -> &T {
        &self.value
    }

    pub fn get_mut(&mut self) -> &mut T {
        &mut self.value
    }
}

impl<T: Display> Display for Wrapper<T> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Wrapper({})", self.value)
    }
}

// Generic functions with closures

/// Map function for vectors
pub fn map<T, U, F>(vec: Vec<T>, f: F) -> Vec<U>
where
    F: Fn(T) -> U,
{
    vec.into_iter().map(f).collect()
}

/// Filter function for vectors
pub fn filter<T, F>(vec: Vec<T>, predicate: F) -> Vec<T>
where
    F: Fn(&T) -> bool,
{
    vec.into_iter().filter(|x| predicate(x)).collect()
}

/// Reduce/fold function
pub fn reduce<T, U, F>(vec: Vec<T>, initial: U, f: F) -> U
where
    F: Fn(U, T) -> U,
{
    vec.into_iter().fold(initial, f)
}

// Const generics (Rust 1.51+)

/// Array wrapper with const generic size
#[derive(Debug)]
pub struct FixedArray<T, const N: usize> {
    data: [T; N],
}

impl<T: Default + Copy, const N: usize> FixedArray<T, N> {
    pub fn new() -> Self {
        Self {
            data: [T::default(); N],
        }
    }

    pub fn get(&self, index: usize) -> Option<&T> {
        self.data.get(index)
    }

    pub fn set(&mut self, index: usize, value: T) -> Result<(), String> {
        if index < N {
            self.data[index] = value;
            Ok(())
        } else {
            Err("Index out of bounds".to_string())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_largest() {
        let numbers = vec![34, 50, 25, 100, 65];
        assert_eq!(largest(&numbers), Some(&100));
    }

    #[test]
    fn test_point_add() {
        let p1 = Point::new(1, 2);
        let p2 = Point::new(3, 4);
        let p3 = p1.add(&p2);
        assert_eq!(p3.x, 4);
        assert_eq!(p3.y, 6);
    }

    #[test]
    fn test_stack() {
        let mut stack = Stack::new();
        stack.push(1);
        stack.push(2);
        stack.push(3);
        assert_eq!(stack.pop(), Some(3));
        assert_eq!(stack.len(), 2);
    }

    #[test]
    fn test_maybe() {
        let just = Maybe::Just(42);
        let nothing: Maybe<i32> = Maybe::Nothing;
        
        assert!(just.is_just());
        assert!(!nothing.is_just());
        assert_eq!(just.unwrap(), 42);
    }
}


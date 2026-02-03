// smart_pointers.rs - Demonstrates Rust smart pointers
use std::cell::{Cell, RefCell};
use std::rc::{Rc, Weak};
use std::sync::Arc;

// Box - heap allocation

/// Basic Box usage
pub fn box_example() -> Box<i32> {
    Box::new(42)
}

/// Recursive type with Box
#[derive(Debug)]
pub enum List {
    Cons(i32, Box<List>),
    Nil,
}

impl List {
    pub fn new() -> Self {
        List::Nil
    }

    pub fn prepend(self, value: i32) -> Self {
        List::Cons(value, Box::new(self))
    }

    pub fn len(&self) -> usize {
        match self {
            List::Cons(_, tail) => 1 + tail.len(),
            List::Nil => 0,
        }
    }
}

/// Box with trait object
pub trait Shape {
    fn area(&self) -> f64;
}

pub struct Circle {
    radius: f64,
}

pub struct Rectangle {
    width: f64,
    height: f64,
}

impl Shape for Circle {
    fn area(&self) -> f64 {
        std::f64::consts::PI * self.radius * self.radius
    }
}

impl Shape for Rectangle {
    fn area(&self) -> f64 {
        self.width * self.height
    }
}

pub fn create_shapes() -> Vec<Box<dyn Shape>> {
    vec![
        Box::new(Circle { radius: 5.0 }),
        Box::new(Rectangle {
            width: 10.0,
            height: 5.0,
        }),
    ]
}

// Rc - reference counting

/// Shared ownership with Rc
pub fn rc_example() {
    let data = Rc::new(vec![1, 2, 3, 4, 5]);
    let data2 = Rc::clone(&data);
    let data3 = Rc::clone(&data);

    println!("Data: {:?}, count: {}", data, Rc::strong_count(&data));
}

/// Graph structure with Rc
#[derive(Debug)]
pub struct Node {
    value: i32,
    children: Vec<Rc<Node>>,
}

impl Node {
    pub fn new(value: i32) -> Rc<Self> {
        Rc::new(Self {
            value,
            children: Vec::new(),
        })
    }

    pub fn value(&self) -> i32 {
        self.value
    }
}

/// Tree with Rc and Weak
#[derive(Debug)]
pub struct TreeNode {
    value: i32,
    parent: RefCell<Weak<TreeNode>>,
    children: RefCell<Vec<Rc<TreeNode>>>,
}

impl TreeNode {
    pub fn new(value: i32) -> Rc<Self> {
        Rc::new(Self {
            value,
            parent: RefCell::new(Weak::new()),
            children: RefCell::new(Vec::new()),
        })
    }

    pub fn add_child(self: &Rc<Self>, child: Rc<TreeNode>) {
        *child.parent.borrow_mut() = Rc::downgrade(self);
        self.children.borrow_mut().push(child);
    }
}

// RefCell - interior mutability

/// RefCell for interior mutability
pub struct MockMessenger {
    pub sent_messages: RefCell<Vec<String>>,
}

impl MockMessenger {
    pub fn new() -> Self {
        Self {
            sent_messages: RefCell::new(Vec::new()),
        }
    }

    pub fn send(&self, message: &str) {
        self.sent_messages.borrow_mut().push(message.to_string());
    }

    pub fn message_count(&self) -> usize {
        self.sent_messages.borrow().len()
    }
}

/// Combining Rc and RefCell
pub struct SharedData {
    data: Rc<RefCell<Vec<i32>>>,
}

impl SharedData {
    pub fn new() -> Self {
        Self {
            data: Rc::new(RefCell::new(Vec::new())),
        }
    }

    pub fn add(&self, value: i32) {
        self.data.borrow_mut().push(value);
    }

    pub fn get(&self, index: usize) -> Option<i32> {
        self.data.borrow().get(index).copied()
    }

    pub fn clone_ref(&self) -> SharedData {
        SharedData {
            data: Rc::clone(&self.data),
        }
    }
}

// Cell - for Copy types

pub struct CellExample {
    value: Cell<i32>,
}

impl CellExample {
    pub fn new(value: i32) -> Self {
        Self {
            value: Cell::new(value),
        }
    }

    pub fn get(&self) -> i32 {
        self.value.get()
    }

    pub fn set(&self, value: i32) {
        self.value.set(value);
    }

    pub fn increment(&self) {
        let current = self.value.get();
        self.value.set(current + 1);
    }
}

// Weak references

pub fn weak_reference_example() {
    let strong = Rc::new(42);
    let weak = Rc::downgrade(&strong);

    println!("Strong count: {}", Rc::strong_count(&strong));
    println!("Weak count: {}", Rc::weak_count(&strong));

    match weak.upgrade() {
        Some(value) => println!("Value: {}", value),
        None => println!("Value has been dropped"),
    }
}

// Custom smart pointer

pub struct MyBox<T> {
    value: T,
}

impl<T> MyBox<T> {
    pub fn new(value: T) -> Self {
        Self { value }
    }
}

impl<T> std::ops::Deref for MyBox<T> {
    type Target = T;

    fn deref(&self) -> &Self::Target {
        &self.value
    }
}

impl<T> std::ops::DerefMut for MyBox<T> {
    fn deref_mut(&mut self) -> &mut Self::Target {
        &mut self.value
    }
}

// Drop trait

pub struct CustomDrop {
    data: String,
}

impl CustomDrop {
    pub fn new(data: String) -> Self {
        println!("Creating CustomDrop with: {}", data);
        Self { data }
    }
}

impl Drop for CustomDrop {
    fn drop(&mut self) {
        println!("Dropping CustomDrop with: {}", self.data);
    }
}

// Arc for thread-safe reference counting
use std::sync::Mutex;
use std::thread;

pub fn arc_example() {
    let data = Arc::new(Mutex::new(vec![1, 2, 3]));
    let mut handles = vec![];

    for i in 0..3 {
        let data = Arc::clone(&data);
        let handle = thread::spawn(move || {
            let mut data = data.lock().unwrap();
            data.push(i);
        });
        handles.push(handle);
    }

    for handle in handles {
        handle.join().unwrap();
    }

    println!("Result: {:?}", data.lock().unwrap());
}

// Cow - Clone on Write
use std::borrow::Cow;

pub fn cow_example(input: &str) -> Cow<str> {
    if input.contains(' ') {
        Cow::Owned(input.replace(' ', "_"))
    } else {
        Cow::Borrowed(input)
    }
}

pub fn cow_modify(mut data: Cow<[i32]>) -> Cow<[i32]> {
    data.to_mut().push(4);
    data
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_list() {
        let list = List::new().prepend(3).prepend(2).prepend(1);
        assert_eq!(list.len(), 3);
    }

    #[test]
    fn test_shared_data() {
        let data = SharedData::new();
        let data2 = data.clone_ref();
        
        data.add(1);
        data2.add(2);
        
        assert_eq!(data.get(0), Some(1));
        assert_eq!(data.get(1), Some(2));
        assert_eq!(data2.get(0), Some(1));
    }

    #[test]
    fn test_cell() {
        let cell = CellExample::new(5);
        assert_eq!(cell.get(), 5);
        cell.increment();
        assert_eq!(cell.get(), 6);
    }

    #[test]
    fn test_mock_messenger() {
        let messenger = MockMessenger::new();
        messenger.send("hello");
        messenger.send("world");
        assert_eq!(messenger.message_count(), 2);
    }

    #[test]
    fn test_cow() {
        let borrowed = cow_example("hello");
        assert!(matches!(borrowed, Cow::Borrowed(_)));
        
        let owned = cow_example("hello world");
        assert!(matches!(owned, Cow::Owned(_)));
    }
}


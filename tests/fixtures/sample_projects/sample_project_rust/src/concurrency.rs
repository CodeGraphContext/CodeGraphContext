// concurrency.rs - Demonstrates Rust concurrency patterns
use std::sync::{Arc, Mutex, RwLock, mpsc};
use std::thread;
use std::time::Duration;

/// Simple thread spawning
pub fn spawn_simple_thread() {
    let handle = thread::spawn(|| {
        for i in 1..5 {
            println!("Thread: {}", i);
            thread::sleep(Duration::from_millis(10));
        }
    });

    handle.join().unwrap();
}

/// Thread with move closure
pub fn thread_with_ownership() {
    let data = vec![1, 2, 3, 4, 5];
    
    let handle = thread::spawn(move || {
        println!("Thread got data: {:?}", data);
        data.iter().sum::<i32>()
    });

    let result = handle.join().unwrap();
    println!("Sum: {}", result);
}

/// Multiple threads
pub fn spawn_multiple_threads(count: usize) -> Vec<i32> {
    let mut handles = vec![];

    for i in 0..count {
        let handle = thread::spawn(move || {
            thread::sleep(Duration::from_millis(10));
            i as i32 * 2
        });
        handles.push(handle);
    }

    handles.into_iter().map(|h| h.join().unwrap()).collect()
}

// Mutex for shared state

/// Shared counter with Mutex
pub fn shared_counter(thread_count: usize) -> i32 {
    let counter = Arc::new(Mutex::new(0));
    let mut handles = vec![];

    for _ in 0..thread_count {
        let counter = Arc::clone(&counter);
        let handle = thread::spawn(move || {
            for _ in 0..100 {
                let mut num = counter.lock().unwrap();
                *num += 1;
            }
        });
        handles.push(handle);
    }

    for handle in handles {
        handle.join().unwrap();
    }

    let final_count = *counter.lock().unwrap();
    final_count
}

/// Safe data structure with Mutex
#[derive(Debug)]
pub struct SafeCounter {
    count: Arc<Mutex<i32>>,
}

impl SafeCounter {
    pub fn new() -> Self {
        Self {
            count: Arc::new(Mutex::new(0)),
        }
    }

    pub fn increment(&self) {
        let mut count = self.count.lock().unwrap();
        *count += 1;
    }

    pub fn get(&self) -> i32 {
        *self.count.lock().unwrap()
    }

    pub fn clone_counter(&self) -> SafeCounter {
        SafeCounter {
            count: Arc::clone(&self.count),
        }
    }
}

// RwLock for read-heavy workloads

/// Shared data with RwLock
pub struct SharedData {
    data: Arc<RwLock<Vec<i32>>>,
}

impl SharedData {
    pub fn new() -> Self {
        Self {
            data: Arc::new(RwLock::new(Vec::new())),
        }
    }

    pub fn add(&self, value: i32) {
        let mut data = self.data.write().unwrap();
        data.push(value);
    }

    pub fn get(&self, index: usize) -> Option<i32> {
        let data = self.data.read().unwrap();
        data.get(index).copied()
    }

    pub fn len(&self) -> usize {
        let data = self.data.read().unwrap();
        data.len()
    }

    pub fn clone_data(&self) -> SharedData {
        SharedData {
            data: Arc::clone(&self.data),
        }
    }
}

// Message passing with channels

/// Simple channel communication
pub fn simple_channel() {
    let (tx, rx) = mpsc::channel();

    thread::spawn(move || {
        let messages = vec!["hello", "from", "thread"];
        for msg in messages {
            tx.send(msg).unwrap();
            thread::sleep(Duration::from_millis(10));
        }
    });

    for received in rx {
        println!("Got: {}", received);
    }
}

/// Multiple producers
pub fn multiple_producers() -> Vec<String> {
    let (tx, rx) = mpsc::channel();
    let mut results = Vec::new();

    for i in 0..3 {
        let tx_clone = tx.clone();
        thread::spawn(move || {
            let message = format!("Message from thread {}", i);
            tx_clone.send(message).unwrap();
        });
    }

    drop(tx); // Drop original sender

    for received in rx {
        results.push(received);
    }

    results
}

/// Worker pool pattern
pub struct ThreadPool {
    workers: Vec<Worker>,
    sender: mpsc::Sender<Job>,
}

type Job = Box<dyn FnOnce() + Send + 'static>;

struct Worker {
    id: usize,
    thread: Option<thread::JoinHandle<()>>,
}

impl Worker {
    fn new(id: usize, receiver: Arc<Mutex<mpsc::Receiver<Job>>>) -> Worker {
        let thread = thread::spawn(move || loop {
            let job = receiver.lock().unwrap().recv();

            match job {
                Ok(job) => {
                    println!("Worker {} executing job", id);
                    job();
                }
                Err(_) => {
                    println!("Worker {} shutting down", id);
                    break;
                }
            }
        });

        Worker {
            id,
            thread: Some(thread),
        }
    }
}

impl ThreadPool {
    pub fn new(size: usize) -> ThreadPool {
        assert!(size > 0);

        let (sender, receiver) = mpsc::channel();
        let receiver = Arc::new(Mutex::new(receiver));
        let mut workers = Vec::with_capacity(size);

        for id in 0..size {
            workers.push(Worker::new(id, Arc::clone(&receiver)));
        }

        ThreadPool { workers, sender }
    }

    pub fn execute<F>(&self, f: F)
    where
        F: FnOnce() + Send + 'static,
    {
        let job = Box::new(f);
        self.sender.send(job).unwrap();
    }
}

impl Drop for ThreadPool {
    fn drop(&mut self) {
        for worker in &mut self.workers {
            if let Some(thread) = worker.thread.take() {
                thread.join().unwrap();
            }
        }
    }
}

// Barrier synchronization
use std::sync::Barrier;

pub fn barrier_example() {
    let barrier = Arc::new(Barrier::new(3));
    let mut handles = vec![];

    for i in 0..3 {
        let barrier = Arc::clone(&barrier);
        let handle = thread::spawn(move || {
            println!("Thread {} before barrier", i);
            barrier.wait();
            println!("Thread {} after barrier", i);
        });
        handles.push(handle);
    }

    for handle in handles {
        handle.join().unwrap();
    }
}

// Atomic operations
use std::sync::atomic::{AtomicUsize, Ordering};

pub struct AtomicCounter {
    count: AtomicUsize,
}

impl AtomicCounter {
    pub fn new() -> Self {
        Self {
            count: AtomicUsize::new(0),
        }
    }

    pub fn increment(&self) {
        self.count.fetch_add(1, Ordering::SeqCst);
    }

    pub fn get(&self) -> usize {
        self.count.load(Ordering::SeqCst)
    }
}

// Once initialization
use std::sync::Once;

static mut SINGLETON: Option<String> = None;
static INIT: Once = Once::new();

pub fn get_singleton() -> &'static String {
    unsafe {
        INIT.call_once(|| {
            SINGLETON = Some(String::from("Singleton instance"));
        });
        SINGLETON.as_ref().unwrap()
    }
}

// Scoped threads (Rust 1.63+)
pub fn scoped_threads() {
    let mut data = vec![1, 2, 3, 4, 5];

    thread::scope(|s| {
        s.spawn(|| {
            println!("Thread 1 can access data: {:?}", data);
        });

        s.spawn(|| {
            println!("Thread 2 can also access data: {:?}", data);
        });
    });

    data.push(6); // Can use data after scope
    println!("Final data: {:?}", data);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_shared_counter() {
        let result = shared_counter(5);
        assert_eq!(result, 500);
    }

    #[test]
    fn test_safe_counter() {
        let counter = SafeCounter::new();
        counter.increment();
        counter.increment();
        assert_eq!(counter.get(), 2);
    }

    #[test]
    fn test_shared_data() {
        let data = SharedData::new();
        data.add(1);
        data.add(2);
        data.add(3);
        assert_eq!(data.len(), 3);
        assert_eq!(data.get(1), Some(2));
    }

    #[test]
    fn test_atomic_counter() {
        let counter = AtomicCounter::new();
        counter.increment();
        counter.increment();
        assert_eq!(counter.get(), 2);
    }
}


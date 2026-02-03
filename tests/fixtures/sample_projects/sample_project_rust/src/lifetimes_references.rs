// lifetimes_references.rs - Demonstrates Rust lifetimes and references
use std::fmt::Display;

/// Function with explicit lifetime annotation
pub fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() {
        x
    } else {
        y
    }
}

/// Multiple lifetime parameters
pub fn first_word<'a, 'b>(x: &'a str, _y: &'b str) -> &'a str {
    x.split_whitespace().next().unwrap_or(x)
}

/// Lifetime with struct
#[derive(Debug)]
pub struct ImportantExcerpt<'a> {
    pub part: &'a str,
}

impl<'a> ImportantExcerpt<'a> {
    /// Lifetime elision in method
    pub fn level(&self) -> i32 {
        3
    }

    /// Method with lifetime annotation
    pub fn announce_and_return_part(&self, announcement: &str) -> &str {
        println!("Attention please: {}", announcement);
        self.part
    }
}

/// Struct with multiple lifetime parameters
#[derive(Debug)]
pub struct Context<'a, 'b> {
    pub primary: &'a str,
    pub secondary: &'b str,
}

impl<'a, 'b> Context<'a, 'b> {
    pub fn new(primary: &'a str, secondary: &'b str) -> Self {
        Self { primary, secondary }
    }

    pub fn get_primary(&self) -> &'a str {
        self.primary
    }

    pub fn get_secondary(&self) -> &'b str {
        self.secondary
    }
}

/// Static lifetime
pub fn static_string() -> &'static str {
    "This string has static lifetime"
}

/// Generic with lifetime and trait bound
pub fn longest_with_announcement<'a, T>(
    x: &'a str,
    y: &'a str,
    announcement: T,
) -> &'a str
where
    T: Display,
{
    println!("Announcement: {}", announcement);
    if x.len() > y.len() {
        x
    } else {
        y
    }
}

/// Reference to slice
pub fn first_element<'a, T>(slice: &'a [T]) -> Option<&'a T> {
    slice.first()
}

/// Mutable reference with lifetime
pub fn append_exclamation<'a>(s: &'a mut String) -> &'a str {
    s.push('!');
    s.as_str()
}

/// Struct holding references
#[derive(Debug)]
pub struct Book<'a> {
    pub title: &'a str,
    pub author: &'a str,
    pub year: u32,
}

impl<'a> Book<'a> {
    pub fn new(title: &'a str, author: &'a str, year: u32) -> Self {
        Self { title, author, year }
    }

    pub fn display(&self) -> String {
        format!("{} by {} ({})", self.title, self.author, self.year)
    }
}

/// Lifetime bounds
pub struct Ref<'a, T: 'a> {
    reference: &'a T,
}

impl<'a, T> Ref<'a, T> {
    pub fn new(reference: &'a T) -> Self {
        Self { reference }
    }

    pub fn get(&self) -> &'a T {
        self.reference
    }
}

/// Higher-ranked trait bounds (HRTBs)
pub fn call_with_ref<F>(f: F)
where
    F: for<'a> Fn(&'a str) -> &'a str,
{
    let s = String::from("Hello");
    let result = f(&s);
    println!("Result: {}", result);
}

/// Lifetime elision example 1
pub fn get_first_word(s: &str) -> &str {
    s.split_whitespace().next().unwrap_or("")
}

/// Lifetime elision example 2
pub fn parse_pair(s: &str) -> (&str, &str) {
    let parts: Vec<&str> = s.split(',').collect();
    if parts.len() >= 2 {
        (parts[0], parts[1])
    } else {
        ("", "")
    }
}

/// Struct with owned and borrowed data
#[derive(Debug)]
pub struct MixedData<'a> {
    pub owned: String,
    pub borrowed: &'a str,
}

impl<'a> MixedData<'a> {
    pub fn new(owned: String, borrowed: &'a str) -> Self {
        Self { owned, borrowed }
    }

    pub fn combine(&self) -> String {
        format!("{} {}", self.owned, self.borrowed)
    }
}

/// Iterator with lifetime
pub struct StrSplitter<'a> {
    remainder: &'a str,
    delimiter: char,
}

impl<'a> StrSplitter<'a> {
    pub fn new(s: &'a str, delimiter: char) -> Self {
        Self {
            remainder: s,
            delimiter,
        }
    }
}

impl<'a> Iterator for StrSplitter<'a> {
    type Item = &'a str;

    fn next(&mut self) -> Option<Self::Item> {
        if self.remainder.is_empty() {
            return None;
        }

        match self.remainder.find(self.delimiter) {
            Some(pos) => {
                let result = &self.remainder[..pos];
                self.remainder = &self.remainder[pos + 1..];
                Some(result)
            }
            None => {
                let result = self.remainder;
                self.remainder = "";
                Some(result)
            }
        }
    }
}

/// Lifetime with enum
#[derive(Debug)]
pub enum Either<'a, 'b> {
    Left(&'a str),
    Right(&'b str),
}

impl<'a, 'b> Either<'a, 'b> {
    pub fn get_value(&self) -> &str {
        match self {
            Either::Left(s) => s,
            Either::Right(s) => s,
        }
    }
}

/// Combining lifetimes
pub fn combine_strings<'a>(strings: &'a [&'a str], separator: &str) -> String {
    strings.join(separator)
}

/// Reference counting considerations (not strictly lifetimes but related)
use std::rc::Rc;

pub struct SharedData {
    pub data: Rc<String>,
}

impl SharedData {
    pub fn new(s: String) -> Self {
        Self {
            data: Rc::new(s),
        }
    }

    pub fn clone_ref(&self) -> SharedData {
        Self {
            data: Rc::clone(&self.data),
        }
    }
}

/// Comparing references with different lifetimes
pub fn compare_lengths<'a, 'b>(s1: &'a str, s2: &'b str) -> bool {
    s1.len() > s2.len()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_longest() {
        let s1 = "hello";
        let s2 = "hi";
        assert_eq!(longest(s1, s2), "hello");
    }

    #[test]
    fn test_important_excerpt() {
        let text = "This is a test. This is important.";
        let excerpt = ImportantExcerpt { part: text };
        assert_eq!(excerpt.level(), 3);
    }

    #[test]
    fn test_book() {
        let book = Book::new("1984", "George Orwell", 1949);
        assert!(book.display().contains("1984"));
    }

    #[test]
    fn test_str_splitter() {
        let text = "a,b,c";
        let splitter = StrSplitter::new(text, ',');
        let parts: Vec<&str> = splitter.collect();
        assert_eq!(parts, vec!["a", "b", "c"]);
    }
}


// generics.go - Demonstrates Go generics (Go 1.18+)
package main

import (
	"fmt"
	"golang.org/x/exp/constraints"
)

// GenericMax returns the maximum of two values
func GenericMax[T constraints.Ordered](a, b T) T {
	if a > b {
		return a
	}
	return b
}

// GenericMin returns the minimum of two values
func GenericMin[T constraints.Ordered](a, b T) T {
	if a < b {
		return a
	}
	return b
}

// Stack is a generic stack data structure
type Stack[T any] struct {
	items []T
}

// Push adds an item to the stack
func (s *Stack[T]) Push(item T) {
	s.items = append(s.items, item)
}

// Pop removes and returns the top item
func (s *Stack[T]) Pop() (T, bool) {
	if len(s.items) == 0 {
		var zero T
		return zero, false
	}
	item := s.items[len(s.items)-1]
	s.items = s.items[:len(s.items)-1]
	return item, true
}

// Peek returns the top item without removing it
func (s *Stack[T]) Peek() (T, bool) {
	if len(s.items) == 0 {
		var zero T
		return zero, false
	}
	return s.items[len(s.items)-1], true
}

// IsEmpty returns true if stack is empty
func (s *Stack[T]) IsEmpty() bool {
	return len(s.items) == 0
}

// Size returns the number of items in the stack
func (s *Stack[T]) Size() int {
	return len(s.items)
}

// Queue is a generic queue data structure
type Queue[T any] struct {
	items []T
}

// Enqueue adds an item to the queue
func (q *Queue[T]) Enqueue(item T) {
	q.items = append(q.items, item)
}

// Dequeue removes and returns the first item
func (q *Queue[T]) Dequeue() (T, bool) {
	if len(q.items) == 0 {
		var zero T
		return zero, false
	}
	item := q.items[0]
	q.items = q.items[1:]
	return item, true
}

// Map applies a function to each element
func Map[T any, U any](items []T, fn func(T) U) []U {
	result := make([]U, len(items))
	for i, item := range items {
		result[i] = fn(item)
	}
	return result
}

// Filter filters items based on a predicate
func Filter[T any](items []T, predicate func(T) bool) []T {
	var result []T
	for _, item := range items {
		if predicate(item) {
			result = append(result, item)
		}
	}
	return result
}

// Reduce reduces a slice to a single value
func Reduce[T any, U any](items []T, initial U, fn func(U, T) U) U {
	result := initial
	for _, item := range items {
		result = fn(result, item)
	}
	return result
}

// Contains checks if a slice contains an item
func Contains[T comparable](items []T, target T) bool {
	for _, item := range items {
		if item == target {
			return true
		}
	}
	return false
}

// Pair is a generic pair type
type Pair[T any, U any] struct {
	First  T
	Second U
}

// NewPair creates a new pair
func NewPair[T any, U any](first T, second U) Pair[T, U] {
	return Pair[T, U]{First: first, Second: second}
}

// Swap swaps the values in a pair
func (p Pair[T, U]) Swap() Pair[U, T] {
	return Pair[U, T]{First: p.Second, Second: p.First}
}

// LinkedListNode is a generic linked list node
type LinkedListNode[T any] struct {
	Value T
	Next  *LinkedListNode[T]
}

// LinkedList is a generic linked list
type LinkedList[T any] struct {
	Head *LinkedListNode[T]
	Tail *LinkedListNode[T]
	size int
}

// Append adds a value to the end of the list
func (ll *LinkedList[T]) Append(value T) {
	node := &LinkedListNode[T]{Value: value}
	if ll.Head == nil {
		ll.Head = node
		ll.Tail = node
	} else {
		ll.Tail.Next = node
		ll.Tail = node
	}
	ll.size++
}

// Prepend adds a value to the beginning of the list
func (ll *LinkedList[T]) Prepend(value T) {
	node := &LinkedListNode[T]{Value: value, Next: ll.Head}
	ll.Head = node
	if ll.Tail == nil {
		ll.Tail = node
	}
	ll.size++
}

// ToSlice converts the linked list to a slice
func (ll *LinkedList[T]) ToSlice() []T {
	result := make([]T, 0, ll.size)
	current := ll.Head
	for current != nil {
		result = append(result, current.Value)
		current = current.Next
	}
	return result
}

// Number constraint for numeric types
type Number interface {
	constraints.Integer | constraints.Float
}

// Sum calculates the sum of numbers
func Sum[T Number](numbers []T) T {
	var sum T
	for _, num := range numbers {
		sum += num
	}
	return sum
}

// Average calculates the average of numbers
func Average[T Number](numbers []T) float64 {
	if len(numbers) == 0 {
		return 0
	}
	total := Sum(numbers)
	return float64(total) / float64(len(numbers))
}

// Cache is a generic cache with type constraints
type Cache[K comparable, V any] struct {
	data map[K]V
}

// NewCache creates a new cache
func NewCache[K comparable, V any]() *Cache[K, V] {
	return &Cache[K, V]{
		data: make(map[K]V),
	}
}

// Set adds or updates a value in the cache
func (c *Cache[K, V]) Set(key K, value V) {
	c.data[key] = value
}

// Get retrieves a value from the cache
func (c *Cache[K, V]) Get(key K) (V, bool) {
	value, ok := c.data[key]
	return value, ok
}

// Delete removes a value from the cache
func (c *Cache[K, V]) Delete(key K) {
	delete(c.data, key)
}

// Keys returns all keys in the cache
func (c *Cache[K, V]) Keys() []K {
	keys := make([]K, 0, len(c.data))
	for k := range c.data {
		keys = append(keys, k)
	}
	return keys
}

// FindFirst returns the first item matching the predicate
func FindFirst[T any](items []T, predicate func(T) bool) (T, bool) {
	for _, item := range items {
		if predicate(item) {
			return item, true
		}
	}
	var zero T
	return zero, false
}

// GroupBy groups items by a key function
func GroupBy[T any, K comparable](items []T, keyFn func(T) K) map[K][]T {
	result := make(map[K][]T)
	for _, item := range items {
		key := keyFn(item)
		result[key] = append(result[key], item)
	}
	return result
}

func demonstrateGenerics() {
	// Generic functions
	fmt.Println("Max:", GenericMax(10, 20))
	fmt.Println("Max:", GenericMax(3.14, 2.71))
	
	// Generic stack
	stack := Stack[int]{}
	stack.Push(1)
	stack.Push(2)
	stack.Push(3)
	val, _ := stack.Pop()
	fmt.Println("Popped:", val)
	
	// Generic map/filter/reduce
	numbers := []int{1, 2, 3, 4, 5}
	doubled := Map(numbers, func(n int) int { return n * 2 })
	fmt.Println("Doubled:", doubled)
	
	evens := Filter(numbers, func(n int) bool { return n%2 == 0 })
	fmt.Println("Evens:", evens)
	
	sum := Reduce(numbers, 0, func(acc, n int) int { return acc + n })
	fmt.Println("Sum:", sum)
	
	// Generic cache
	cache := NewCache[string, int]()
	cache.Set("age", 30)
	age, _ := cache.Get("age")
	fmt.Println("Age:", age)
}


// advanced_types.go - Demonstrates advanced Go types
package main

import (
	"fmt"
	"sort"
)

// CustomString is a custom type based on string
type CustomString string

// Length returns the length of the custom string
func (cs CustomString) Length() int {
	return len(cs)
}

// ToUpper converts to uppercase
func (cs CustomString) ToUpper() CustomString {
	return CustomString(fmt.Sprintf("%s", cs))
}

// CustomInt is a custom numeric type
type CustomInt int

// IsEven checks if the number is even
func (ci CustomInt) IsEven() bool {
	return ci%2 == 0
}

// Double doubles the value
func (ci CustomInt) Double() CustomInt {
	return ci * 2
}

// Status is an enum-like type
type Status int

const (
	StatusPending Status = iota
	StatusActive
	StatusInactive
	StatusDeleted
)

// String implements Stringer interface for Status
func (s Status) String() string {
	return [...]string{"Pending", "Active", "Inactive", "Deleted"}[s]
}

// IsValid checks if status is valid
func (s Status) IsValid() bool {
	return s >= StatusPending && s <= StatusDeleted
}

// Priority represents priority levels
type Priority string

const (
	PriorityLow    Priority = "low"
	PriorityMedium Priority = "medium"
	PriorityHigh   Priority = "high"
)

// MapOperations demonstrates map operations
func MapOperations() map[string]int {
	// Initialize map
	scores := make(map[string]int)
	
	// Add elements
	scores["Alice"] = 95
	scores["Bob"] = 87
	scores["Charlie"] = 92
	
	// Check existence
	if val, ok := scores["Alice"]; ok {
		fmt.Printf("Alice's score: %d\n", val)
	}
	
	// Delete element
	delete(scores, "Bob")
	
	return scores
}

// NestedMap demonstrates nested maps
func NestedMap() map[string]map[string]int {
	users := make(map[string]map[string]int)
	
	users["user1"] = make(map[string]int)
	users["user1"]["age"] = 25
	users["user1"]["score"] = 100
	
	users["user2"] = map[string]int{
		"age":   30,
		"score": 95,
	}
	
	return users
}

// SliceOperations demonstrates slice operations
func SliceOperations() []int {
	// Create slice
	nums := []int{1, 2, 3, 4, 5}
	
	// Append
	nums = append(nums, 6, 7, 8)
	
	// Slice operations
	subset := nums[2:5]
	fmt.Println(subset)
	
	// Copy
	copied := make([]int, len(nums))
	copy(copied, nums)
	
	return copied
}

// SliceOfSlices demonstrates 2D slices
func SliceOfSlices() [][]int {
	matrix := [][]int{
		{1, 2, 3},
		{4, 5, 6},
		{7, 8, 9},
	}
	
	return matrix
}

// ArrayOperations demonstrates array operations
func ArrayOperations() [5]int {
	var arr [5]int
	arr[0] = 10
	arr[1] = 20
	
	// Array initialization
	arr2 := [5]int{1, 2, 3, 4, 5}
	
	return arr2
}

// StructWithTags demonstrates struct tags
type User struct {
	ID        int    `json:"id" db:"user_id"`
	Username  string `json:"username" db:"username" validate:"required"`
	Email     string `json:"email" db:"email" validate:"email"`
	Age       int    `json:"age,omitempty" db:"age"`
	IsActive  bool   `json:"is_active" db:"is_active"`
	Role      string `json:"role" db:"role" default:"user"`
}

// AnonymousStruct demonstrates anonymous structs
func AnonymousStruct() {
	person := struct {
		Name string
		Age  int
	}{
		Name: "John",
		Age:  30,
	}
	
	fmt.Printf("%+v\n", person)
}

// FunctionType is a function type
type FunctionType func(int, int) int

// ApplyOperation applies a function operation
func ApplyOperation(a, b int, op FunctionType) int {
	return op(a, b)
}

// MathOperations demonstrates function types
func MathOperations() {
	add := func(a, b int) int { return a + b }
	multiply := func(a, b int) int { return a * b }
	
	fmt.Println(ApplyOperation(5, 3, add))
	fmt.Println(ApplyOperation(5, 3, multiply))
}

// ChannelTypes demonstrates different channel types
func ChannelTypes() {
	// Unbuffered channel
	ch1 := make(chan int)
	
	// Buffered channel
	ch2 := make(chan string, 5)
	
	// Send-only channel (in function signature)
	go func(ch chan<- int) {
		ch <- 42
	}(ch1)
	
	// Receive-only channel (in function signature)
	go func(ch <-chan string) {
		<-ch
	}(ch2)
}

// SortableInts demonstrates custom sorting
type SortableInts []int

func (s SortableInts) Len() int           { return len(s) }
func (s SortableInts) Less(i, j int) bool { return s[i] < s[j] }
func (s SortableInts) Swap(i, j int)      { s[i], s[j] = s[j], s[i] }

// SortIntegers sorts integers using custom type
func SortIntegers(nums []int) []int {
	sortable := SortableInts(nums)
	sort.Sort(sortable)
	return nums
}

// ByAge implements sort for Person by age
type ByAge []Person

func (a ByAge) Len() int           { return len(a) }
func (a ByAge) Less(i, j int) bool { return a[i].Age < a[j].Age }
func (a ByAge) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }

// SortPeople sorts people by age
func SortPeople(people []Person) []Person {
	sort.Sort(ByAge(people))
	return people
}

// Result is a generic result type
type Result struct {
	Success bool
	Data    interface{}
	Error   error
}

// NewSuccessResult creates a success result
func NewSuccessResult(data interface{}) Result {
	return Result{
		Success: true,
		Data:    data,
		Error:   nil,
	}
}

// NewErrorResult creates an error result
func NewErrorResult(err error) Result {
	return Result{
		Success: false,
		Data:    nil,
		Error:   err,
	}
}

// PointerTypes demonstrates pointer operations
func PointerTypes() {
	x := 10
	ptr := &x
	
	fmt.Printf("Value: %d, Pointer: %p, Dereferenced: %d\n", x, ptr, *ptr)
	
	*ptr = 20
	fmt.Printf("Modified value: %d\n", x)
}

// PointerToStruct demonstrates pointer to struct
func PointerToStruct() *User {
	user := &User{
		ID:       1,
		Username: "john_doe",
		Email:    "john@example.com",
		Age:      30,
		IsActive: true,
	}
	
	return user
}

// TypeAlias demonstrates type aliasing
type UserID = int
type Username = string
type EmailAddress = string

// CreateUserWithAliases uses type aliases
func CreateUserWithAliases(id UserID, name Username, email EmailAddress) User {
	return User{
		ID:       id,
		Username: name,
		Email:    email,
	}
}

// InterfaceType demonstrates interface{} (any)
func InterfaceType(data interface{}) string {
	switch v := data.(type) {
	case int:
		return fmt.Sprintf("Integer: %d", v)
	case string:
		return fmt.Sprintf("String: %s", v)
	case []int:
		return fmt.Sprintf("Slice of ints: %v", v)
	case User:
		return fmt.Sprintf("User: %s", v.Username)
	default:
		return fmt.Sprintf("Unknown type: %T", v)
	}
}

// BitFlags demonstrates bit flags
type Permission uint8

const (
	PermissionRead Permission = 1 << iota
	PermissionWrite
	PermissionExecute
	PermissionDelete
)

// HasPermission checks if a permission is set
func HasPermission(perms Permission, perm Permission) bool {
	return perms&perm != 0
}

// AddPermission adds a permission
func AddPermission(perms Permission, perm Permission) Permission {
	return perms | perm
}

// RemovePermission removes a permission
func RemovePermission(perms Permission, perm Permission) Permission {
	return perms &^ perm
}

func demonstrateAdvancedTypes() {
	// Custom types
	cs := CustomString("hello")
	fmt.Println(cs.Length())
	
	ci := CustomInt(10)
	fmt.Println(ci.IsEven())
	
	// Enums
	status := StatusActive
	fmt.Println(status.String())
	
	// Maps
	scores := MapOperations()
	fmt.Println(scores)
	
	// Slices
	nums := SliceOperations()
	fmt.Println(nums)
	
	// Sorting
	sorted := SortIntegers([]int{5, 2, 8, 1, 9})
	fmt.Println(sorted)
}


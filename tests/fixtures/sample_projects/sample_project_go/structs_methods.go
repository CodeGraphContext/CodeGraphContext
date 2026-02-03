// structs_methods.go - Demonstrates Go structs and methods
package main

import "fmt"

// Person represents a basic struct
type Person struct {
	Name string
	Age  int
}

// Employee extends Person concept with additional fields
type Employee struct {
	Person
	ID       int
	Position string
	Salary   float64
}

// AnonymousFieldStruct uses anonymous fields
type AnonymousFieldStruct struct {
	string
	int
	bool
}

// PrivateFieldStruct demonstrates private fields
type PrivateFieldStruct struct {
	PublicField  string
	privateField int // unexported field
}

// NewPerson is a constructor function
func NewPerson(name string, age int) *Person {
	return &Person{
		Name: name,
		Age:  age,
	}
}

// Greet is a value receiver method
func (p Person) Greet() string {
	return fmt.Sprintf("Hello, my name is %s", p.Name)
}

// HaveBirthday is a pointer receiver method (modifies struct)
func (p *Person) HaveBirthday() {
	p.Age++
}

// IsAdult demonstrates method with return value
func (p Person) IsAdult() bool {
	return p.Age >= 18
}

// NewEmployee creates a new employee
func NewEmployee(name string, age, id int, position string) *Employee {
	return &Employee{
		Person: Person{
			Name: name,
			Age:  age,
		},
		ID:       id,
		Position: position,
	}
}

// GetDetails is a method on embedded struct
func (e Employee) GetDetails() string {
	return fmt.Sprintf("%s (%d) - %s [ID: %d]", e.Name, e.Age, e.Position, e.ID)
}

// Promote modifies employee position
func (e *Employee) Promote(newPosition string, newSalary float64) {
	e.Position = newPosition
	e.Salary = newSalary
}

// GivesRaise calculates new salary
func (e *Employee) GiveRaise(percentage float64) {
	e.Salary = e.Salary * (1 + percentage/100)
}

// SetPrivateField demonstrates accessing private fields through methods
func (p *PrivateFieldStruct) SetPrivateField(val int) {
	p.privateField = val
}

// GetPrivateField gets the private field value
func (p *PrivateFieldStruct) GetPrivateField() int {
	return p.privateField
}

// MethodCallingMethod demonstrates internal method calls
func (p Person) FullIntroduction() string {
	greeting := p.Greet()
	ageStatus := "minor"
	if p.IsAdult() {
		ageStatus = "adult"
	}
	return fmt.Sprintf("%s and I am a %s", greeting, ageStatus)
}

// CompareAge compares two persons
func (p Person) CompareAge(other Person) string {
	if p.Age > other.Age {
		return fmt.Sprintf("%s is older than %s", p.Name, other.Name)
	} else if p.Age < other.Age {
		return fmt.Sprintf("%s is younger than %s", p.Name, other.Name)
	}
	return fmt.Sprintf("%s and %s are the same age", p.Name, other.Name)
}

func demonstrateStructs() {
	person := NewPerson("Alice", 30)
	fmt.Println(person.Greet())
	person.HaveBirthday()
	
	employee := NewEmployee("Bob", 25, 1001, "Developer")
	employee.Promote("Senior Developer", 90000)
	fmt.Println(employee.GetDetails())
}


// embedded_composition.go - Demonstrates Go embedding and composition
package main

import "fmt"

// Base is a base struct
type Base struct {
	ID   int
	Name string
}

// GetID returns the ID
func (b Base) GetID() int {
	return b.ID
}

// GetName returns the name
func (b Base) GetName() string {
	return b.Name
}

// Describe provides a description
func (b Base) Describe() string {
	return fmt.Sprintf("Base{ID: %d, Name: %s}", b.ID, b.Name)
}

// Extended embeds Base and adds functionality
type Extended struct {
	Base
	Extra string
}

// Describe overrides the Base method
func (e Extended) Describe() string {
	return fmt.Sprintf("Extended{ID: %d, Name: %s, Extra: %s}", e.ID, e.Name, e.Extra)
}

// GetExtra returns the extra field
func (e Extended) GetExtra() string {
	return e.Extra
}

// Address represents a physical address
type Address struct {
	Street  string
	City    string
	ZipCode string
}

// FullAddress returns formatted address
func (a Address) FullAddress() string {
	return fmt.Sprintf("%s, %s %s", a.Street, a.City, a.ZipCode)
}

// ContactInfo has contact details
type ContactInfo struct {
	Email string
	Phone string
}

// GetContact returns contact string
func (c ContactInfo) GetContact() string {
	return fmt.Sprintf("Email: %s, Phone: %s", c.Email, c.Phone)
}

// Customer embeds multiple structs
type Customer struct {
	Base
	Address
	ContactInfo
	LoyaltyPoints int
}

// NewCustomer creates a new customer
func NewCustomer(id int, name, email string) *Customer {
	return &Customer{
		Base: Base{
			ID:   id,
			Name: name,
		},
		ContactInfo: ContactInfo{
			Email: email,
		},
	}
}

// GetFullInfo returns all customer info
func (c Customer) GetFullInfo() string {
	return fmt.Sprintf("%s | %s | Points: %d", 
		c.Describe(), c.GetContact(), c.LoyaltyPoints)
}

// Logger provides logging functionality
type Logger interface {
	Log(message string)
}

// ConsoleLogger logs to console
type ConsoleLogger struct {
	Prefix string
}

// Log implements Logger interface
func (cl ConsoleLogger) Log(message string) {
	fmt.Printf("[%s] %s\n", cl.Prefix, message)
}

// Service embeds a logger
type Service struct {
	Logger
	Name string
}

// Execute performs service action
func (s Service) Execute() {
	s.Log(fmt.Sprintf("Executing service: %s", s.Name))
}

// Timestamper adds timestamp functionality
type Timestamper struct {
	timestamp string
}

// SetTimestamp sets the timestamp
func (t *Timestamper) SetTimestamp(ts string) {
	t.timestamp = ts
}

// GetTimestamp gets the timestamp
func (t Timestamper) GetTimestamp() string {
	return t.timestamp
}

// Versioned adds version tracking
type Versioned struct {
	Version int
}

// IncrementVersion increases version
func (v *Versioned) IncrementVersion() {
	v.Version++
}

// GetVersion returns the version
func (v Versioned) GetVersion() int {
	return v.Version
}

// Document combines multiple embedded types
type Document struct {
	Timestamper
	Versioned
	Content string
	Author  string
}

// Update updates the document
func (d *Document) Update(content string) {
	d.Content = content
	d.IncrementVersion()
}

// GetInfo returns document info
func (d Document) GetInfo() string {
	return fmt.Sprintf("Version %d by %s at %s", 
		d.GetVersion(), d.Author, d.GetTimestamp())
}

// Reader interface
type Reader interface {
	Read() string
}

// Writer interface
type Writer interface {
	Write(data string) error
}

// ReadWriter combines interfaces
type ReadWriter interface {
	Reader
	Writer
}

// FileHandler implements ReadWriter
type FileHandler struct {
	Filename string
	buffer   string
}

// Read implements Reader
func (fh FileHandler) Read() string {
	return fh.buffer
}

// Write implements Writer
func (fh *FileHandler) Write(data string) error {
	fh.buffer = data
	return nil
}

// BufferedHandler embeds FileHandler
type BufferedHandler struct {
	FileHandler
	BufferSize int
}

// Flush clears the buffer
func (bh *BufferedHandler) Flush() {
	bh.buffer = ""
}

// Engine represents an engine
type Engine struct {
	Horsepower int
	Type       string
}

// Start starts the engine
func (e Engine) Start() string {
	return fmt.Sprintf("Starting %s engine with %d HP", e.Type, e.Horsepower)
}

// Wheels represents wheels
type Wheels struct {
	Count int
	Size  int
}

// Roll makes wheels roll
func (w Wheels) Roll() string {
	return fmt.Sprintf("Rolling on %d wheels of size %d", w.Count, w.Size)
}

// Car composes Engine and Wheels
type Car struct {
	Engine
	Wheels
	Make  string
	Model string
}

// Drive drives the car
func (c Car) Drive() string {
	return fmt.Sprintf("%s %s: %s, %s", 
		c.Make, c.Model, c.Start(), c.Roll())
}

// Metadata provides common metadata
type Metadata struct {
	CreatedBy string
	Tags      []string
}

// AddTag adds a tag
func (m *Metadata) AddTag(tag string) {
	m.Tags = append(m.Tags, tag)
}

// GetTags returns all tags
func (m Metadata) GetTags() []string {
	return m.Tags
}

// Article combines content and metadata
type Article struct {
	Metadata
	Title string
	Body  string
}

// Summary returns article summary
func (a Article) Summary() string {
	return fmt.Sprintf("'%s' by %s [%d tags]", 
		a.Title, a.CreatedBy, len(a.Tags))
}

// ConflictExample shows field name conflicts
type ConflictExample struct {
	Base
	Extended
}

// AccessConflict demonstrates accessing conflicting fields
func (c ConflictExample) AccessConflict() string {
	// Need to specify which embedded type's field to access
	return fmt.Sprintf("Base Name: %s, Extended Name: %s", 
		c.Base.Name, c.Extended.Name)
}

func demonstrateComposition() {
	// Basic embedding
	extended := Extended{
		Base:  Base{ID: 1, Name: "Test"},
		Extra: "Additional",
	}
	fmt.Println(extended.Describe())
	fmt.Println(extended.GetID()) // Promoted method from Base
	
	// Multiple embedding
	customer := NewCustomer(100, "John Doe", "john@example.com")
	customer.Street = "123 Main St"
	customer.City = "NYC"
	customer.Phone = "555-1234"
	fmt.Println(customer.GetFullInfo())
	
	// Interface embedding
	service := Service{
		Logger: ConsoleLogger{Prefix: "SVC"},
		Name:   "DataProcessor",
	}
	service.Execute()
	
	// Composition
	car := Car{
		Engine: Engine{Horsepower: 300, Type: "V8"},
		Wheels: Wheels{Count: 4, Size: 18},
		Make:   "Tesla",
		Model:  "Model S",
	}
	fmt.Println(car.Drive())
}


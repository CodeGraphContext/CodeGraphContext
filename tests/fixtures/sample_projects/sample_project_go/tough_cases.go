package tough

import (
	"fmt"
	"io"
)

/*
Tough Case 1: Implicit Interface Implementation
This struct implements io.Writer and io.Closer without any explicit declaration.
The indexer must detect that it satisfies these interfaces.
*/
type MockDevice struct {
	ID string
}

func (m *MockDevice) Write(p []byte) (n int, err error) {
	fmt.Printf("Device %s writing: %s\n", m.ID, string(p))
	return len(p), nil
}

func (m *MockDevice) Close() error {
	fmt.Printf("Device %s closed\n", m.ID)
	return nil
}

func UseDevice(w io.WriteCloser) {
	w.Write([]byte("hello"))
	w.Close()
}

/*
Tough Case 2: Init Functions
Go allows multiple init functions across files. The indexer should track these
as entry points or special initialization nodes.
*/
var GlobalState string

func init() {
	GlobalState = "initialized_phase_1"
}

func init() {
	GlobalState = "initialized_phase_2"
}

/*
Tough Case 3: Struct Embedding and Shadowing
Embedded fields can have their methods shadowed by the outer struct.
*/
type Base struct {
	Name string
}

func (b *Base) Describe() string {
	return "Base: " + b.Name
}

type Extended struct {
	Base // Embedded
	Age  int
}

// Shadowing the Describe method
func (e *Extended) Describe() string {
	return fmt.Sprintf("Extended: %s (Age: %d)", e.Base.Describe(), e.Age)
}

/*
Tough Case 4: Channel-based Relationships
Relationships between a sender and a receiver are often missed.
*/
func Coordinator() {
	ch := make(chan string)
	go Worker(ch)
	ch <- "task_start"
}

import "unsafe"

/*
Tough Case 5: Unsafe Pointer Arithmetic
Simulating access to a struct field or method via pointer offsets.
This is the "nuclear option" of breaking static analysis.
*/
type SecretData struct {
	visible string
	hidden  string
}

func (s *SecretData) Reveal() string {
	return s.hidden
}

func UnsafeAccess() {
	data := SecretData{visible: "public", hidden: "private"}
	
	// Accessing the 'hidden' field by calculating its offset from 'visible'
	// A static indexer will see no direct reference to the 'hidden' field.
	ptr := unsafe.Pointer(&data.visible)
	hiddenPtr := (*string)(unsafe.Pointer(uintptr(ptr) + unsafe.Offsetof(data.hidden)))
	
	fmt.Println("Accessed via unsafe:", *hiddenPtr)
}

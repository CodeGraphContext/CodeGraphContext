// interfaces.go - Demonstrates Go interfaces
package main

import (
	"fmt"
	"math"
)

// Shape is a basic interface
type Shape interface {
	Area() float64
	Perimeter() float64
}

// Drawable extends Shape interface
type Drawable interface {
	Shape
	Draw() string
}

// Named is a simple interface
type Named interface {
	GetName() string
}

// Circle implements Shape
type Circle struct {
	Radius float64
	Name   string
}

// Rectangle implements Shape
type Rectangle struct {
	Width  float64
	Height float64
	Name   string
}

// Triangle implements Shape
type Triangle struct {
	A, B, C float64
	Name    string
}

// Area implements Shape interface for Circle
func (c Circle) Area() float64 {
	return math.Pi * c.Radius * c.Radius
}

// Perimeter implements Shape interface for Circle
func (c Circle) Perimeter() float64 {
	return 2 * math.Pi * c.Radius
}

// Draw implements Drawable interface for Circle
func (c Circle) Draw() string {
	return fmt.Sprintf("Drawing circle with radius %.2f", c.Radius)
}

// GetName implements Named interface for Circle
func (c Circle) GetName() string {
	return c.Name
}

// Area implements Shape interface for Rectangle
func (r Rectangle) Area() float64 {
	return r.Width * r.Height
}

// Perimeter implements Shape interface for Rectangle
func (r Rectangle) Perimeter() float64 {
	return 2 * (r.Width + r.Height)
}

// Draw implements Drawable interface for Rectangle
func (r Rectangle) Draw() string {
	return fmt.Sprintf("Drawing rectangle %.2fx%.2f", r.Width, r.Height)
}

// GetName implements Named interface for Rectangle
func (r Rectangle) GetName() string {
	return r.Name
}

// Area implements Shape interface for Triangle
func (t Triangle) Area() float64 {
	// Heron's formula
	s := (t.A + t.B + t.C) / 2
	return math.Sqrt(s * (s - t.A) * (s - t.B) * (s - t.C))
}

// Perimeter implements Shape interface for Triangle
func (t Triangle) Perimeter() float64 {
	return t.A + t.B + t.C
}

// GetName implements Named interface for Triangle
func (t Triangle) GetName() string {
	return t.Name
}

// CalculateTotalArea accepts interface and calculates total
func CalculateTotalArea(shapes []Shape) float64 {
	total := 0.0
	for _, shape := range shapes {
		total += shape.Area()
	}
	return total
}

// PrintShapeInfo uses interface for polymorphism
func PrintShapeInfo(s Shape) {
	fmt.Printf("Area: %.2f, Perimeter: %.2f\n", s.Area(), s.Perimeter())
}

// DrawIfPossible uses type assertion
func DrawIfPossible(s Shape) string {
	if drawable, ok := s.(Drawable); ok {
		return drawable.Draw()
	}
	return "Shape is not drawable"
}

// DescribeShape uses type switch
func DescribeShape(s Shape) string {
	switch v := s.(type) {
	case Circle:
		return fmt.Sprintf("Circle with radius %.2f", v.Radius)
	case Rectangle:
		return fmt.Sprintf("Rectangle with dimensions %.2fx%.2f", v.Width, v.Height)
	case Triangle:
		return fmt.Sprintf("Triangle with sides %.2f, %.2f, %.2f", v.A, v.B, v.C)
	default:
		return "Unknown shape"
	}
}

// EmptyInterface demonstrates empty interface usage
func EmptyInterface(data interface{}) string {
	switch v := data.(type) {
	case int:
		return fmt.Sprintf("Integer: %d", v)
	case string:
		return fmt.Sprintf("String: %s", v)
	case Shape:
		return fmt.Sprintf("Shape with area: %.2f", v.Area())
	default:
		return fmt.Sprintf("Unknown type: %T", v)
	}
}

// InterfaceComposition demonstrates interface embedding
type ComplexShape interface {
	Shape
	Named
	Volume() float64
}

// ProcessShapes processes multiple shapes
func ProcessShapes(shapes ...Shape) map[string]float64 {
	results := make(map[string]float64)
	totalArea := 0.0
	totalPerimeter := 0.0
	
	for _, shape := range shapes {
		totalArea += shape.Area()
		totalPerimeter += shape.Perimeter()
	}
	
	results["total_area"] = totalArea
	results["total_perimeter"] = totalPerimeter
	results["count"] = float64(len(shapes))
	
	return results
}

func demonstrateInterfaces() {
	circle := Circle{Radius: 5.0, Name: "MyCircle"}
	rectangle := Rectangle{Width: 10.0, Height: 5.0, Name: "MyRectangle"}
	
	shapes := []Shape{circle, rectangle}
	fmt.Printf("Total area: %.2f\n", CalculateTotalArea(shapes))
	
	fmt.Println(DescribeShape(circle))
	fmt.Println(DrawIfPossible(circle))
}


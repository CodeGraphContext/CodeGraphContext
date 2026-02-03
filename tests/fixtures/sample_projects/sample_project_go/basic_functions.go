// basic_functions.go - Demonstrates basic Go function patterns
package main

import (
	"fmt"
	"math"
)

// SimpleFunction is a basic function with single return
func SimpleFunction(x int) int {
	return x * 2
}

// MultipleReturns demonstrates multiple return values
func MultipleReturns(a, b int) (int, int, error) {
	if b == 0 {
		return 0, 0, fmt.Errorf("division by zero")
	}
	return a + b, a - b, nil
}

// NamedReturns uses named return values
func NamedReturns(x, y int) (sum int, product int) {
	sum = x + y
	product = x * y
	return // naked return
}

// VariadicFunction accepts variable number of arguments
func VariadicFunction(prefix string, numbers ...int) string {
	result := prefix
	for _, num := range numbers {
		result += fmt.Sprintf(" %d", num)
	}
	return result
}

// HigherOrderFunction takes a function as parameter
func HigherOrderFunction(fn func(int) int, value int) int {
	return fn(value) + 10
}

// FunctionReturningFunction returns a closure
func FunctionReturningFunction(multiplier int) func(int) int {
	return func(x int) int {
		return x * multiplier
	}
}

// RecursiveFunction demonstrates recursion
func RecursiveFunction(n int) int {
	if n <= 1 {
		return 1
	}
	return n * RecursiveFunction(n-1)
}

// DeferExample shows defer usage
func DeferExample() string {
	defer fmt.Println("This runs last")
	fmt.Println("This runs first")
	return "Function complete"
}

// PanicRecoverExample demonstrates panic and recover
func PanicRecoverExample(shouldPanic bool) (result string) {
	defer func() {
		if r := recover(); r != nil {
			result = fmt.Sprintf("Recovered from: %v", r)
		}
	}()
	
	if shouldPanic {
		panic("something went wrong")
	}
	
	result = "No panic occurred"
	return
}

// MathHelper calls external package function
func MathHelper(x float64) float64 {
	return math.Sqrt(x)
}

// init function runs before main
func init() {
	fmt.Println("Initializing basic_functions package")
}

func main() {
	fmt.Println(SimpleFunction(5))
	sum, diff, _ := MultipleReturns(10, 3)
	fmt.Println(sum, diff)
	
	doubler := FunctionReturningFunction(2)
	fmt.Println(doubler(5))
}


// Package util provides utility functions for the sample project
package util

import (
	"fmt"
	"strings"
)

// StringUtils provides string utility functions
type StringUtils struct{}

// Reverse reverses a string
func (su StringUtils) Reverse(s string) string {
	runes := []rune(s)
	for i, j := 0, len(runes)-1; i < j; i, j = i+1, j-1 {
		runes[i], runes[j] = runes[j], runes[i]
	}
	return string(runes)
}

// IsPalindrome checks if a string is a palindrome
func (su StringUtils) IsPalindrome(s string) bool {
	s = strings.ToLower(strings.ReplaceAll(s, " ", ""))
	return s == su.Reverse(s)
}

// MathUtils provides math utility functions
type MathUtils struct{}

// Factorial calculates factorial
func (mu MathUtils) Factorial(n int) int {
	if n <= 1 {
		return 1
	}
	return n * mu.Factorial(n-1)
}

// Fibonacci calculates fibonacci number
func (mu MathUtils) Fibonacci(n int) int {
	if n <= 1 {
		return n
	}
	return mu.Fibonacci(n-1) + mu.Fibonacci(n-2)
}

// GCD calculates greatest common divisor
func (mu MathUtils) GCD(a, b int) int {
	for b != 0 {
		a, b = b, a%b
	}
	return a
}

// LCM calculates least common multiple
func (mu MathUtils) LCM(a, b int) int {
	return (a * b) / mu.GCD(a, b)
}

// SliceUtils provides slice utility functions
type SliceUtils struct{}

// Sum calculates sum of integers
func (su SliceUtils) Sum(nums []int) int {
	total := 0
	for _, num := range nums {
		total += num
	}
	return total
}

// Average calculates average
func (su SliceUtils) Average(nums []int) float64 {
	if len(nums) == 0 {
		return 0
	}
	return float64(su.Sum(nums)) / float64(len(nums))
}

// Max finds maximum value
func (su SliceUtils) Max(nums []int) int {
	if len(nums) == 0 {
		return 0
	}
	max := nums[0]
	for _, num := range nums {
		if num > max {
			max = num
		}
	}
	return max
}

// Min finds minimum value
func (su SliceUtils) Min(nums []int) int {
	if len(nums) == 0 {
		return 0
	}
	min := nums[0]
	for _, num := range nums {
		if num < min {
			min = num
		}
	}
	return min
}

// Unique removes duplicates from slice
func (su SliceUtils) Unique(nums []int) []int {
	seen := make(map[int]bool)
	result := []int{}
	
	for _, num := range nums {
		if !seen[num] {
			seen[num] = true
			result = append(result, num)
		}
	}
	
	return result
}

// Validator provides validation functions
type Validator struct{}

// IsEmail checks if string is valid email format (simplified)
func (v Validator) IsEmail(email string) bool {
	return strings.Contains(email, "@") && strings.Contains(email, ".")
}

// IsURL checks if string is valid URL format (simplified)
func (v Validator) IsURL(url string) bool {
	return strings.HasPrefix(url, "http://") || strings.HasPrefix(url, "https://")
}

// IsEmpty checks if string is empty or whitespace
func (v Validator) IsEmpty(s string) bool {
	return strings.TrimSpace(s) == ""
}

// Logger provides logging functionality
type Logger struct {
	Prefix string
}

// NewLogger creates a new logger
func NewLogger(prefix string) *Logger {
	return &Logger{Prefix: prefix}
}

// Info logs info message
func (l Logger) Info(message string) {
	fmt.Printf("[%s] INFO: %s\n", l.Prefix, message)
}

// Error logs error message
func (l Logger) Error(message string) {
	fmt.Printf("[%s] ERROR: %s\n", l.Prefix, message)
}

// Debug logs debug message
func (l Logger) Debug(message string) {
	fmt.Printf("[%s] DEBUG: %s\n", l.Prefix, message)
}

// Helper functions (package-level)

// Capitalize capitalizes first letter of string
func Capitalize(s string) string {
	if len(s) == 0 {
		return s
	}
	return strings.ToUpper(s[:1]) + s[1:]
}

// Truncate truncates string to specified length
func Truncate(s string, length int) string {
	if len(s) <= length {
		return s
	}
	return s[:length] + "..."
}

// Contains checks if slice contains value
func Contains(slice []string, value string) bool {
	for _, item := range slice {
		if item == value {
			return true
		}
	}
	return false
}

// Map applies function to each element
func Map(slice []int, fn func(int) int) []int {
	result := make([]int, len(slice))
	for i, v := range slice {
		result[i] = fn(v)
	}
	return result
}

// Filter filters slice based on predicate
func Filter(slice []int, predicate func(int) bool) []int {
	result := []int{}
	for _, v := range slice {
		if predicate(v) {
			result = append(result, v)
		}
	}
	return result
}


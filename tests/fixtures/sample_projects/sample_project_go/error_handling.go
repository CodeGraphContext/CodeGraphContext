// error_handling.go - Demonstrates Go error handling patterns
package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"strconv"
)

// CustomError is a custom error type
type CustomError struct {
	Code    int
	Message string
}

// Error implements error interface for CustomError
func (e *CustomError) Error() string {
	return fmt.Sprintf("Error %d: %s", e.Code, e.Message)
}

// ValidationError represents validation failures
type ValidationError struct {
	Field string
	Value interface{}
	Issue string
}

// Error implements error interface for ValidationError
func (e *ValidationError) Error() string {
	return fmt.Sprintf("validation failed for field '%s' with value '%v': %s", 
		e.Field, e.Value, e.Issue)
}

// NewCustomError creates a new custom error
func NewCustomError(code int, message string) error {
	return &CustomError{Code: code, Message: message}
}

// BasicErrorReturn demonstrates simple error return
func BasicErrorReturn(x int) (int, error) {
	if x < 0 {
		return 0, errors.New("negative number not allowed")
	}
	return x * 2, nil
}

// ErrorWithFormatting uses fmt.Errorf
func ErrorWithFormatting(name string, age int) error {
	if age < 0 {
		return fmt.Errorf("invalid age %d for person %s", age, name)
	}
	if name == "" {
		return fmt.Errorf("name cannot be empty")
	}
	return nil
}

// MultipleErrorChecks demonstrates multiple error checks
func MultipleErrorChecks(a, b int) (int, error) {
	if a < 0 {
		return 0, errors.New("first parameter cannot be negative")
	}
	if b == 0 {
		return 0, errors.New("second parameter cannot be zero")
	}
	if a > 1000 {
		return 0, errors.New("first parameter too large")
	}
	return a / b, nil
}

// ErrorWrapping demonstrates error wrapping (Go 1.13+)
func ErrorWrapping(filename string) error {
	if filename == "" {
		return fmt.Errorf("filename is empty")
	}
	
	_, err := os.Open(filename)
	if err != nil {
		return fmt.Errorf("failed to open file %s: %w", filename, err)
	}
	
	return nil
}

// ValidateUser validates user data
func ValidateUser(username string, age int) error {
	if len(username) < 3 {
		return &ValidationError{
			Field: "username",
			Value: username,
			Issue: "must be at least 3 characters",
		}
	}
	
	if age < 18 {
		return &ValidationError{
			Field: "age",
			Value: age,
			Issue: "must be 18 or older",
		}
	}
	
	return nil
}

// ParseAndValidate demonstrates error handling chain
func ParseAndValidate(input string) (int, error) {
	value, err := strconv.Atoi(input)
	if err != nil {
		return 0, fmt.Errorf("failed to parse input: %w", err)
	}
	
	if value < 0 {
		return 0, NewCustomError(400, "value must be non-negative")
	}
	
	if value > 100 {
		return 0, NewCustomError(400, "value must not exceed 100")
	}
	
	return value, nil
}

// ErrorTypeAssertion demonstrates error type checking
func ErrorTypeAssertion(err error) string {
	if err == nil {
		return "no error"
	}
	
	// Type assertion for custom error
	if customErr, ok := err.(*CustomError); ok {
		return fmt.Sprintf("Custom error with code: %d", customErr.Code)
	}
	
	// Type assertion for validation error
	if valErr, ok := err.(*ValidationError); ok {
		return fmt.Sprintf("Validation error on field: %s", valErr.Field)
	}
	
	return "unknown error type"
}

// ErrorsIs demonstrates errors.Is (Go 1.13+)
func ErrorsIs(err error) bool {
	return errors.Is(err, io.EOF)
}

// ErrorsAs demonstrates errors.As (Go 1.13+)
func ErrorsAs(err error) (*CustomError, bool) {
	var customErr *CustomError
	if errors.As(err, &customErr) {
		return customErr, true
	}
	return nil, false
}

// DeferredErrorHandling demonstrates defer with error handling
func DeferredErrorHandling(filename string) (err error) {
	file, err := os.Open(filename)
	if err != nil {
		return fmt.Errorf("cannot open file: %w", err)
	}
	
	defer func() {
		if closeErr := file.Close(); closeErr != nil {
			if err != nil {
				err = fmt.Errorf("close error: %v (original error: %w)", closeErr, err)
			} else {
				err = closeErr
			}
		}
	}()
	
	// Do something with file
	_, err = file.Read(make([]byte, 100))
	if err != nil && err != io.EOF {
		return fmt.Errorf("read error: %w", err)
	}
	
	return nil
}

// SentinelErrors demonstrates sentinel error pattern
var (
	ErrNotFound     = errors.New("not found")
	ErrUnauthorized = errors.New("unauthorized")
	ErrForbidden    = errors.New("forbidden")
)

// FindUser demonstrates sentinel error usage
func FindUser(id int) (string, error) {
	if id < 0 {
		return "", ErrNotFound
	}
	if id > 1000 {
		return "", ErrUnauthorized
	}
	return fmt.Sprintf("user_%d", id), nil
}

// HandleUserError demonstrates handling sentinel errors
func HandleUserError(id int) string {
	user, err := FindUser(id)
	if err != nil {
		if errors.Is(err, ErrNotFound) {
			return "User not found"
		}
		if errors.Is(err, ErrUnauthorized) {
			return "Unauthorized access"
		}
		return "Unknown error"
	}
	return user
}

// PanicToError converts panic to error
func PanicToError() (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("recovered from panic: %v", r)
		}
	}()
	
	panic("something went wrong")
}

// ChainedValidation demonstrates chained error checks
func ChainedValidation(data map[string]interface{}) error {
	if err := validateName(data); err != nil {
		return fmt.Errorf("name validation: %w", err)
	}
	
	if err := validateAge(data); err != nil {
		return fmt.Errorf("age validation: %w", err)
	}
	
	if err := validateEmail(data); err != nil {
		return fmt.Errorf("email validation: %w", err)
	}
	
	return nil
}

func validateName(data map[string]interface{}) error {
	name, ok := data["name"].(string)
	if !ok || name == "" {
		return errors.New("name is required")
	}
	return nil
}

func validateAge(data map[string]interface{}) error {
	age, ok := data["age"].(int)
	if !ok || age < 0 {
		return errors.New("valid age is required")
	}
	return nil
}

func validateEmail(data map[string]interface{}) error {
	email, ok := data["email"].(string)
	if !ok || email == "" {
		return errors.New("email is required")
	}
	return nil
}

func demonstrateErrors() {
	// Test basic error
	_, err := BasicErrorReturn(-1)
	if err != nil {
		fmt.Println("Error:", err)
	}
	
	// Test custom error
	err = NewCustomError(404, "Resource not found")
	fmt.Println(ErrorTypeAssertion(err))
	
	// Test validation error
	err = ValidateUser("ab", 15)
	fmt.Println(err)
}


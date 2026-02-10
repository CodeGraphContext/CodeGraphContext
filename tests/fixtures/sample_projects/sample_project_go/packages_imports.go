// packages_imports.go - Demonstrates Go package imports and usage
package main

import (
	// Standard library imports
	"fmt"
	"io"
	"math"
	"math/rand"
	"net/http"
	"os"
	"strings"
	"time"
	
	// Aliased imports
	str "strings"
	
	// Dot imports (imports all exported names directly)
	// . "fmt"  // Uncomment to use - not recommended in production
	
	// Blank imports (for side effects only)
	_ "image/png"
	
	// Local package import (would be actual import in real project)
	// "github.com/user/project/module"
)

// StandardLibraryUsage demonstrates standard library usage
func StandardLibraryUsage() {
	// fmt package
	fmt.Println("Hello from fmt")
	
	// strings package
	upper := strings.ToUpper("hello")
	fmt.Println(upper)
	
	// math package
	sqrt := math.Sqrt(16)
	fmt.Printf("Square root: %.2f\n", sqrt)
	
	// time package
	now := time.Now()
	fmt.Println("Current time:", now.Format(time.RFC3339))
	
	// rand package
	rand.Seed(time.Now().UnixNano())
	randomNum := rand.Intn(100)
	fmt.Println("Random number:", randomNum)
}

// AliasedImportUsage demonstrates aliased imports
func AliasedImportUsage() {
	// Using str alias for strings package
	result := str.Contains("hello world", "world")
	fmt.Println("Contains:", result)
	
	trimmed := str.TrimSpace("  spaces  ")
	fmt.Println("Trimmed:", trimmed)
}

// FileOperations demonstrates os and io packages
func FileOperations() error {
	// Create a file
	file, err := os.Create("example.txt")
	if err != nil {
		return fmt.Errorf("failed to create file: %w", err)
	}
	defer file.Close()
	
	// Write to file
	_, err = io.WriteString(file, "Hello, File!\n")
	if err != nil {
		return fmt.Errorf("failed to write to file: %w", err)
	}
	
	// Read file
	content, err := os.ReadFile("example.txt")
	if err != nil {
		return fmt.Errorf("failed to read file: %w", err)
	}
	
	fmt.Println("File content:", string(content))
	
	// Clean up
	os.Remove("example.txt")
	
	return nil
}

// HTTPClientExample demonstrates net/http package
func HTTPClientExample() error {
	// Make HTTP request
	resp, err := http.Get("https://api.github.com")
	if err != nil {
		return fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()
	
	fmt.Println("Status:", resp.Status)
	
	// Read response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read response: %w", err)
	}
	
	fmt.Println("Response length:", len(body))
	
	return nil
}

// HTTPServerExample demonstrates creating an HTTP server
func HTTPServerExample() {
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "Hello, %s!", r.URL.Path[1:])
	})
	
	http.HandleFunc("/api/users", handleUsers)
	
	// This would start the server (commented out for sample)
	// http.ListenAndServe(":8080", nil)
}

func handleUsers(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		fmt.Fprintf(w, "Getting users")
	case http.MethodPost:
		fmt.Fprintf(w, "Creating user")
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

// StringsPackageUsage demonstrates extensive strings package usage
func StringsPackageUsage() {
	// Various string operations
	text := "Hello, World! Hello, Go!"
	
	contains := strings.Contains(text, "World")
	hasPrefix := strings.HasPrefix(text, "Hello")
	hasSuffix := strings.HasSuffix(text, "Go!")
	
	count := strings.Count(text, "Hello")
	index := strings.Index(text, "World")
	
	split := strings.Split(text, " ")
	joined := strings.Join(split, "-")
	
	replaced := strings.Replace(text, "Hello", "Hi", -1)
	
	fmt.Printf("Contains: %v, Prefix: %v, Suffix: %v\n", contains, hasPrefix, hasSuffix)
	fmt.Printf("Count: %d, Index: %d\n", count, index)
	fmt.Printf("Split: %v\n", split)
	fmt.Printf("Joined: %s\n", joined)
	fmt.Printf("Replaced: %s\n", replaced)
}

// MathPackageUsage demonstrates math package
func MathPackageUsage() {
	// Math constants
	fmt.Println("Pi:", math.Pi)
	fmt.Println("E:", math.E)
	
	// Math functions
	fmt.Println("Sqrt(16):", math.Sqrt(16))
	fmt.Println("Pow(2, 10):", math.Pow(2, 10))
	fmt.Println("Max(10, 20):", math.Max(10, 20))
	fmt.Println("Min(10, 20):", math.Min(10, 20))
	fmt.Println("Abs(-42):", math.Abs(-42))
	fmt.Println("Ceil(4.2):", math.Ceil(4.2))
	fmt.Println("Floor(4.8):", math.Floor(4.8))
	fmt.Println("Round(4.5):", math.Round(4.5))
}

// TimePackageUsage demonstrates time package
func TimePackageUsage() {
	// Current time
	now := time.Now()
	fmt.Println("Current time:", now)
	
	// Time formatting
	formatted := now.Format("2006-01-02 15:04:05")
	fmt.Println("Formatted:", formatted)
	
	// Parsing time
	parsed, _ := time.Parse("2006-01-02", "2024-01-15")
	fmt.Println("Parsed:", parsed)
	
	// Time arithmetic
	tomorrow := now.Add(24 * time.Hour)
	yesterday := now.Add(-24 * time.Hour)
	fmt.Println("Tomorrow:", tomorrow.Format("2006-01-02"))
	fmt.Println("Yesterday:", yesterday.Format("2006-01-02"))
	
	// Duration
	duration := 2 * time.Hour
	fmt.Println("Duration:", duration)
	
	// Sleep
	// time.Sleep(time.Second)
}

// OSPackageUsage demonstrates os package
func OSPackageUsage() {
	// Environment variables
	os.Setenv("MY_VAR", "my_value")
	value := os.Getenv("MY_VAR")
	fmt.Println("Environment variable:", value)
	
	// Command line arguments
	args := os.Args
	fmt.Println("Program name:", args[0])
	
	// Working directory
	wd, _ := os.Getwd()
	fmt.Println("Working directory:", wd)
	
	// File info
	fileInfo, err := os.Stat("packages_imports.go")
	if err == nil {
		fmt.Println("File size:", fileInfo.Size())
		fmt.Println("Is directory:", fileInfo.IsDir())
		fmt.Println("Modified:", fileInfo.ModTime())
	}
}

// IOPackageUsage demonstrates io package
func IOPackageUsage() {
	// String reader
	reader := strings.NewReader("Hello from io package")
	
	// Read all
	content, _ := io.ReadAll(reader)
	fmt.Println("Content:", string(content))
	
	// Copy example (would copy from one reader/writer to another)
	// io.Copy(dst, src)
}

// MultiplePackageUsage uses multiple packages together
func MultiplePackageUsage() error {
	// Combine time, strings, and fmt
	now := time.Now()
	formatted := now.Format(time.RFC3339)
	upper := strings.ToUpper(formatted)
	final := fmt.Sprintf("Current time: %s", upper)
	
	// Combine math and fmt
	result := math.Sqrt(math.Pow(3, 2) + math.Pow(4, 2))
	output := fmt.Sprintf("Hypotenuse: %.2f", result)
	
	fmt.Println(final)
	fmt.Println(output)
	
	return nil
}

// PackageInitPattern demonstrates initialization patterns
var (
	initialized bool
	config      map[string]string
)

func init() {
	// This runs automatically when package is imported
	initialized = true
	config = make(map[string]string)
	config["version"] = "1.0.0"
	config["env"] = "development"
	
	fmt.Println("Package initialized")
}

// GetConfig returns the config
func GetConfig(key string) string {
	return config[key]
}

func demonstrateImports() {
	StandardLibraryUsage()
	AliasedImportUsage()
	StringsPackageUsage()
	MathPackageUsage()
	TimePackageUsage()
	OSPackageUsage()
	IOPackageUsage()
	MultiplePackageUsage()
}


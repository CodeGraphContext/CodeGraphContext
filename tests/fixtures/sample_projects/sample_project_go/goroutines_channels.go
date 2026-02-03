// goroutines_channels.go - Demonstrates Go concurrency patterns
package main

import (
	"fmt"
	"sync"
	"time"
)

// SimpleGoroutine demonstrates basic goroutine
func SimpleGoroutine(id int) {
	fmt.Printf("Goroutine %d starting\n", id)
	time.Sleep(time.Millisecond * 100)
	fmt.Printf("Goroutine %d done\n", id)
}

// ChannelSender sends data to a channel
func ChannelSender(ch chan<- int, values []int) {
	for _, v := range values {
		ch <- v
	}
	close(ch)
}

// ChannelReceiver receives data from a channel
func ChannelReceiver(ch <-chan int, done chan<- bool) {
	sum := 0
	for v := range ch {
		sum += v
	}
	fmt.Printf("Sum: %d\n", sum)
	done <- true
}

// BufferedChannelExample demonstrates buffered channels
func BufferedChannelExample() {
	ch := make(chan string, 3)
	
	ch <- "first"
	ch <- "second"
	ch <- "third"
	
	fmt.Println(<-ch)
	fmt.Println(<-ch)
	fmt.Println(<-ch)
}

// SelectExample demonstrates select statement
func SelectExample(ch1, ch2 chan string) string {
	select {
	case msg1 := <-ch1:
		return fmt.Sprintf("Received from ch1: %s", msg1)
	case msg2 := <-ch2:
		return fmt.Sprintf("Received from ch2: %s", msg2)
	case <-time.After(time.Second):
		return "Timeout"
	}
}

// Worker demonstrates worker pool pattern
func Worker(id int, jobs <-chan int, results chan<- int, wg *sync.WaitGroup) {
	defer wg.Done()
	for job := range jobs {
		fmt.Printf("Worker %d processing job %d\n", id, job)
		time.Sleep(time.Millisecond * 50)
		results <- job * 2
	}
}

// WorkerPool creates a pool of workers
func WorkerPool(numWorkers int, numJobs int) []int {
	jobs := make(chan int, numJobs)
	results := make(chan int, numJobs)
	var wg sync.WaitGroup
	
	// Start workers
	for w := 1; w <= numWorkers; w++ {
		wg.Add(1)
		go Worker(w, jobs, results, &wg)
	}
	
	// Send jobs
	for j := 1; j <= numJobs; j++ {
		jobs <- j
	}
	close(jobs)
	
	// Wait and collect results
	go func() {
		wg.Wait()
		close(results)
	}()
	
	var output []int
	for result := range results {
		output = append(output, result)
	}
	
	return output
}

// Counter demonstrates mutex for safe concurrent access
type Counter struct {
	mu    sync.Mutex
	value int
}

// Increment safely increments counter
func (c *Counter) Increment() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value++
}

// GetValue safely gets counter value
func (c *Counter) GetValue() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.value
}

// RWMutexExample demonstrates read-write mutex
type ConcurrentMap struct {
	mu   sync.RWMutex
	data map[string]int
}

// Set adds or updates a value
func (cm *ConcurrentMap) Set(key string, value int) {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	cm.data[key] = value
}

// Get retrieves a value
func (cm *ConcurrentMap) Get(key string) (int, bool) {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	val, ok := cm.data[key]
	return val, ok
}

// OnceExample demonstrates sync.Once
var once sync.Once
var instance *Singleton

type Singleton struct {
	data string
}

// GetSingleton returns singleton instance
func GetSingleton() *Singleton {
	once.Do(func() {
		fmt.Println("Creating singleton instance")
		instance = &Singleton{data: "singleton data"}
	})
	return instance
}

// PipelineStage1 first stage of pipeline
func PipelineStage1(input <-chan int, output chan<- int) {
	for num := range input {
		output <- num * 2
	}
	close(output)
}

// PipelineStage2 second stage of pipeline
func PipelineStage2(input <-chan int, output chan<- int) {
	for num := range input {
		output <- num + 10
	}
	close(output)
}

// Pipeline demonstrates pipeline pattern
func Pipeline(numbers []int) []int {
	stage1 := make(chan int)
	stage2 := make(chan int)
	
	// Input
	go func() {
		for _, num := range numbers {
			stage1 <- num
		}
		close(stage1)
	}()
	
	// Stage 1
	go PipelineStage1(stage1, stage2)
	
	// Collect results
	var results []int
	for result := range stage2 {
		results = append(results, result)
	}
	
	return results
}

// FanOut sends data to multiple channels
func FanOut(input <-chan int, outputs []chan<- int) {
	for val := range input {
		for _, out := range outputs {
			out <- val
		}
	}
	for _, out := range outputs {
		close(out)
	}
}

// FanIn merges multiple channels into one
func FanIn(inputs ...<-chan int) <-chan int {
	output := make(chan int)
	var wg sync.WaitGroup
	
	for _, input := range inputs {
		wg.Add(1)
		go func(ch <-chan int) {
			defer wg.Done()
			for val := range ch {
				output <- val
			}
		}(input)
	}
	
	go func() {
		wg.Wait()
		close(output)
	}()
	
	return output
}

func demonstrateConcurrency() {
	// Simple goroutines
	for i := 1; i <= 3; i++ {
		go SimpleGoroutine(i)
	}
	
	// Worker pool
	results := WorkerPool(3, 5)
	fmt.Println("Results:", results)
	
	time.Sleep(time.Second)
}


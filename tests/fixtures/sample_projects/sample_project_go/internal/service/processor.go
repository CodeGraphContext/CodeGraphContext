package service

import "fmt"

type Processor interface {
	Process(data string) string
}

type DefaultProcessor struct{}

func (p DefaultProcessor) Process(data string) string {
	return fmt.Sprintf("Processed by Go: %s", data)
}

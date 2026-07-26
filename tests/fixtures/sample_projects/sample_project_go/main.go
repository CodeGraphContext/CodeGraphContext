package main

import (
	"fmt"
	"sample_project_go/internal/service"
)

func main() {
	var p service.Processor = service.DefaultProcessor{}
	result := p.Process("CGC Data")
	fmt.Println(result)
}

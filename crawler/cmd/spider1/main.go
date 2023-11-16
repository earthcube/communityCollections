package main

import (
	"survey/internal/queue"
	"survey/internal/spider"
)

func main() {
	ns := NewSpider()
	ns.ProcessQueue()

	spider.Crawl("https://earth-search.aws.element84.com/v1/k")

	spider.CatScan()
}

func NewSpider() *queue.Spider {
	return &queue.Spider{
		Visited: make(map[string]bool),
		Queue:   []string{"https://earth-search.aws.element84.com/v1/"}, // Seed URL
	}
}

package main

import (
	"survey/internal/queue"
	"survey/internal/spider"
)

func main() {
	ns := NewSpider()
	ns.ProcessQueue()

	spider.Crawl("https://fils.network")

	spider.CatScan()
}

func NewSpider() *queue.Spider {
	return &queue.Spider{
		Visited: make(map[string]bool),
		Queue:   []string{"https://example.com"}, // Seed URL
	}
}

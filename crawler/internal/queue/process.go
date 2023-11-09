package queue

import (
	"fmt"
	"net/http"
)

import "sync"

// Spider represents the web spider with a queue and a list of visited URLs.
type Spider struct {
	Visited map[string]bool
	Queue   []string
	mu      sync.Mutex
}

func (s *Spider) AddToQueue(url string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Add the URL to the queue if it's not already visited.
	if !s.Visited[url] {
		s.Queue = append(s.Queue, url)
	}
}

func (s *Spider) ProcessQueue() {
	for len(s.Queue) > 0 {
		// Dequeue the next URL for processing.
		url := s.Queue[0]
		s.Queue = s.Queue[1:]

		// Mark the URL as visited.
		s.mu.Lock()
		s.Visited[url] = true
		s.mu.Unlock()

		// Process the URL (e.g., make an HTTP request).
		fmt.Printf("Visiting: %s\n", url)

		// Simulate an HTTP GET request. You can replace this with a proper HTTP request.
		resp, err := http.Get(url)
		if err != nil {
			fmt.Printf("Error visiting %s: %v\n", url, err)
			continue
		}
		resp.Body.Close()

		// Extract and enqueue links from the webpage.
		links := extractLinks(resp.Body)
		for _, link := range links {
			s.AddToQueue(link)
		}
	}
}

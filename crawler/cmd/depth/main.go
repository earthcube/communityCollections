package main

import (
	"fmt"

	"github.com/gocolly/colly/v2"
)

func main() {
	// Instantiate default collector
	c := colly.NewCollector(
		// MaxDepth is 1, so only the links on the scraped page
		// is visited, and no further links are followed
		colly.AllowedDomains("hydrography.org"),
		colly.MaxDepth(3),
	)

	// On every a element which has href attribute call callback
	c.OnHTML("a[href]", func(e *colly.HTMLElement) {
		link := e.Attr("href")
		// Print link
		//fmt.Println(link)
		// Visit link found on page
		e.Request.Visit(link)
	})

	c.OnHTML("body", func(e *colly.HTMLElement) {
		s := e.DOM.Find("script").Text()
		//s := e.DOM.Find("script").Attr(type="application/ld+json").Text()

		//r := regexp.MustCompile(`something\.array\s*=\s*(.+\}])\s*`)
		//res := r.FindString(s)
		//res = strings.ReplaceAll(res, "something.array = ", "")

		fmt.Println(s)
	})

	// Start scraping on https://en.wikipedia.org
	c.Visit("https://hydrography.org/")
}

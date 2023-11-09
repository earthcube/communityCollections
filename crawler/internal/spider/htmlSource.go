package spider

import (
	"golang.org/x/net/html"
	"strings"
)

func GetLinksFromHtml(document string) ([]string, error) {

	var links []string
	doc, err := html.Parse(strings.NewReader(document))
	if err != nil {
		return links, err
	}

	var f func(*html.Node)
	f = func(n *html.Node) {
		if n.Type == html.ElementNode && n.Data == "a" {
			for _, a := range n.Attr {
				if a.Key == "href" {
					links = append(links, a.Val)
				}
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			f(c)
		}
	}
	f(doc)
	return links, nil
}

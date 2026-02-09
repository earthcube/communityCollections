package spider

import (
	"fmt"
	"io/ioutil"
	"net/http"
)

func Crawl(u string) {
	resp, err := http.Get(u)
	if err != nil {
		panic(err)
	}

	bytes, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		panic(err)
	}

	stringBody := string(bytes)
	links, err := GetLinksFromHtml(stringBody)

	if err != nil {
		panic(err)
	}

	for _, link := range links {
		fmt.Println(link)
	}
}

package spider

import (
	"fmt"
	"github.com/tidwall/gjson"
	"io/ioutil"
	"log"
)

func CatScan() {

	d := testData()

	value := gjson.Get(d, "hasPart.#.url")
	fmt.Println("------------------------------------")

	value.ForEach(func(key, value gjson.Result) bool {
		lu := value.String()
		fmt.Println(lu)
		//lu := tu

		//lja, err := acquire.PageRender(v1, timeout, lu, k, repologger, repostats)
		//if err != nil {
		//	log.Println("Error when acquiring the  JSON-LD document:", err)
		//}
		//fmt.Printf("\n ---------start for %s\n", lu)
		//fmt.Println(lja[0])
		//fmt.Println("---------------------------------------")

		return true // keep iterating
	})
}

func testData() string {
	content, err := ioutil.ReadFile("data/catalogJSON.json")
	if err != nil {
		log.Fatal(err)
	}

	return string(content)
}

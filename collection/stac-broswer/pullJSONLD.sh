#!/bin/bash

url=$1

curl -s  --header "Accept: text/html"   $url \
    | sed -n '/<script type=\"application\/ld+json\">/,/<\/script>/p' \
    | sed 's/<\/script>//' | sed 's/<script type=\"application\/ld+json\">//
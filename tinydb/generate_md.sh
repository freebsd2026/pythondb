#!/bin/bash

start_page=1
end_page=4

page_width=900
page_height=1100

md_file="temp.md"

echo "" > $md_file

for ((i=start_page;i<=end_page;i++))
do
    if [ $i -le 9 ]; then
        j="00$i"
    elif [ $i -le 99 ]; then
        j="0$i"
    else
        j="$i"
    fi

    echo "<img src=\"../images/$j.jpg\" width=\"${page_width}\" height=\"${page_height}\">" >> $md_file
done


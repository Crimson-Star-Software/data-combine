#!/bin/bash

dbname="yaya_orl"

if [ $# -gt 0 ]; then
    dbname=$1
fi

echo $dbname

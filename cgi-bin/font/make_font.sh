#!/bin/sh

./extract_ttf.ff
./encode_ttf.py < numerals.ttf > numerals.py

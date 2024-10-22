#!/usr/bin/python3

import base64

data = open('numerals.ttf', 'rb').read()
text = base64.b64encode(data).decode('ascii').replace('\\', '\\\\')
lines = [text[i:i + 99] for i in range(0, len(text), 99)]
f = open('numerals.py', 'w')
print('font_data = """\\', file=f)
for line in lines:
  print(line + '\\', file=f)
print('"""', file=f)

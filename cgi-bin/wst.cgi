#!/usr/bin/python3
# CGI for Weather Station.
# 2021-12-21,2023-06-04,2024-10-10  T. Nakagawa

from PIL import Image, ImageDraw, ImageFont
import base64
import datetime
import io
import math
import time

LOGFILE = '/var/log/wst.log'
STATIONS = 4
COLORS = ['red', 'blue', 'green', 'purple']
LABELS = ['Temperature (&#8451;)', 'Humidity (%)', 'Pressure (hPa)', 'Battery (V)']

def read_data(file):
  LINELEN = 70
  with open(file, 'rb') as f:
    f.seek(-LINELEN * 24 * 60 // 5 * STATIONS * 7, 2)
    f.readline()  # Skip the incomplete line.
    lines = f.readlines()
  data = [[] for _ in range(STATIONS)]
  for line in lines:
    tmst, host, vals = line.decode('ascii').split()
    if host != 'wst':
      continue
    epoch = datetime.datetime.fromisoformat(tmst).timestamp()
    vals = vals.split(',')
    stid = int(vals[0])
    assert len(vals) == 6 and stid >= 0 and stid < STATIONS
    if vals[3] == '0.0':  # Atmospheric pressure is unavailable.
      vals[3] = 'nan'
    d = [epoch] + list(map(float, vals[1:]))
    data[stid].append(d)
  return data

def filter_data(data, min_epoch):
  for st in range(STATIONS):
    for j in reversed(range(len(data[st]))):
      if data[st][j][0] < min_epoch:
        data[st] = data[st][j + 1:]
        break

def plot_chart(now, span, tdata, index):
  if span == 'day':
    xmin = now - 60 * 60 * 24
    xmax = now
    xstp = 60 * 60 * 3
    xorg = datetime.datetime.fromisoformat(time.strftime('%Y-%m-%d %H:00:00', time.localtime(xmin))).timestamp() + 60 * 60
    xfmt = lambda v: time.strftime('%H:%M', time.localtime(v))
  elif span == 'week':
    xmin = now - 60 * 60 * 24 * 7
    xmax = now
    xstp = 60 * 60 * 24
    xorg = datetime.datetime.fromisoformat(time.strftime('%Y-%m-%d 00:00:00', time.localtime(xmin))).timestamp() + 60 * 60 * 24
    xfmt = lambda v: time.strftime('%m/%d', time.localtime(v))
  ymin, ymax = float('inf'), float('-inf')
  for st in range(STATIONS):
    if tdata[st]:
      ymin = min(ymin, min(tdata[st][1 + index]))
      ymax = max(ymax, max(tdata[st][1 + index]))
  delta = (ymax - ymin) / 6
  ystp = float('1' + ('%.0e' % delta)[1:])
  for mul in [10.0, 5.0, 2.0]:
    if abs(ystp * mul - delta) < abs(ystp - delta):
      ystp *= mul
      break
  ymin -= ystp / 2.0
  ymax += ystp / 2.0
  yorg = int(ymin / ystp) * ystp + ystp
  acc = 0 if ystp >= 1.0 else len(str(ystp)) - 2
  yfmt = lambda v: '%.*f' % (acc, v)
  fig = Figure(width=500, height=350,
               xmin=xmin, xmax=xmax, xorigin=xorg, xstep=xstp, xformatter=xfmt, xrotation=45,
               ymin=ymin, ymax=ymax, yorigin=yorg, ystep=ystp, yformatter=yfmt, ygrid=True)

  for st in range(STATIONS):
    if not tdata[st]:
      continue
    if math.isnan(tdata[st][1 + index][0]):
      continue
    fig.plot(tdata[st][0], tdata[st][1 + index], color=COLORS[st])
  f = io.BytesIO()
  fig.save(f, format='PNG', compress_level=6)
  img = base64.b64encode(f.getvalue()).decode()
  return img

def main():
  data = read_data(LOGFILE)
  now = int(time.time())

  # Charts for the week.
  wcharts = []
  filter_data(data, now - 60 * 60 * 24 * 7)
  tdata = [list(zip(*d)) for d in data]
  for i in range(4):
    wcharts.append(plot_chart(now, 'week', tdata, i))

  # Charts for the day.
  dcharts = []
  filter_data(data, now - 60 * 60 * 24)
  tdata = [list(zip(*d)) for d in data]
  for i in range(4):
    dcharts.append(plot_chart(now, 'day', tdata, i))

  # Latest information.
  latest = []
  for st in range(STATIONS):
    buf = []
    if data[st]:
      buf.append(time.strftime('%Y-%m-%d %H:%M', time.localtime(data[st][-1][0])))
      buf.append('&nbsp;&nbsp;&nbsp;')
      for i, unit in enumerate(['&#8451;', '%', ' hPa', ' V', ' ms']):
        if math.isnan(data[st][-1][1 + i]):
          continue
        if i != 0:
          buf.append(' / ')
        buf.append('%.1f%s' % (data[st][-1][1 + i], unit))
    latest.append(''.join(buf))

  # Output the HTML page.
  print('Content-Type: text/html; charset=UTF-8')
  print('')
  print('<!DOCTYPE html>')
  print('<html>')
  print('<head><title>Weather Station</title></head>')
  print('<body>')
  print('<h2>')
  for st in range(STATIONS):
    if latest[st]:
      print('<span style="color: %s;">(%d)</span> %s<br>' % (COLORS[st], 1 + st, latest[st]))
  print('</h2>')
  print('<h1>Day</h1>')
  print('<div style="text-align: center;">')
  for label, chart in zip(LABELS, dcharts):
    print('<div style="display: inline-block; text-align: center; line-height: 0">')
    print('<p style="font-weight: bold">%s</p>' % label)
    print('<img src="data:image/png;base64,%s">' % chart)
    print('</div>')
  print('</div>')
  print('<h1>Week</h1>')
  print('<div style="text-align: center;">')
  for label, chart in zip(LABELS, wcharts):
    print('<div style="display: inline-block; text-align: center; line-height: 0">')
    print('<p style="font-weight: bold">%s</p>' % label)
    print('<img src="data:image/png;base64,%s">' % chart)
    print('</div>')
  print('</div>')
  print('</body>')
  print('</html>')

class Figure(object):
  def __init__(self, width=320, height=240, fontsize=12, thickness=1,
               xmin=0, xmax=1, xorigin=0.1, xstep=0.1, xgrid=False, xtick=True, xformatter=None, xrotation=0,
               ymin=0, ymax=1, yorigin=0.1, ystep=0.1, ygrid=False, ytick=True, yformatter=None, yrotation=0):
    self.xmin, self.xmax = xmin, xmax
    self.ymin, self.ymax = ymin, ymax
    self.img = Image.new(mode='RGB', size=(width, height), color='white')
    self.draw = ImageDraw.Draw(self.img)
    font_file = io.BytesIO(base64.b64decode(FONT_DATA))
    font = ImageFont.truetype(font_file, fontsize)

    xgap = 0
    xlen = 0
    if xformatter:
      r = xrotation * 2.0 * math.pi / 360.0
      for x in [xmin, xmax]:
        size = self.draw.textbbox((0, 0), xformatter(x), font=font)
        xlen = max(xlen, size[2] - size[0], size[3] - size[1])
        bb = [[size[0], size[2], size[2], size[0]], [size[1], size[1], size[3], size[3]]]  # [[x0, ..., x3], [y0, ..., y3]]
        for i in range(4):
          bb[1][i] = bb[0][i] * math.sin(r) + bb[1][i] * math.cos(r)
        xgap = max(xgap, int(max(bb[1]) - min(bb[1])))
    ygap = 0
    ylen = 0
    if yformatter:
      r = yrotation * 2.0 * math.pi / 360.0
      for y in [ymin, ymax]:
        size = self.draw.textbbox((0, 0), yformatter(y), font=font)
        ylen = max(ylen, size[2] - size[0], size[3] - size[1])
        bb = [[size[0], size[2], size[2], size[0]], [size[1], size[1], size[3], size[3]]]  # [[x0, ..., x3], [y0, ..., y3]]
        for i in range(4):
          bb[0][i] = bb[0][i] * math.cos(r) - bb[1][i] * math.sin(r)
        ygap = max(ygap, int(max(bb[0]) - min(bb[0])))
    self.view = (thickness // 2 + 4 + ygap, thickness // 2, width - 1 - thickness // 2, height - 1 - thickness // 2 - 4 - xgap)

    x0 = self.view[0] + (xorigin - xmin) * (self.view[2] - self.view[0]) / (xmax - xmin)
    dx = xstep * (self.view[2] - self.view[0]) / (xmax - xmin)
    for i in range(math.ceil((xmax - xorigin) / xstep)):
      if xtick:
        self.draw.line([(x0 + dx * i, self.view[3]), (x0 + dx * i, self.view[3] + 2)], fill='black', width=thickness)
      if xgrid:
        self.draw.line([(x0 + dx * i, self.view[1]), (x0 + dx * i, self.view[3])], fill='lightgray', width=thickness)
      if xformatter:
        img = Image.new('RGBA', size=(xlen, xlen))
        draw = ImageDraw.Draw(img)
        draw.text((xlen / 2, xlen / 2), xformatter(xorigin + xstep * i), fill='black', font=font, anchor='mm')
        img = img.rotate(xrotation, center=(xlen / 2, xlen / 2), resample=Image.BICUBIC)
        self.img.paste(img, (int(x0 + dx * i - xlen / 2), int(self.view[3] + 4 - (xgap - xlen) / 2)), img)
    y0 = self.view[3] - (yorigin - ymin) * (self.view[3] - self.view[1]) / (ymax - ymin)
    dy = ystep * (self.view[3] - self.view[1]) / (ymax - ymin)
    for i in range(math.ceil((ymax - yorigin) / ystep)):
      if ytick:
        self.draw.line([(self.view[0], y0 - dy * i), (self.view[0] - 2, y0 - dy * i)], fill='black', width=thickness)
      if ygrid:
        self.draw.line([(self.view[0], y0 - dy * i), (self.view[2], y0 - dy * i)], fill='lightgray', width=thickness)
      if yformatter:
        img = Image.new('RGBA', size=(ylen, ylen))
        draw = ImageDraw.Draw(img)
        draw.text((ylen / 2, ylen / 2), yformatter(yorigin + ystep * i), fill='black', font=font, anchor='mm')
        img = img.rotate(yrotation, center=(ylen / 2, ylen / 2), resample=Image.BICUBIC)
        self.img.paste(img, (int(self.view[0] - 4 - (ygap + ylen) / 2), int(y0 - dy * i - ylen / 2)), img)
    self.draw.rectangle(self.view, outline='black', width=thickness)

  def plot(self, xs, ys, color, thickness=2):
    points = []
    xscale =  (self.view[2] - self.view[0]) / (self.xmax - self.xmin)
    yscale =  (self.view[3] - self.view[1]) / (self.ymax - self.ymin)
    for x, y in zip(xs, ys):
      points.append((self.view[0] + (x - self.xmin) * xscale, self.view[3] - (y - self.ymin) * yscale))
    self.draw.line(points, fill=color, width=thickness)

  def save(self, file, **kwargs):
    self.img.save(file, **kwargs)
    self.img.close()

FONT_DATA = """\
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\
LSxLUVggsAMlRWlTWEQbISFZGyEhWS0sRbAUQ7AAYGOwAWBpRC0ssC9FRC0sRSMgRYpgRC0sRSNFYEQtLEsjUVi5ADP/4LE0IBu\
zMwA0AFlERC0ssBZDWLADJkWKWGRmsB9gG2SwIGBmIFgbIbBAWbABYVkjWGVZsCkjRCMQsCngGyEhISEhWS0ssAJDVFhLUyNLUV\
pYOBshIVkbISEhIVktLLAWQ1iwBCVFZLAgYGYgWBshsEBZsAFhI1gbZVmwKSNEsAUlsAglCCBYAhsDWbAEJRCwBSUgRrAEJSNCP\
LAEJbAHJQiwByUQsAYlIEawBCWwAWAjQjwgWAEbAFmwBCUQsAUlsCngsCkgRWVEsAclELAGJbAp4LAFJbAIJQggWAIbA1mwBSWw\
AyVDSLAEJbAHJQiwBiWwAyWwAWBDSBshWSEhISEhISEtLAKwBCUgIEawBCUjQrAFJQiwAyVFSCEhISEtLAKwAyUgsAQlCLACJUN\
IISEhLSxFIyBFGCCwAFAgWCNlI1kjaCCwQFBYIbBAWSNYZVmKYEQtLEtTI0tRWlggRYpgRBshIVktLEtUWCBFimBEGyEhWS0sS1\
MjS1FaWDgbISFZLSywACFLVFg4GyEhWS0ssAJDVFiwRisbISEhIVktLLACQ1RYsEcrGyEhIVktLLACQ1RYsEgrGyEhISFZLSywA\
kNUWLBJKxshISFZLSwgiggjS1OKS1FaWCM4GyEhWS0sALACJUmwAFNYILBAOBEbIVktLAFGI0ZgI0ZhIyAQIEaKYbj/gGKKsUBA\
inBFYGg6LSwgiiNJZIojU1g8GyFZLSxLUlh9G3pZLSywEgBLAUtUQi0ssQIAQrEjAYhRsUABiFNaWLkQAAAgiFRYsgIBAkNgQlm\
xJAGIUVi5IAAAQIhUWLICAgJDYEKxJAGIVFiyAiACQ2BCAEsBS1JYsgIIAkNgQlkbuUAAAICIVFiyAgQCQ2BCWblAAACAY7gBAI\
hUWLICCAJDYEJZuUAAAQBjuAIAiFRYsgIQAkNgQlm5QAACAGO4BACIVFiyAkACQ2BCWVlZWVktLEUYaCNLUVgjIEUgZLBAUFh8W\
WiKYFlELSywABawAiWwAiUBsAEjPgCwAiM+sQECBgywCiNlQrALI0IBsAEjPwCwAiM/sQECBgywBiNlQrAHI0KwARYBLSx6ihBF\
I/UYLQAAALEJQL4BBwABAB8BBwABAJ8BBECOAcD9Aa/9AQD9AQpP+wEg+wH1UCgf8kYoH/FGKh/wRisfX+9/7wIP70/vX++P76/\
vBQvl5B4f4+JGHw/iAUDiRhYf4eBGH8/g3+Dv4ANA4DM2RuBGGB/dPd9V3j0DVd8BA1XcA/8fD9Uf1QIP1R/VAkDKGBtGz8IBvc\
A8H8FQJh+8vigf/7kBULhwuIC4A7j/wED/uBIyRh+3P7dPt2+3f7eft6+3B3CyoLKwsgMPsgGQtQGwtQEPtQEID7M/s++zA4Cwk\
LACsLDAsNCwAy+vP68CoK2wrQLArdCtAi+sP6wCn6sBwKrQqgJPqY+pAi+pb6m/qf+pBJybJB9QmwFvlgG/lgGWRh0flZQXH3+U\
j5T/lAMwkUCRAoCRAXCPgI8CkI8BwI/QjwJPjF+Mb4wDhkb/H5+FAYSDMR90cz8fc1AmH29uPB9uRjUfGgEYVRkzGFUHMwNVBgP\
/H2BQJh9fUCYfXEYxH1taSB9aRjEfEzISVQUBA1UEMgNVbwMBDwM/AwLvUf9RAkBRNThGQFElKEbPQFRQAUlGIB9IRjUfR0Y1H6\
9GAd9G70YCgEYBFjIVVREBD1UQMg9VAgEAVQEAAR8fDz8PXw9/DwQPDy8PTw9vD48P3w//Dwc/D38P7w8DbwABgBYBBQG4AZCxV\
FMrK0u4B/9SS7AHUFuwAYiwJVOwAYiwQFFasAaIsABVWltYsQEBjlmFjY0AQh1LsDJTWLBgHVlLsGRTWLBAHVlLsIBTWLAQHbEW\
AEJZdHN0dSsrKysrAXN0dSsrKwB0Kytzc3UrKysBKysrACsrKysrKwErKwArKwErcysAdHN0dXN0cysBK3R1AHMrc3QBc3N0AHN\
0dHN0cwFec3N0c3MAcytzcwErACsBKwBzK3R1KysrKwErK3QrK15zKwArXnN0ASsrKwArc3Nec3NzAXNzcxheAAAABcwFzAB9BY\
EAFQB5BYEAFQAAAAAAAAAAAAAAAAAABDoAFAB3AAD/7AAAAAD/7AAAAAD/7AAA/lcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAtAC9AK8AoAAAAAAAAAAA\
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\
7S/tAS8rXXFyM+0yMTATNTMVAzUzFbvDw8MDa8/P/JXPzwAAAAAAHAFWAAEAAAAAAAAAYADCAAEAAAAAAAEADwFDAAEAAAAAAAI\
ABwFjAAEAAAAAAAMAGgGhAAEAAAAAAAQADwHcAAEAAAAAAAUADgIKAAEAAAAAAAYADgI3AAEAAAAAAAcAegM8AAEAAAAAAAgAFA\
PhAAEAAAAAAAkADgQUAAEAAAAAAAsAHARdAAEAAAAAAAwALgTYAAEAAAAAAA0AbwXnAAEAAAAAAA4APgbVAAMAAQQJAAAAwAAAA\
AMAAQQJAAEAHgEjAAMAAQQJAAIADgFTAAMAAQQJAAMANAFrAAMAAQQJAAQAHgG8AAMAAQQJAAUAHAHsAAMAAQQJAAYAHAIZAAMA\
AQQJAAcA9AJGAAMAAQQJAAgAKAO3AAMAAQQJAAkAHAP2AAMAAQQJAAsAOAQjAAMAAQQJAAwAXAR6AAMAAQQJAA0A3gUHAAMAAQQ\
JAA4AfAZXAEMAbwBwAHkAcgBpAGcAaAB0ACAAKABjACkAIAAyADAAMAA3ACAAUgBlAGQAIABIAGEAdAAsACAASQBuAGMALgAgAE\
EAbABsACAAcgBpAGcAaAB0AHMAIAByAGUAcwBlAHIAdgBlAGQALgAgAEwASQBCAEUAUgBBAFQASQBPAE4AIABpAHMAIABhACAAd\
AByAGEAZABlAG0AYQByAGsAIABvAGYAIABSAGUAZAAgAEgAYQB0ACwAIABJAG4AYwAuAABDb3B5cmlnaHQgKGMpIDIwMDcgUmVk\
IEhhdCwgSW5jLiBBbGwgcmlnaHRzIHJlc2VydmVkLiBMSUJFUkFUSU9OIGlzIGEgdHJhZGVtYXJrIG9mIFJlZCBIYXQsIEluYy4\
AAEwAaQBiAGUAcgBhAHQAaQBvAG4AIABTAGEAbgBzAABMaWJlcmF0aW9uIFNhbnMAAFIAZQBnAHUAbABhAHIAAFJlZ3VsYXIAAE\
EAcwBjAGUAbgBkAGUAcgAgAC0AIABMAGkAYgBlAHIAYQB0AGkAbwBuACAAUwBhAG4AcwAAQXNjZW5kZXIgLSBMaWJlcmF0aW9uI\
FNhbnMAAEwAaQBiAGUAcgBhAHQAaQBvAG4AIABTAGEAbgBzAABMaWJlcmF0aW9uIFNhbnMAAFYAZQByAHMAaQBvAG4AIAAxAC4A\
MAA3AC4ANAAAVmVyc2lvbiAxLjA3LjQAAEwAaQBiAGUAcgBhAHQAaQBvAG4AUwBhAG4AcwAATGliZXJhdGlvblNhbnMAAEwAaQB\
iAGUAcgBhAHQAaQBvAG4AIABpAHMAIABhACAAdAByAGEAZABlAG0AYQByAGsAIABvAGYAIABSAGUAZAAgAEgAYQB0ACwAIABJAG\
4AYwAuACAAcgBlAGcAaQBzAHQAZQByAGUAZAAgAGkAbgAgAFUALgBTAC4AIABQAGEAdABlAG4AdAAgAGEAbgBkACAAVAByAGEAZ\
ABlAG0AYQByAGsAIABPAGYAZgBpAGMAZQAgAGEAbgBkACAAYwBlAHIAdABhAGkAbgAgAG8AdABoAGUAcgAgAGoAdQByAGkAcwBk\
AGkAYwB0AGkAbwBuAHMALgAATGliZXJhdGlvbiBpcyBhIHRyYWRlbWFyayBvZiBSZWQgSGF0LCBJbmMuIHJlZ2lzdGVyZWQgaW4\
gVS5TLiBQYXRlbnQgYW5kIFRyYWRlbWFyayBPZmZpY2UgYW5kIGNlcnRhaW4gb3RoZXIganVyaXNkaWN0aW9ucy4AAEEAcwBjAG\
UAbgBkAGUAcgAgAEMAbwByAHAAbwByAGEAdABpAG8AbgAAQXNjZW5kZXIgQ29ycG9yYXRpb24AAFMAdABlAHYAZQAgAE0AYQB0A\
HQAZQBzAG8AbgAAU3RldmUgTWF0dGVzb24AAGgAdAB0AHAAOgAvAC8AdwB3AHcALgBhAHMAYwBlAG4AZABlAHIAYwBvAHIAcAAu\
AGMAbwBtAC8AAGh0dHA6Ly93d3cuYXNjZW5kZXJjb3JwLmNvbS8AAGgAdAB0AHAAOgAvAC8AdwB3AHcALgBhAHMAYwBlAG4AZAB\
lAHIAYwBvAHIAcAAuAGMAbwBtAC8AdAB5AHAAZQBkAGUAcwBpAGcAbgBlAHIAcwAuAGgAdABtAGwAAGh0dHA6Ly93d3cuYXNjZW\
5kZXJjb3JwLmNvbS90eXBlZGVzaWduZXJzLmh0bWwAAEwAaQBjAGUAbgBzAGUAZAAgAHUAbgBkAGUAcgAgAHQAaABlACAATABpA\
GIAZQByAGEAdABpAG8AbgAgAEYAbwBuAHQAcwAgAGwAaQBjAGUAbgBzAGUALAAgAHMAZQBlACAAaAB0AHQAcABzADoALwAvAGYA\
ZQBkAG8AcgBhAHAAcgBvAGoAZQBjAHQALgBvAHIAZwAvAHcAaQBrAGkALwBMAGkAYwBlAG4AcwBpAG4AZwAvAEwAaQBiAGUAcgB\
hAHQAaQBvAG4ARgBvAG4AdABMAGkAYwBlAG4AcwBlAABMaWNlbnNlZCB1bmRlciB0aGUgTGliZXJhdGlvbiBGb250cyBsaWNlbn\
NlLCBzZWUgaHR0cHM6Ly9mZWRvcmFwcm9qZWN0Lm9yZy93aWtpL0xpY2Vuc2luZy9MaWJlcmF0aW9uRm9udExpY2Vuc2UAAGgAd\
AB0AHAAcwA6AC8ALwBmAGUAZABvAHIAYQBwAHIAbwBqAGUAYwB0AC4AbwByAGcALwB3AGkAawBpAC8ATABpAGMAZQBuAHMAaQBu\
AGcALwBMAGkAYgBlAHIAYQB0AGkAbwBuAEYAbwBuAHQATABpAGMAZQBuAHMAZQAAaHR0cHM6Ly9mZWRvcmFwcm9qZWN0Lm9yZy9\
3aWtpL0xpY2Vuc2luZy9MaWJlcmF0aW9uRm9udExpY2Vuc2UAAAAAAgAAAAAAAP+9AJYAAAAAAAAAAAAAAAAAAAAAAAAAAAARAA\
AAAQACAQIAEQASABMAFAAVABYAFwAYABkAGgAbABwAHQd1bmkwMEFEAAAAAwAIAAIAEQAB//8AAwABAAAADAAAABYAHgACAAEAA\
wAQAAEABAAAAAIAAAABAAAAAQAAAAAAAAABAAAAAOIaYuMAAAAAvxr/gAAAAADPkk3h\
"""

if __name__ == '__main__':
  main()

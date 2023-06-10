#!/usr/bin/python3
# CGI for Weather Station.
# 2021-12-21,2023-06-04  T. Nakagawa

import base64
import datetime
import io
import matplotlib.dates
import matplotlib.pyplot as plt
import os

LOGFILE = '/var/log/wst.log'

def read_data(file):
  LINELEN = 70
  with open(file, 'r') as f:
    f.seek(max(f.tell() - LINELEN * 24 * 60 // 5 * 3 * 7, 0), 0)
    f.readline()
    data = f.readlines()
  data = [d.split() for d in data]
  pres = []
  temp = ([], [], [])
  humi = ([], [], [])
  batt = ([], [], [])
  dura = ([], [], [])
  for time, host, vals in data:
    dt = datetime.datetime.fromisoformat(time).replace(tzinfo=None)
    vals = vals.split(',')
    stid = int(vals[0])
    assert stid >= 0 and stid <= 2
    temp[stid].append((dt, float(vals[1])))
    humi[stid].append((dt, float(vals[2])))
    if stid == 0:
      pres.append((dt, float(vals[3])))
    batt[stid].append((dt, float(vals[4])))
    dura[stid].append((dt, float(vals[5])))
  return pres, temp, humi, batt, dura

def filter_data(data, now, days):
  for i in range(len(data)):
    if now - data[i][0] <= datetime.timedelta(days=days):
      data[:] = data[i:]
      break

def plot_chart(fmt, title, unit, xy0, xy1=None, xy2=None):
  os.environ['MPLCONFIGDIR'] = '/tmp/'
  fig, ax = plt.subplots()
  fig.autofmt_xdate(rotation=45)
  ax.set_title(title)
  ax.set_ylabel(unit)
  ax.grid(axis='y')
  ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter(fmt))
  if xy0:
    x, y = zip(*xy0)
    ax.plot(x, y, color='r')
  if xy1:
    x, y = zip(*xy1)
    ax.plot(x, y, color='b')
  if xy2:
    x, y = zip(*xy2)
    ax.plot(x, y, color='g')
  f = io.BytesIO()
  plt.savefig(f, format='png', dpi=72)
  data = base64.b64encode(f.getvalue()).decode()
  return data

def get_latest(time, unit, vals):
  buf = []
  for unit, val in zip(unit, vals):
    if buf:
      buf.append(', ')
    buf.append('%.1f %s' % (val, unit))
  buf = [time.strftime('%m/%d %H:%M'), '&nbsp;&nbsp;&nbsp;'] + buf
  return ''.join(buf)

def main():
  now = datetime.datetime.now()

  pres, temp, humi, batt, dura = read_data(LOGFILE)
  charts = [[], []]	# charts[daily/weekly][temp/humi/pres/volt]
  latest = []

  # Weekly charts.
  for data in [pres, *temp, *humi, *batt, *dura]:
    filter_data(data, now, 7)
  charts[1].append(plot_chart('%m/%d', 'Temperature', '℃', temp[0], temp[1], temp[2]))
  charts[1].append(plot_chart('%m/%d', 'Humidity', '%',     humi[0], humi[1], humi[2]))
  charts[1].append(plot_chart('%m/%d', 'Pressure', 'hPa',   pres))
  charts[1].append(plot_chart('%m/%d', 'Battery', 'V',      batt[0], batt[1], batt[2]))

  # Daily charts.
  for data in [pres, *temp, *humi, *batt, *dura]:
    filter_data(data, now, 1)
  charts[0].append(plot_chart('%H:%M', 'Temperature', '℃', temp[0], temp[1], temp[2]))
  charts[0].append(plot_chart('%H:%M', 'Humidity', '%',     humi[0], humi[1], humi[2]))
  charts[0].append(plot_chart('%H:%M', 'Pressure', 'hPa',   pres))
  charts[0].append(plot_chart('%H:%M', 'Battery', 'V',      batt[0], batt[1], batt[2]))
  for i in range(3):
    unit = ['℃', '%', 'V', 'ms']
    vals = [temp[i][-1][1], humi[i][-1][1], batt[i][-1][1], dura[i][-1][1]]
    if i == 0:
      unit.append('hPa')
      vals.append(pres[-1][1])
    latest.append(get_latest(temp[i][-1][0], unit, vals))

  # Print the HTML page.
  print('Content-Type: text/html; charset=UTF-8')
  print('')
  print('<!DOCTYPE html>')
  print('<html>')
  print('<head><title>Weather Station</title></head>')
  print('<body>')
  print('<h2><font color="red">①</font> %s<br>' % latest[0])
  print('<font color="blue">②</font> %s<br>' % latest[1])
  print('<font color="green">③</font> %s</h2>' % latest[2])
  print('<h1>Daily</h1>')
  print('<div style="text-align: center;">')
  print('<img src="data:image/png;base64,%s">' % charts[0][0])
  print('<img src="data:image/png;base64,%s">' % charts[0][1])
  print('<img src="data:image/png;base64,%s">' % charts[0][2])
  print('<img src="data:image/png;base64,%s">' % charts[0][3])
  print('</div>')
  print('<h1>Weekly</h1>')
  print('<div style="text-align: center;">')
  print('<img src="data:image/png;base64,%s">' % charts[1][0])
  print('<img src="data:image/png;base64,%s">' % charts[1][1])
  print('<img src="data:image/png;base64,%s">' % charts[1][2])
  print('<img src="data:image/png;base64,%s">' % charts[1][3])
  print('</div>')
  print('</body>')
  print('</html>')

if __name__ == '__main__':
  main()

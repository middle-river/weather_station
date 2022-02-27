#!/usr/bin/python3
# CGI for Weather Station with ESP32.
# 2021-12-21  T. Nakagawa

import datetime
import fcntl
import os

LCKFILE = '/usr/lib/cgi-bin/wst.lck'
LOGFILE = '/usr/lib/cgi-bin/wst.log'
DATFILE = '/usr/lib/cgi-bin/wst.dat'

# Lightweight CGI class (URL encoding is not supported)
class cgi_FieldStorage(dict):
  def __init__(self):
    params = os.environ.get('QUERY_STRING', '').split('&')
    for param in params:
      if '=' not in param:
        continue
      key, value = param.split('=', 1)
      self[key] = value

  def getfirst(self, key, default=None):
    return self.get(key, default)

def read_data(text, origin):
  # This data structure contains only the data necessary for rendering recent weekly/daily charts.
  weekly = [[''] * 24 * 7, [''] * 24 * 7]	# hourly data for a week.
  daily = [[''] * 6 * 24, [''] * 6 * 24]	# 10 minute interval data for a day.
  for buf in text.split('\n'):
    if not buf:
      continue
    time, cid, temp, humi, pres, volt = buf.split(',')
    cid = int(cid)
    assert cid == 0 or cid == 1
    dt = datetime.datetime.fromisoformat(time)
    wdiff = origin.replace(minute=0, second=0, microsecond=0) - dt.replace(minute=0, second=0, microsecond=0)
    w = int(wdiff.total_seconds() / (60 * 60))
    ddiff = origin.replace(minute=origin.minute // 10 * 10, second=0, microsecond=0) - dt.replace(minute=dt.minute // 10 * 10, second=0, microsecond=0)
    d = int(ddiff.total_seconds() / (60 * 10))
    if w < 24 * 7 and not weekly[cid][-w - 1]:
      weekly[cid][-w - 1] = buf
    if d < 6 * 24 and not daily[cid][-d - 1]:
      daily[cid][-d - 1] = buf
  return (weekly, daily)

def write_data(f, data):
  for seq in (data[0][0], data[0][1], data[1][0], data[1][1]):
    for buf in seq:
      print(buf, file=f)

def plot_chart(title, unit, x0, y0, x1, y1, fmt):
  import base64
  import io
  import os
  os.environ['MPLCONFIGDIR'] = '/tmp/'
  import matplotlib.pyplot as plt
  import matplotlib.dates
  fig, ax = plt.subplots()
  fig.autofmt_xdate(rotation=45)
  ax.set_title(title)
  ax.set_ylabel(unit)
  ax.grid(axis='y')
  ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter(fmt))
  if x0 and y0:
    ax.plot(x0, y0, color='r')
  if x1 and y1:
    ax.plot(x1, y1, color='b')
  f = io.BytesIO()
  plt.savefig(f, format='png', dpi=72)
  data = base64.b64encode(f.getvalue()).decode()
  return data

def get_latest(values):
  buf = []
  for i, unit in enumerate(['℃', '%', 'hPa']):
    if not values[1 + i]:
      continue
    if buf:
      buf.append(', ')
    buf.append('%.1f %s' % (values[1 + i][-1], unit))
  if values[0]:
    buf = [values[0][-1].strftime('%H:%M'), '&nbsp;&nbsp;&nbsp;'] + buf
  return ''.join(buf)

def collect(form):
  now = datetime.datetime.now()
  time = now.isoformat()
  cid = int(form.getfirst('id'))
  temp = form.getfirst('temp', '')
  humi = form.getfirst('humi', '')
  pres = form.getfirst('pres', '')
  volt = form.getfirst('volt', '')
  buf = '%s,%s,%s,%s,%s,%s\n' % (time, cid, temp, humi, pres, volt)

  # Mutex.
  with open(LCKFILE, 'r') as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)

    # Append to the log file.
    with open(LOGFILE, 'a') as f:
      f.write(buf)

    # Update the data file.
    if cid == 0 or cid == 1:
      with open(DATFILE, 'r+') as f:
        data = read_data(f.read() + buf, now)
        f.truncate(0)
        f.seek(0)
        write_data(f, data)

    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

  # Output a response.
  print('Content-Type: text/plain\r\n\r\nOK')

def render():
  # Read the data.
  now = datetime.datetime.now()
  with open(DATFILE, 'r') as f:
    data = read_data(f.read(), now)
  values = [[[[] for _ in range(5)] for _ in range(2)] for _ in range(2)]	# values[weekly/daily][cid][time/temp/humi/pres/volt]
  for span in range(2):
    for cid in range(2):
      for buf in data[span][cid]:
        if not buf:
          continue
        time, _, temp, humi, pres, volt = buf.split(',')
        values[span][cid][0].append(datetime.datetime.fromisoformat(time))
        values[span][cid][1].append(float(temp))
        values[span][cid][2].append(float(humi))
        if pres:
          values[span][cid][3].append(float(pres))
        values[span][cid][4].append(float(volt))

  # Plot the charts.
  charts = [[None] * 4 for _ in range(2)]	# charts[weekly/daily][temp/humi/pres/volt]
  for span, fmt in enumerate(['%m/%d', '%H:%M']):
    for i, (title, unit) in enumerate([('Temperature', '℃'), ('Humidity', '%'), ('Pressure', 'hPa'), ('Battery', 'V')]):
      charts[span][i] = plot_chart(title, unit, values[span][0][0], values[span][0][1 + i], values[span][1][0], values[span][1][1 + i], fmt)
  latest0 = get_latest(values[1][0])
  latest1 = get_latest(values[1][1])

  # Print the HTML page.
  print('Content-Type: text/html; charset=UTF-8')
  print('')
  print('<!DOCTYPE html>');
  print('<html>');
  print('<head><title>Weather Station</title></head>');
  print('<body>');
  print('<h2>%s<br>%s</h2>' % (latest0, latest1))
  print('<h1>Daily</h1>');
  print('<div style="text-align: center;">');
  print('<img src="data:image/png;base64,%s">' % charts[1][0])
  print('<img src="data:image/png;base64,%s">' % charts[1][1])
  print('<img src="data:image/png;base64,%s">' % charts[1][2])
  print('<img src="data:image/png;base64,%s">' % charts[1][3])
  print('</div>')
  print('<h1>Weekly</h1>');
  print('<div style="text-align: center;">');
  print('<img src="data:image/png;base64,%s">' % charts[0][0])
  print('<img src="data:image/png;base64,%s">' % charts[0][1])
  print('<img src="data:image/png;base64,%s">' % charts[0][2])
  print('<img src="data:image/png;base64,%s">' % charts[0][3])
  print('</div>')
  print('</body>');
  print('</html>');

def main():
  form = cgi_FieldStorage()
  if 'id' in form:
    collect(form)
  else:
    render()

if __name__ == '__main__':
  main()

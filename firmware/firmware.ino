// Weather Station Sensor with BME280/AHT25.
// 2021-12-23,2022-02-23,2023-05-28  T. Nakagawa

#define STID 0	// Station ID.
#if STID == 0
#define SENSOR 0	// 0:BME280, 1:AHT25.
#define VOLTAGE_ADJUST (3.30f / 3.67f)
#define HALL_NEUTRAL -29
#elif STID == 1
#define SENSOR 1	// 0:BME280, 1:AHT25.
#define VOLTAGE_ADJUST (3.30f / 3.43f)
#define HALL_NEUTRAL -25
#elif STID == 2
#define SENSOR 1	// 0:BME280, 1:AHT25.
#define VOLTAGE_ADJUST (3.30f / 3.65f)
#define HALL_NEUTRAL -72
#endif

#include <Preferences.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/adc.h>
#include <lwip/etharp.h>
#include <soc/rtc_cntl_reg.h>
#if SENSOR == 0
#include "BME280.h"
#else
#include "AHT25.h"
#endif

extern "C" int rom_phy_get_vdd33();

constexpr int PIN_SDA = 21;
constexpr int PIN_SCL = 22;
constexpr int PIN_VCC = 23;

Preferences preferences;
#if SENSOR == 0
BME280 sensor(PIN_SDA, PIN_SCL);
#else
AHT25 sensor(PIN_SDA, PIN_SCL);
#endif

RTC_DATA_ATTR int active_time = 0;

// This function must be called immediately after enabling WiFi/BT.
float getVoltage() {
  int v = 0;
  for (int i = 0; i < 10; i++) v += rom_phy_get_vdd33();
  v /= 10;
  const float vdd =  (0.0005045f * v + 0.3368f) * VOLTAGE_ADJUST;
  return vdd;
}

String urlDecode(const String &str) {
  String result;
  for (int i = 0; i < str.length(); i++) {
    const char c = str[i];
    if (c == '+') {
      result.concat(" ");
    } else if (c == '%' && i + 2 < str.length()) {
      const char c0 = str[++i];
      const char c1 = str[++i];
      unsigned char d = 0;
      d += (c0 <= '9') ? c0 - '0' : (c0 <= 'F') ? c0 - 'A' + 10 : c0 - 'a' + 10;
      d <<= 4;
      d += (c1 <= '9') ? c1 - '0' : (c1 <= 'F') ? c1 - 'A' + 10 : c1 - 'a' + 10;
      result.concat((char)d);
    } else {
      result.concat(c);
    }
  }
  return result;
}

void config() {
  Serial.println("Configuration mode.");
  preferences.begin("config", false);
  Serial.println("Free entries: " + String(preferences.freeEntries()));
  WiFi.mode(WIFI_AP);
  WiFi.softAP("ESP32", "12345678");
  delay(100);
  WiFi.softAPConfig(IPAddress(192, 168, 0, 1), IPAddress(192, 168, 0, 1), IPAddress(255, 255, 255, 0));

  WiFiServer server(80);
  server.begin();
  while (true) {
    WiFiClient client = server.available();
    if (client) {
      const String line = client.readStringUntil('\n');
      Serial.println("Accessed: " + line);
      String message;
      if (line.startsWith("GET /?")) {
        String key;
        String val;
        String buf = line.substring(6);
        int pos = buf.indexOf(" ");
        if (pos < 0) pos = 0;
        buf = buf.substring(0, pos);
        buf.concat("&");
        while (buf.length()) {
          int pos = buf.indexOf("&");
          const String param = buf.substring(0, pos);
          buf = buf.substring(pos + 1);
          pos = param.indexOf("=");
          if (pos < 0) continue;
          if (param.substring(0, pos) == "key") key = urlDecode(param.substring(pos + 1));
          else if (param.substring(0, pos) == "val") val = urlDecode(param.substring(pos + 1));
        }
        key.trim();
        val.trim();
        Serial.println("key=" + key + ", val=" + val);
        if (key == "QUIT") {
          Serial.println("Quit the configuration mode.");
          break;
        } else if (key == "LIST") {
          for (const char *k : {"SSID", "PASS", "CHAN", "ADRS", "GATE", "MASK", "HOST", "WAIT"}) {
            const String v = preferences.getString(k);
            message += String(k) + "=" + v + "<br>";
          }
        } else if (key.length()) {
          preferences.putString(key.c_str(), val);
          if (preferences.getString(key.c_str()) == val) {
            message = "Succeeded to update: " + key;
          } else {
            message = "Failed to write: " + key;
          }
        } else {
          message = "Key was not specified.";
        }
      }

      client.println("<!DOCTYPE html>");
      client.println("<html>");
      client.println("<head><title>Configuration</title></head>");
      client.println("<body>");
      client.println("<h1>Configuration</h1>");
      client.println("<form action=\"/\" method=\"get\">Key: <input type=\"text\" name=\"key\" size=\"10\"> Value: <input type=\"text\" name=\"val\" size=\"20\"> <input type=\"submit\"></form>");
      client.println("<p>" + message + "</p>");
      client.println("</body>");
      client.println("</html>");
      client.stop();
    }
  }
  server.end();
  WiFi.disconnect(true);

  // Connect to the AP for storing the AP information.
  Serial.println("Connecting to AP.");
  WiFi.persistent(true);
  WiFi.mode(WIFI_STA);
  WiFi.begin(preferences.getString("SSID").c_str(), preferences.getString("PASS").c_str(), preferences.getString("CHAN").toInt());
  while (true) ;
}

void sendData(int stid, float temp, float humi, float pres, float volt) {
  // Generate the message.
  String buf;
  buf += "wst";
  buf += " " + String(stid);
  buf += "," + String(temp, 1);
  buf += "," + String(humi, 1);
  buf += "," + String(pres, 1);
  buf += "," + String(volt, 2);
  buf += "," + String(active_time);
  Serial.println("Data: " + buf);

  // Get the host IP address.
  const String host = preferences.getString("HOST");
  IPAddress adrs;
  if (!adrs.fromString(host)) {
    if (WiFi.hostByName(host.c_str(), adrs) != 1) return;
  }

  // Get an ARP response.
  ip4_addr req_ip;
  ip4_addr_set_u32(&req_ip, adrs);
  etharp_request(netif_default, &req_ip);
  eth_addr *ret_eth;
  ip4_addr const *ret_ip;
  while (etharp_find_addr(netif_default, &req_ip, &ret_eth, &ret_ip) < 0 && millis() < 5000) delay(1);

  // Send a UDP packet.
  WiFiUDP udp;
  udp.begin(50000);
  udp.beginPacket(adrs, 514);
  udp.write((const uint8_t *)buf.c_str(), buf.length());
  udp.endPacket();
  delay(10);
  udp.stop();
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);  // Disable brown-out detection.
  Serial.begin(115200);
  while (!Serial) ;
  Serial.println("Weather Station " + String(STID));

  // Check the hall sensor.
  int h = 0;
  for (int i = 0; i < 10; i++) h += hall_sensor_read();
  h /= 10;
  Serial.println("Hall sensor: " + String(h));
  if (h < HALL_NEUTRAL - 30 || h > HALL_NEUTRAL + 30) config();
  preferences.begin("config", true);

  // Get the temperature and humidity.
  pinMode(PIN_VCC, OUTPUT);
  digitalWrite(PIN_VCC, HIGH);
  delay(100);
  sensor.begin();
  float temp, humi, pres;
  for (int i = 0; i < 10; i++) sensor.get(temp, humi, pres);	// Wait until the sensor outputs become stable.
  sensor.get(temp, humi, pres);
  digitalWrite(PIN_VCC, LOW);
  Serial.println("Temperature: " + String(temp) + " C");
  Serial.println("Humidity: " + String(humi) + " %");
  Serial.println("Pressure: " + String(pres) + " hPa");

  // Enable WiFi.
  const uint32_t wifi_start = millis();
  Serial.println("Connecting WiFi... " + String(millis()));
  WiFi.persistent(false);
  IPAddress adrs, gate, mask;
  if (adrs.fromString(preferences.getString("ADRS")) &&
      gate.fromString(preferences.getString("GATE")) &&
      mask.fromString(preferences.getString("MASK"))) {
    Serial.println("DHCP is not used.");
    WiFi.config(adrs, gate, mask);
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin();
  while (WiFi.status() != WL_CONNECTED && millis() < 5000) delay(1);

  // Get the battery voltage.
  Serial.println("Measuring voltage... " + String(millis()));
  const float volt = getVoltage();
  Serial.println("Battery voltage: " + String(volt) + " V");

  // Send the data.
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("Sending the data... " + String(millis()));
    sendData(STID, temp, humi, pres, volt);
  }

  // Disable WiFi.
  Serial.println("Disconnecting... " + String(millis()));
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  active_time = (int)(millis() - wifi_start);
  Serial.println("WiFi active time: " + String(active_time));

  float wait = preferences.getString("WAIT").toFloat();
  if (wait < 1.0f) wait = 10.0f;
  const int sleep = wait * 60 * 1000 * 1000;
  esp_sleep_enable_timer_wakeup(sleep);
  Serial.println("Sleeping time: " + String(sleep));
  Serial.println("Sleeping... " + String(millis()));
  esp_deep_sleep_start();
}
 
void loop() {
}

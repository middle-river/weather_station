// Weather Station Sensor with AHT25.
// 2021-12-23  T. Nakagawa

#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <soc/rtc_cntl_reg.h>
#include "AHT25.h"

extern "C" int rom_phy_get_vdd33();

constexpr int SHUTDOWN_VOLTAGE = 2.7;
constexpr int PIN_SDA = 21;
constexpr int PIN_SCL = 22;
constexpr int PIN_VCC = 23;

Preferences preferences;
AHT25 aht25(PIN_SDA, PIN_SCL);

float getVoltage() {
  btStart();
  delay(1000);
  float vdd = 0.0f;
  for (int i = 0; i < 100; i++) {
    delay(10);
    vdd += rom_phy_get_vdd33();
  }
  btStop();
  vdd /= 100.0f;
  vdd = -0.0000135277f * vdd * vdd + 0.0128399f * vdd + 0.474502f;
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
        if (key.length()) {
          preferences.putString(key.c_str(), val);
          if (preferences.getString(key.c_str()) == val) {
            message = "Succeeded to update: " + key;
          } else {
            message = "Failed to write: " + key;
          }
        } else {
          message = "Key was not found.";
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
}

void sendData(int id, float temp, float humi, float volt) {
  const String url = preferences.getString("UURL");
  Serial.println("URL: " + url);
  HTTPClient client;
  client.begin(url);
  client.addHeader("Content-Type", "application/x-www-form-urlencoded");
  String payload = "id=" + String(id);
  payload.concat("&temp=" + String(temp, 2));
  payload.concat("&humi=" + String(humi, 2));
  payload.concat("&volt=" + String(volt, 2));
  const int response = client.POST(payload);
  Serial.println("Response code: " + String(response));
  client.end();
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);  // Disable brown-out detection.
  Serial.begin(115200);
  while (!Serial) ;
  Serial.println("Weather Station Sensor with AHT25.");

  const int h = hallRead();
  Serial.println("Hall sensor: " + String(h));
  if (h < 10 || h > 70) config();
  preferences.begin("config", true);

  // Get the battery voltage.
  const float volt = getVoltage();
  Serial.println("Battery voltage: " + String(volt) + " V");
  if (volt < SHUTDOWN_VOLTAGE) {
    Serial.println("Battery voltage is low. Shutting down.");
    esp_deep_sleep_start();  // Sleep indefinitely.
  }

  // Get the temperature and humidity.
  pinMode(PIN_VCC, OUTPUT);
  digitalWrite(PIN_VCC, HIGH);
  delay(100);
  aht25.begin();
  float temp, humi;
  for (int i = 0; i < 3; i++) aht25.get(temp, humi);	// Wait until the sensor outputs become stable.
  aht25.get(temp, humi);
  digitalWrite(PIN_VCC, LOW);
  Serial.println("Temperature: " + String(temp) + " C");
  Serial.println("Humidity: " + String(humi) + " %");

  // Enable WiFi.
  WiFi.mode(WIFI_STA);
  WiFi.begin(preferences.getString("SSID").c_str(), preferences.getString("PASS").c_str());
  Serial.print("Connecting WiFi.");
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() >= 30000) break;
    delay(500);
    Serial.print(".");
  }
  Serial.println("");

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("Sending the data.");
    sendData(1, temp, humi, volt);
  }

  // Disable WiFi.
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);

  // Deep sleep.
  Serial.println("Awake time: " + String(millis() / 1000.0f, 2) + " sec.");
  Serial.println("Sleeping.");
  esp_sleep_enable_timer_wakeup(9.5f * 60 * 1000 * 1000);	// Sleep for 9.5 minute.
  esp_deep_sleep_start();
}
 
void loop() {
}

// Library for AHT25 Temperature/Humidity Sensor.
// 2021-12-23  T. Nakagawa

#include <Wire.h>

class AHT25 {
private:
  void write(int size, const uint8_t *data) {
    Wire.beginTransmission(ADDRESS);
    for (int i = 0; i < size; i++) Wire.write(data[i]);
    Wire.endTransmission();
  }

  static constexpr int ADDRESS = 0x38;
  int sda_;
  int scl_;

public:
  AHT25(int sda, int scl) : sda_(sda), scl_(scl) {
  }

  void begin() {
    Wire.begin(sda_, scl_);
    write(1, (const uint8_t *)"\xe1");	// Initialization.
    delay(100);
  }

  void get(float &temp, float &humi) {
    write(3, (const uint8_t *)"\xac\x33\x00");	// Trigger measurement.
    delay(100);
    Wire.requestFrom(ADDRESS, 6);
    uint8_t data[6];
    for (int i = 0; i < 6; i++) if (Wire.available()) data[i] = Wire.read();
    const uint32_t tmp_humi = (data[1] << 12) | (data[2] << 4) | (data[3] >> 4);
    const uint32_t tmp_temp = ((data[3] & 0x0f) << 16) | (data[4] << 8) | data[5];
    humi = tmp_humi / (float)(1 << 20) * 100.0f;
    temp = tmp_temp / (float)(1 << 20) * 200.0f - 50.0f;
  }
};

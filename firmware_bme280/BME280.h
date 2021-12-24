// Library for BME280 Temperature/Humidity/Pressure Sensor (I2C).
// 2021-12-20  T. Nakagawa

#include <Wire.h>

class BME280 {
private:
  void write(uint8_t adrs, uint8_t data) {
    Wire.beginTransmission(ADDRESS);
    Wire.write(adrs);
    Wire.write(data);
    Wire.endTransmission();
  }

  void write(uint8_t adrs) {
    Wire.beginTransmission(ADDRESS);
    Wire.write(adrs);
    Wire.endTransmission();
  }

  uint8_t readU8(uint8_t adrs) {
    write(adrs);
    Wire.requestFrom(ADDRESS, 1);
    const uint8_t d0 = Wire.read();
    return d0;
  }

  uint16_t readU16(uint8_t adrs) {
    write(adrs);
    Wire.requestFrom(ADDRESS, 2);
    const uint8_t d0 = Wire.read();
    const uint8_t d1 = Wire.read();
    return (((uint16_t)d1 << 8) | d0);
  }

  int32_t compensateT(int32_t adc_t, int32_t &t_fine) {
    const int32_t var1  = ((((adc_t >> 3) - ((int32_t)dig_t1_ << 1))) * ((int32_t)dig_t2_)) >> 11;
    const int32_t var2  = (((((adc_t >> 4) - ((int32_t)dig_t1_)) * ((adc_t >> 4) - ((int32_t)dig_t1_))) >> 12) * ((int32_t)dig_t3_)) >> 14;
    t_fine = var1 + var2;
    int32_t t  = (t_fine * 5 + 128) >> 8;
    return t;
  }

  uint32_t compensateH(int32_t adc_h, int32_t t_fine) {
    int32_t v_x1_u32r = (t_fine - ((int32_t)76800)); 
    v_x1_u32r = (((((adc_h << 14) - (((int32_t)dig_h4_) << 20) - (((int32_t)dig_h5_) * v_x1_u32r)) + ((int32_t)16384)) >> 15) * (((((((v_x1_u32r * ((int32_t)dig_h6_)) >> 10) * (((v_x1_u32r * ((int32_t)dig_h3_)) >> 11) + ((int32_t)32768))) >> 10) + ((int32_t)2097152)) * ((int32_t)dig_h2_) + 8192) >> 14));
    v_x1_u32r = (v_x1_u32r - (((((v_x1_u32r >> 15) * (v_x1_u32r >> 15)) >> 7) * ((int32_t)dig_h1_)) >> 4));
    v_x1_u32r = (v_x1_u32r < 0 ? 0 : v_x1_u32r);
    v_x1_u32r = (v_x1_u32r > 419430400 ? 419430400 : v_x1_u32r);
    return (uint32_t)(v_x1_u32r >> 12);
  }

  int32_t compensateP(int32_t adc_p, int32_t t_fine) {
    int32_t var1 = (((int32_t)t_fine) >> 1) - (int32_t)64000;
    int32_t var2 = (((var1 >> 2) * (var1 >> 2)) >> 11 ) * ((int32_t)dig_p6_);
    var2 = var2 + ((var1 * ((int32_t)dig_p5_)) << 1);
    var2 = (var2 >> 2) + (((int32_t)dig_p4_) << 16);
    var1 = (((dig_p3_ * (((var1 >> 2) * (var1 >> 2)) >> 13 )) >> 3) + ((((int32_t)dig_p2_) * var1) >> 1)) >> 18;
    var1 =((((32768 + var1)) * ((int32_t)dig_p1_)) >> 15);
    if (var1 == 0) return 0;
    uint32_t p = (((uint32_t)(((int32_t)1048576) - adc_p) - (var2 >> 12))) * 3125;
    if (p < 0x80000000) {
      p = (p << 1) / ((uint32_t)var1);
    } else {
      p = (p / (uint32_t)var1) * 2;
    }
    var1 = (((int32_t)dig_p9_) * ((int32_t)(((p >> 3) * (p >> 3)) >> 13))) >> 12;
    var2 = (((int32_t)(p >> 2)) * ((int32_t)dig_p8_)) >> 13;
    p = (uint32_t)((int32_t)p + ((var1 + var2 + dig_p7_) >> 4));
    return p;
  }

  static constexpr int ADDRESS = 0x76;
  int sda_;
  int scl_;
  uint16_t dig_t1_;
  int16_t dig_t2_;
  int16_t dig_t3_;
  uint16_t dig_p1_;
  int16_t dig_p2_;
  int16_t dig_p3_;
  int16_t dig_p4_;
  int16_t dig_p5_;
  int16_t dig_p6_;
  int16_t dig_p7_;
  int16_t dig_p8_;
  int16_t dig_p9_;
  uint8_t dig_h1_;
  int16_t dig_h2_;
  uint8_t dig_h3_;
  int16_t dig_h4_;
  int16_t dig_h5_;
  int8_t dig_h6_;

public:
  BME280(int sda, int scl) : sda_(sda), scl_(scl) {
  }

  void begin() {
    Wire.begin(sda_, scl_);
    write(0xf5, 0x00);	// CONFIG (Filter off).
    write(0xf4, 0x24);	// CTRL_MEAS (Temperature oversampling x1, Pressure oversampling x1, Sleep mode).
    write(0xf2, 0x01);	// CTRL_HUM (Humidity oversampling x1).

    // Compensation parameters.
    dig_t1_ = readU16(0x88);
    dig_t2_ = (int16_t)readU16(0x8a);
    dig_t3_ = (int16_t)readU16(0x8c);
    dig_p1_ = readU16(0x8e);
    dig_p2_ = (int16_t)readU16(0x90);
    dig_p3_ = (int16_t)readU16(0x92);
    dig_p4_ = (int16_t)readU16(0x94);
    dig_p5_ = (int16_t)readU16(0x96);
    dig_p6_ = (int16_t)readU16(0x98);
    dig_p7_ = (int16_t)readU16(0x9a);
    dig_p8_ = (int16_t)readU16(0x9c);
    dig_p9_ = (int16_t)readU16(0x9e);
    dig_h1_ = readU8(0xa1);
    dig_h2_ = (int16_t)readU16(0xe1);
    dig_h3_ = readU8(0xe3);
    dig_h4_ = (int16_t)((readU8(0xe4) << 4) | (readU8(0xe5) & 0x0f));
    dig_h5_ = (int16_t)((readU8(0xe6) << 4) | (readU8(0xe5) >> 4));
    dig_h6_ = readU8(0xe7);
  }

  void get(float &temp, float &humi, float &pres) {
    write(0xf4, 0x25);	// CTRL_MEAS (Forced mode).
    write(0xf7);
    Wire.requestFrom(ADDRESS, 8);
    uint8_t data[8];
    for (int i = 0; i < 8; i++) data[i] = Wire.read();
    const uint32_t tmp_pres = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4);
    const uint32_t tmp_temp = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4);
    const uint32_t tmp_humi = (data[6] << 8) | (data[7]);
    int32_t t_fine;
    temp = compensateT(tmp_temp, t_fine) / 100.0f;
    humi = compensateH(tmp_humi, t_fine) / 1024.0f;
    pres = compensateP(tmp_pres, t_fine) / 100.0f;
  }
};

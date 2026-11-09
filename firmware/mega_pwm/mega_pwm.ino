// SPDX-License-Identifier: Apache-2.0
#include <Wire.h>
#include <stdlib.h>
#include <string.h>

// Adafruit PCA9685 shield, default hardware address. No Mega servo/feedback pins.
constexpr uint8_t ADDRESS = 0x40;
constexpr uint8_t ALL_OFF_H = 0xfd;
constexpr uint16_t MAX_MS = 1000;
constexpr uint16_t MIN_US = 1400, MAX_US = 1600;
constexpr uint32_t ARM_MS = 2000;
bool healthy = false, armed = false, active = false;
uint32_t armUntil, stopAt, nextOffRetry;
char line[64];
uint8_t used = 0;
bool discard = false;

bool writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(ADDRESS);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

int readRegister(uint8_t reg) {
  Wire.beginTransmission(ADDRESS);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom(ADDRESS, uint8_t(1)) != 1) return -1;
  return Wire.read();
}

bool allOff() {
  armed = active = false;
  bool ok = writeRegister(ALL_OFF_H, 0x10);
  if (!ok) healthy = false;
  return ok;
}

bool setPulse(uint8_t channel, uint16_t microseconds) {
  // Nominal 25 MHz oscillator and prescale=121. Actual pulse width is unmeasured.
  uint16_t ticks = (microseconds * 25UL + 61) / 122;
  uint8_t reg = 0x06 + 4 * channel;
  Wire.beginTransmission(ADDRESS);
  Wire.write(reg);
  Wire.write(0); Wire.write(0);
  Wire.write(ticks & 0xff); Wire.write(ticks >> 8);
  return Wire.endTransmission() == 0 &&
      readRegister(reg) == 0 && readRegister(reg + 1) == 0 &&
      readRegister(reg + 2) == (ticks & 0xff) && readRegister(reg + 3) == (ticks >> 8);
}

bool elapsed(uint32_t now, uint32_t deadline) { return (int32_t)(now - deadline) >= 0; }

bool number(const char *token, uint16_t low, uint16_t high, uint16_t &value) {
  if (!token || !*token) return false;
  uint32_t parsed = 0;
  for (; *token; ++token) {
    if (*token < '0' || *token > '9') return false;
    parsed = parsed * 10 + (*token - '0');
    if (parsed > high) return false;
  }
  if (parsed < low) return false;
  value = parsed;
  return true;
}

void reject(const __FlashStringHelper *reason) {
  bool stopped = allOff();
  Serial.print(F("ERR "));
  Serial.println(stopped ? reason : F("I2C"));
}

void command() {
  char *state;
  const char *verb = strtok_r(line, " ", &state);
  if (!verb) return;
  if (!strcmp(verb, "STOP")) {
    Serial.println(allOff() ? F("OK STOP") : F("ERR I2C"));
    return;
  }
  const char *arg = strtok_r(nullptr, " ", &state);
  if (!strcmp(verb, "HELLO") && !arg) { Serial.println(F("HOME_BOT_PWM 1")); return; }
  if (!strcmp(verb, "STATUS") && !arg) {
    Serial.println(!healthy ? F("STATUS FAULT") : active ? F("STATUS ACTIVE") : armed ? F("STATUS ARMED") : F("STATUS OFF"));
    return;
  }
  if (!healthy) { reject(F("I2C")); return; }
  if (!strcmp(verb, "VERIFY") && !arg && !active && !armed) {
    uint16_t mask = 0;
    int prescale = readRegister(0xfe);
    for (uint8_t i = 0; i < 16 && prescale >= 0; ++i) {
      int off = readRegister(0x09 + i * 4);
      if (off < 0) { prescale = -1; break; }
      if (off & 0x10) mask |= uint16_t(1) << i;
    }
    int mode1 = readRegister(0x00), mode2 = readRegister(0x01);
    if (prescale != 121 || mask != 0xffff || mode1 < 0 || (mode1 & 0x70) != 0x20 || mode2 != 0x04) {
      healthy = false; reject(F("READBACK")); return;
    }
    Serial.println(F("PWM 0x40 121 FFFF"));
    return;
  }
  if (!strcmp(verb, "ARM") && !arg && !active) {
    armed = true;
    armUntil = millis() + ARM_MS;
    Serial.println(F("OK ARM"));
    return;
  }
  if (strcmp(verb, "PULSE")) { reject(F("COMMAND")); return; }
  if (!armed || active || elapsed(millis(), armUntil)) { reject(F("DISARMED")); return; }

  uint16_t duration, channels[2], widths[2];
  if (!number(arg, 20, MAX_MS, duration)) { reject(F("DURATION")); return; }
  uint8_t count = 0;
  while ((arg = strtok_r(nullptr, " ", &state))) {
    if (count == 2 || !number(arg, 0, 15, channels[count]) ||
        !number(strtok_r(nullptr, " ", &state), MIN_US, MAX_US, widths[count]) ||
        (count && channels[0] == channels[count])) { reject(F("CHANNEL_OR_WIDTH")); return; }
    ++count;
  }
  if (!count) { reject(F("CHANNEL_OR_WIDTH")); return; }
  armed = false;
  // The deadline is set before the first write, even for paired channels.
  stopAt = millis() + duration;
  for (uint8_t i = 0; i < count; ++i) {
    if (!setPulse(channels[i], widths[i])) { healthy = false; reject(F("READBACK")); return; }
  }
  active = true;
  Serial.println(F("OK PULSE"));
}

void setup() {
  Wire.begin();
  Wire.setWireTimeout(3000, true);
  // Disable every output before configuring the oscillator or accepting commands.
  healthy = allOff() && writeRegister(0x00, 0x30) && writeRegister(0x01, 0x04) &&
      writeRegister(0xfe, 121) && writeRegister(0x00, 0x20);
  delayMicroseconds(600);
  if (healthy) healthy = writeRegister(0x00, 0xa0) && allOff();
  Serial.begin(115200);
  Serial.println(F("HOME_BOT_PWM 1"));
  Serial.println(healthy ? F("STATUS OFF") : F("STATUS FAULT"));
}

void loop() {
  uint32_t now = millis();
  if (armed && elapsed(now, armUntil)) armed = false;
  if (active && elapsed(now, stopAt)) Serial.println(allOff() ? F("DONE OFF") : F("ERR I2C"));
  if (!healthy && elapsed(now, nextOffRetry)) {
    nextOffRetry = now + 100;
    allOff(); // Retry the stop if the bus returns; do not automatically rearm.
  }
  for (uint8_t i = 0; i < 16 && Serial.available(); ++i) {
    int c = Serial.read();
    if (c == '\n') {
      if (!discard) { line[used] = 0; command(); }
      used = 0; discard = false;
    } else if (c != '\r' && !discard) {
      if (c < 32 || c > 126 || used >= sizeof(line) - 1) {
        discard = true;
        reject(F("LINE"));
      } else line[used++] = c;
    }
  }
}

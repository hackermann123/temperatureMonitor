/*
 * Temperature Monitoring System - Arduino Sketch v2
 * With improved diagnostics and Serial Monitor messages
 * 
 * Reads DS18B20 OneWire sensors and sends both temperature data
 * and diagnostic messages to Serial Monitor
 * 
 * Supports up to 10 sensors on the OneWire bus
 */

#include <OneWire.h>

// ============================================================================
// CONFIGURATION
// ============================================================================

#define ONE_WIRE_BUS 2           // OneWire data line on digital pin 2
#define SENSOR_TIMEOUT 1000      // Milliseconds to wait for sensor response
#define MAX_SENSORS 10           // Maximum number of sensors to track
#define READ_INTERVAL 1000       // Milliseconds between sensor reads
#define RESCAN_INTERVAL 10000    // Milliseconds between rescans (10 seconds)

// ============================================================================
// GLOBAL VARIABLES
// ============================================================================

OneWire ds(ONE_WIRE_BUS);
byte found_sensors = 0;
byte sensor_addresses[MAX_SENSORS][8];
unsigned long last_read_time = 0;
unsigned long last_rescan_time = 0;
unsigned long last_broadcast = 0;

void rescan_sensors();
void read_all_sensors();
void handle_serial_command(String command);
void print_address(byte* addr);
String format_sensor_address(byte* addr);
float read_temperature(byte* addr);
bool start_conversion(byte* addr);

// ============================================================================
// SETUP
// ============================================================================

void setup(void) {
  Serial.begin(9600);
  delay(1000);
  
  // Print startup info
  Serial.println("[INFO] Temperature Monitoring System Started");
  Serial.println("[INFO] Searching for OneWire sensors...");
  
  // Initial sensor scan
  rescan_sensors();
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop(void) {
  // Periodic rescan (every 60 seconds)
  if (millis() - last_rescan_time > RESCAN_INTERVAL) {
    rescan_sensors();
    last_rescan_time = millis();
  }
  
  // Read sensors periodically
  if (millis() - last_read_time > READ_INTERVAL) {
    read_all_sensors();
    last_read_time = millis();
  }
  
  // Check for serial commands
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    handle_serial_command(command);
  }
  
  delay(10);
}

// ============================================================================
// SENSOR SCANNING
// ============================================================================

void rescan_sensors(void) {
  Serial.println("[INFO] Starting sensor rescan...");
  
  found_sensors = 0;
  ds.reset_search();
  byte addr[8];
  
  // Search for all OneWire devices
  while (ds.search(addr)) {
    if (found_sensors >= MAX_SENSORS) {
      Serial.println("[WARN] Maximum sensor limit reached, ignoring additional sensors");
      break;
    }
    
    // Check if it's a DS18B20 (0x28) or DS18S20 (0x10)
    if (addr[0] == 0x28 || addr[0] == 0x10) {
      // Store address
      for (int i = 0; i < 8; i++) {
        sensor_addresses[found_sensors][i] = addr[i];
      }
      
      // Print address
      Serial.print("[INFO] Found sensor ");
      Serial.print(found_sensors + 1);
      Serial.print(": ");
      print_address(addr);
      Serial.println();
      
      found_sensors++;
    } else {
      Serial.print("[WARN] Unknown device type 0x");
      Serial.println(addr[0], HEX);
    }
  }
  
  // Print summary
  Serial.print("[INFO] RESCAN_COMPLETE:");
  Serial.print(found_sensors);
  Serial.println("_SENSORS_FOUND");
  
  if (found_sensors == 0) {
    Serial.println("[ERROR] No temperature sensors found on OneWire bus!");
  }
}

// ============================================================================
// SENSOR READING
// ============================================================================

void read_all_sensors(void) {
  if (found_sensors == 0) {
    // Only print occasionally to avoid spam
    if (millis() - last_broadcast > 10000) {
      Serial.println("[ERROR] No sensors available to read");
      last_broadcast = millis();
    }
    return;
  }
  
  // First pass: issue temperature conversion command to all sensors
  for (int i = 0; i < found_sensors; i++) {
    if (!start_conversion(sensor_addresses[i])) {
      Serial.print("[ERROR] Failed to start conversion for sensor ");
      Serial.println(i + 1);
    }
  }
  
  // Wait for conversion to complete (max 750ms for 12-bit)
  delay(800);
  
  // Second pass: read temperatures from all sensors
  String output = "";
  bool all_ok = true;
  
  for (int i = 0; i < found_sensors; i++) {
    float temp = read_temperature(sensor_addresses[i]);
    
    if (temp == -999.0) {
      // Read failed
      Serial.print("[ERROR] CRC_FAILED for sensor ");
      Serial.println(i + 1);
      all_ok = false;
      continue;
    }
    
    // Add to output string
    if (output.length() > 0) {
      output += ",";
    }
    
    // Add sensor address and temperature
    output += format_sensor_address(sensor_addresses[i]);
    output += ":";
    output += String(temp, 2);
  }
  
  // Send all temperatures together
  if (output.length() > 0) {
    Serial.println(output);
  } else if (!all_ok) {
    Serial.println("[ERROR] Failed to read any sensor temperatures");
  }
}

bool start_conversion(byte* addr) {
  ds.reset();
  ds.select(addr);
  ds.write(0x44, 1);  // Start temperature conversion
  return true;
}

float read_temperature(byte* addr) {
  byte data[12];
  
  // Reset, select, and read scratchpad
  ds.reset();
  ds.select(addr);
  ds.write(0xBE);  // Read scratchpad
  
  // Read 9 bytes
  for (int i = 0; i < 9; i++) {
    data[i] = ds.read();
  }
  
  // Verify CRC
  byte crc = OneWire::crc8(data, 8);
  if (crc != data[8]) {
    return -999.0;  // CRC error
  }
  
  // Convert raw temperature
  int16_t raw = (data[1] << 8) | data[0];
  
  // Account for resolution setting
  byte cfg = (data[4] & 0x60);
  if (cfg == 0x00) raw = raw & ~7;      // 9-bit
  else if (cfg == 0x20) raw = raw & ~3;  // 10-bit
  else if (cfg == 0x40) raw = raw & ~1;  // 11-bit
  
  float celsius = (float)raw / 16.0;
  
  return celsius;
}

// ============================================================================
// SERIAL COMMAND HANDLING
// ============================================================================

void handle_serial_command(String command) {
  if (command.length() == 0) {
    return;
  }
  
  Serial.print("[INFO] Received command: ");
  Serial.println(command);
  
  if (command == "RESCAN") {
    rescan_sensors();
  }
  else if (command == "STATUS") {
    Serial.print("[INFO] Found ");
    Serial.print(found_sensors);
    Serial.println(" temperature sensor(s)");
  }
  else if (command == "TEST") {
    Serial.println("[INFO] Test message - System is responding");
  }
  else {
    Serial.print("[WARN] Unknown command: ");
    Serial.println(command);
  }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

void print_address(byte* addr) {
  for (int i = 0; i < 8; i++) {
    if (addr[i] < 16) {
      Serial.print("0");
    }
    Serial.print(addr[i], HEX);
  }
}

String format_sensor_address(byte* addr) {
  String result = "";
  for (int i = 0; i < 8; i++) {
    if (addr[i] < 16) {
      result += "0";
    }
    result += String(addr[i], HEX);
  }
  return result;
}

// ============================================================================
// EXAMPLE MESSAGE FORMATS
// ============================================================================

/*
 * The system sends various message types for debugging:
 * 
 * TEMPERATURE DATA:
 * 281234567890ab:25.50,289876543210cd:26.30
 * 
 * INFO MESSAGES:
 * [INFO] Temperature Monitoring System Started
 * [INFO] Found sensor 1: 281234567890ab
 * [INFO] RESCAN_COMPLETE:2_SENSORS_FOUND
 * [INFO] Received command: RESCAN
 * [INFO] Found 2 temperature sensor(s)
 * [INFO] Test message - System is responding
 * 
 * WARNING MESSAGES:
 * [WARN] Maximum sensor limit reached
 * [WARN] Unknown device type 0x01
 * [WARN] Unknown command: INVALID
 * 
 * ERROR MESSAGES:
 * [ERROR] No temperature sensors found on OneWire bus!
 * [ERROR] Failed to start conversion for sensor 1
 * [ERROR] CRC_FAILED for sensor 1
 * [ERROR] Failed to read any sensor temperatures
 * [ERROR] No sensors available to read
 * 
 * All messages are tagged with timestamp on the Raspberry Pi side
 * and stored in the Serial Monitor for debugging.
 */

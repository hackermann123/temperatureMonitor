// Temperature Monitoring System - Arduino Sketch
// Target: Arduino UNO with DS18B20 OneWire Sensors
// Libraries: OneWire, DallasTemperature

#include <OneWire.h>
#include <DallasTemperature.h>

// ============================================================================
// CONFIGURATION
// ============================================================================

#define ONE_WIRE_BUS 2                    // OneWire data pin on Arduino
#define SAMPLING_INTERVAL 2000            // milliseconds (2 seconds)
#define RESCAN_INTERVAL 10000             // milliseconds (10 seconds)
#define MAX_PROBES 10
#define SERIAL_BAUD 9600

// ============================================================================
// GLOBAL VARIABLES
// ============================================================================

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

// Store sensor addresses
DeviceAddress sensorAddresses[MAX_PROBES];
uint8_t sensorCount = 0;

// Timing
unsigned long lastSampleTime = 0;
unsigned long lastRescanTime = 0;

// Temperature resolution (9-12 bits)
#define TEMPERATURE_PRECISION 12

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(100);
  
  Serial.println("Temperature Monitoring System Starting...");
  Serial.print("OneWire Bus on Pin: ");
  Serial.println(ONE_WIRE_BUS);
  Serial.print("Sampling Interval: ");
  Serial.print(SAMPLING_INTERVAL);
  Serial.println(" ms");
  
  // Initialize sensors
  sensors.begin();
  sensors.setResolution(TEMPERATURE_PRECISION);
  
  // Initial scan
  scanProbes();
  
  Serial.println("System Ready!");
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  // Check for serial commands
  handleSerialCommands();
  
  // Periodic rescan (every 10 seconds)
  if (millis() - lastRescanTime >= RESCAN_INTERVAL) {
    scanProbes();
    lastRescanTime = millis();
  }
  
  // Periodic temperature sampling and transmission
  if (millis() - lastSampleTime >= SAMPLING_INTERVAL) {
    readAndTransmitTemperatures();
    lastSampleTime = millis();
  }
}

// ============================================================================
// PROBE DETECTION & SCANNING
// ============================================================================

void scanProbes() {
  /**
   * Scan OneWire bus for all connected DS18B20 probes
   * Auto-detects and addresses them
   */
  
  sensorCount = 0;
  DeviceAddress tempAddress;
  
  Serial.println("[SCAN] Starting probe detection...");
  
  // Scan for all devices on the bus
  oneWire.reset_search();
  
  while (oneWire.search(tempAddress)) {
    // Verify it's a DS18B20 (family code 0x28)
    if (tempAddress[0] == 0x28) {
      if (sensorCount < MAX_PROBES) {
        // Store address
        for (int i = 0; i < 8; i++) {
          sensorAddresses[sensorCount][i] = tempAddress[i];
        }
        
        // Print found probe
        Serial.print("[SCAN] Probe ");
        Serial.print(sensorCount + 1);
        Serial.print(" Address: ");
        printAddress(tempAddress);
        Serial.println();
        
        sensorCount++;
      }
    }
  }
  
  Serial.print("[SCAN] Total probes found: ");
  Serial.println(sensorCount);
  
  if (sensorCount == 0) {
    Serial.println("[WARN] No DS18B20 probes detected! Check connections.");
  }
}

// ============================================================================
// TEMPERATURE READING & TRANSMISSION
// ============================================================================

void readAndTransmitTemperatures() {
  /**
   * Read all probe temperatures and transmit via Serial
   * Format: "28ABC123:25.50,28DEF456:26.75"
   * This format is parsed by Flask backend
   */
  
  if (sensorCount == 0) {
    Serial.println("[WARN] No probes available");
    return;
  }
  
  // Request temperature conversion from all sensors (async)
  sensors.requestTemperatures();
  delay(10);  // Small delay for conversion
  
  // Build transmission string
  String transmissionData = "";
  
  for (int i = 0; i < sensorCount; i++) {
    // Get temperature
    float tempC = sensors.getTempC(sensorAddresses[i]);
    
    // Handle invalid readings
    if (tempC == DEVICE_DISCONNECTED_C) {
      tempC = -999.0;  // Sentinel value for disconnected
    }
    
    // Build address string (28 + hex address)
    transmissionData += "28";
    for (int j = 1; j < 8; j++) {  // Skip first byte (family code)
      if (sensorAddresses[i][j] < 16) transmissionData += "0";
      transmissionData += String(sensorAddresses[i][j], HEX);
    }
    
    // Add temperature
    transmissionData += ":";
    transmissionData += String(tempC, 2);
    
    // Add comma separator (except last probe)
    if (i < sensorCount - 1) {
      transmissionData += ",";
    }
  }
  
  // Transmit to Pi
  Serial.println(transmissionData);
}

// ============================================================================
// SERIAL COMMAND HANDLING
// ============================================================================

void handleSerialCommands() {
  /**
   * Handle commands from Raspberry Pi
   * RESCAN - Force probe rescan
   * STATUS - Report system status
   */
  
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toUpperCase();
    
    if (command == "RESCAN") {
      Serial.println("[CMD] Rescan command received");
      scanProbes();
    }
    else if (command == "STATUS") {
      Serial.print("[STATUS] Probes: ");
      Serial.print(sensorCount);
      Serial.print(", Sampling: ");
      Serial.print(SAMPLING_INTERVAL);
      Serial.println("ms");
    }
    else if (command.startsWith("INTERVAL:")) {
      // Format: INTERVAL:5000 (set to 5 seconds)
      // Note: This would require additional handling to change SAMPLING_INTERVAL dynamically
      Serial.println("[CMD] Dynamic interval adjustment not yet implemented");
    }
    else if (command.startsWith("PRECISION:")) {
      // Format: PRECISION:11 (set resolution to 11 bits)
      // Parse and set
      int newPrecision = command.substring(10).toInt();
      if (newPrecision >= 9 && newPrecision <= 12) {
        sensors.setResolution(newPrecision);
        Serial.print("[CMD] Precision set to ");
        Serial.print(newPrecision);
        Serial.println(" bits");
      }
    }
    else {
      Serial.println("[CMD] Unknown command: " + command);
    }
  }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

void printAddress(DeviceAddress deviceAddress) {
  /**
   * Print a device address in hex format
   * Example: 28AB3C500415124B
   */
  for (uint8_t i = 0; i < 8; i++) {
    if (deviceAddress[i] < 16) Serial.print("0");
    Serial.print(deviceAddress[i], HEX);
  }
}

// ============================================================================
// NOTES FOR CUSTOMIZATION
// ============================================================================

/*
 * PIN CONFIGURATION:
 * - Change ONE_WIRE_BUS to use different Arduino pin
 * - Example: #define ONE_WIRE_BUS 3 for pin 3
 * 
 * SAMPLING INTERVAL:
 * - Adjust SAMPLING_INTERVAL to change read frequency
 * - Minimum: 1000ms (1 second) - respects DS18B20 conversion time
 * - Default: 2000ms (2 seconds)
 * 
 * TEMPERATURE RESOLUTION:
 * - 9-bit:  93.75ms conversion time
 * - 10-bit: 187.5ms conversion time
 * - 11-bit: 375ms conversion time
 * - 12-bit: 750ms conversion time (maximum precision)
 * - Current: 12-bit (TEMPERATURE_PRECISION = 12)
 * 
 * TROUBLESHOOTING:
 * 1. No probes detected:
 *    - Check OneWire resistor (4.7k between data and +5V)
 *    - Verify DS18B20 power (VDD to +5V, GND to GND)
 *    - Check data line connections
 * 
 * 2. Intermittent readings:
 *    - Increase pull-up resistor if line is long (6.8k-10k)
 *    - Check for electromagnetic interference
 *    - Reduce cable length or shield cables
 * 
 * 3. Inaccurate temperatures:
 *    - Verify TEMPERATURE_PRECISION setting
 *    - Allow more time for conversion (increase SAMPLING_INTERVAL)
 * 
 * EXPANDING BEYOND 10 PROBES:
 * - Change MAX_PROBES to 20 (uses more RAM)
 * - Arduino UNO RAM: 2KB (limited to ~15-20 devices)
 * - Consider Arduino Mega for more devices
 */

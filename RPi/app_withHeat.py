# Temperature Monitoring System - Flask Backend (v6.5 - WITH HEATER CONTROL)

import os
import json
import serial
import threading
import time
from datetime import datetime
from pathlib import Path
from enum import Enum
from queue import Queue
from flask import Flask, render_template, jsonify, request, send_file
from functools import wraps
import spidev
import math

# ... [All existing imports and classes remain the same until HeaterTemperatureReader] ...

# ============================================================================
# HEATER TEMPERATURE CONTROLLER
# ============================================================================
class TemperatureSystemStateMachine:
    pass


class SerialHandler:
    pass


class SensorDataManager:
    pass


class DataLogger:
    pass


class SerialMessageQueue:
    pass
class HeaterTemperatureReader:
    """Read temperature from MCP3204 thermistor (heater circuit)"""
    
    # Thermistor configuration (from heating_control.py)
    THERMISTOR_BETA = 3984
    THERMISTOR_REFERENCE_RESISTANCE = 11450
    THERMISTOR_REFERENCE_TEMP = 21.60
    VOLTAGE_DIVIDER_RESISTOR = 2200
    SUPPLY_VOLTAGE = 3.3
    ADC_REFERENCE_VOLTAGE = 3.3
    VOLTAGE_DIVIDER_INVERTED = True
    
    def __init__(self):
        self.current_temp = None
        self.last_read_time = time.time()
        self.lock = threading.Lock()
        self.spi = None
        self.initialized = False
        
    def initialize(self):
        """Initialize SPI connection"""
        try:
            self.spi = spidev.SpiDev()
            self.spi.open(0, 0)  # /dev/spidev0.0
            self.spi.max_speed_hz = 1000000
            self.spi.mode = 0
            self.initialized = True
            print("[HEATER] SPI initialized successfully")
            return True
        except Exception as e:
            print(f"[HEATER] SPI initialization failed: {e} (non-critical, heater temp unavailable)")
            self.initialized = False
            return False
    
    def read_temperature(self):
        """Read heater thermistor temperature from MCP3204 channel 0"""
        if not self.initialized:
            return None
        
        try:
            # Read channel 0 from MCP3204
            cmd = [0x06, 0x00, 0x00]
            response = self.spi.xfer2(cmd)
            raw_value = ((response[1] & 0x0F) << 8) | response[2]
            voltage = (raw_value / 4095.0) * self.ADC_REFERENCE_VOLTAGE
            
            # Calculate temperature using voltage divider equation
            if voltage <= 0 or voltage >= self.SUPPLY_VOLTAGE:
                return None
            
            if self.VOLTAGE_DIVIDER_INVERTED:
                resistance = self.VOLTAGE_DIVIDER_RESISTOR * (self.SUPPLY_VOLTAGE - voltage) / voltage
            else:
                resistance = self.VOLTAGE_DIVIDER_RESISTOR * voltage / (self.SUPPLY_VOLTAGE - voltage)
            
            if resistance <= 0:
                return None
            
            # Steinhart-Hart equation
            T_ref_kelvin = self.THERMISTOR_REFERENCE_TEMP + 273.15
            temp_kelvin = 1.0 / (
                1.0 / T_ref_kelvin +
                (1.0 / self.THERMISTOR_BETA) * math.log(resistance / self.THERMISTOR_REFERENCE_RESISTANCE)
            )
            temp_celsius = temp_kelvin - 273.15
            
            with self.lock:
                self.current_temp = temp_celsius
            
            return temp_celsius
        except Exception as e:
            print(f"[HEATER] Error reading temperature: {e}")
            return None
    
    def get_current_temp(self):
        """Get last read temperature"""
        with self.lock:
            return self.current_temp
    
    def cleanup(self):
        """Close SPI connection"""
        if self.spi:
            try:
                self.spi.close()
            except:
                pass

# [All existing code: STATE MACHINE, SERIAL HANDLER, MESSAGE QUEUE, etc.]
# ... [Insert all existing classes and code here - NO CHANGES TO EXISTING CODE] ...

# Global managers
state_machine = TemperatureSystemStateMachine()
serial_handler = SerialHandler(use_mock=False)
data_manager = SensorDataManager()
logger = DataLogger()
serial_message_queue = SerialMessageQueue(max_messages=100)
heater_reader = HeaterTemperatureReader()

# Global logging thread
logging_thread = None
heater_target_temp = None
heater_reader_thread = None

# [Continue with existing SERIAL READER THREAD, LOGGING THREAD, FLASK ROUTES...]
# [All existing routes and code continue - add only the new/modified sections below]

# NEW ROUTES - ADD BEFORE system_status():

@app.route('/api/heater-temp', methods=['GET'])
def get_heater_temp():
    """Get current heater temperature reading"""
    try:
        temp = heater_reader.read_temperature()
        if temp is not None:
            return jsonify({
                "status": "ok",
                "temperature": round(temp, 2),
                "initialized": heater_reader.initialized
            })
        else:
            return jsonify({
                "status": "error",
                "temperature": None,
                "initialized": heater_reader.initialized,
                "error": "Failed to read temperature"
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "initialized": heater_reader.initialized
        }), 500

@app.route('/api/heater-temp', methods=['POST'])
def set_heater_target():
    """Set heater target temperature"""
    global heater_target_temp
    try:
        data = request.get_json()
        target = data.get('target')
        
        if target is None:
            return jsonify({"error": "Missing 'target' parameter"}), 400
        
        heater_target_temp = float(target)
        print(f"[HEATER] Target temperature set to {heater_target_temp}°C")
        
        return jsonify({
            "status": "ok",
            "target": heater_target_temp,
            "message": f"Heater target set to {heater_target_temp}°C"
        })
    except ValueError:
        return jsonify({"error": "Invalid temperature value"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# MODIFIED system_status ENDPOINT:

@app.route('/api/system/status', methods=['GET'])
def system_status():
    """Get system status - INCLUDES mock_mode and heater info"""
    state, logging_state, error = state_machine.get_state()
    heater_temp = heater_reader.get_current_temp()

    return jsonify({
        "system_state": state.value,
        "logging_state": logging_state.value,
        "error": error,
        "serial_connected": serial_handler.is_connected,
        "mock_mode": serial_handler.use_mock,
        "heater_temperature": round(heater_temp, 2) if heater_temp else None,
        "heater_initialized": heater_reader.initialized
    })

# MODIFIED startup_sequence():

def startup_sequence():
    """Initialize system on startup"""
    print("[STARTUP] Initializing Temperature Monitoring System v6.5 (WITH HEATER CONTROL)")
    print(f"[STARTUP] Log folder: {LOG_FOLDER}")
    print("[STARTUP] Serial Message Queue: 100 messages max")
    print("[STARTUP] CSV logging: Now includes sensor names!")
    print("[STARTUP] Probe management: Now includes DELETE functionality!")
    print("[STARTUP] Heater integration: Temperature logging + target setting")
    Path(LOG_FOLDER).mkdir(parents=True, exist_ok=True)

    # Initialize heater reader
    heater_reader.initialize()

    reader = SerialReaderThread(serial_handler, data_manager, state_machine, logger, serial_message_queue)
    reader.start()

    print("[STARTUP] Serial reader thread started")
    print("[STARTUP] System ready")

if __name__ == '__main__':
    startup_sequence()
    app.run(host='0.0.0.0', port=5000, debug=False)

# MODIFICATIONS NEEDED IN EXISTING CODE:
# 1. DataLogger.start_session() - Add "Heater Temp (°C)" to header
# 2. DataLogger.log_reading() - Add heater_temp parameter and log it
# 3. SerialReaderThread.run() - Pass heater_temp to logger
# 4. /api/logging/start - Accept and return heater_target

# SEE PATCH_NOTES.md FOR EXACT LOCATIONS OF THESE CHANGES

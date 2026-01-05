#!/usr/bin/env python3
"""
Flask Web Application - Temperature Control & Logging System
UPDATED: Added heater target write endpoint and heater status reading from shared files
"""

from flask import Flask, render_template, request, jsonify
from datetime import datetime
from pathlib import Path
import json
import threading
import time
import serial
import sys
from collections import defaultdict, deque
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================

SERIAL_PORT = '/dev/ttyUSB0'
SERIAL_BAUD = 115200
SERIAL_TIMEOUT = 1

HEATER_TARGET_FILE = "/tmp/heater_target.json"
HEATER_STATUS_FILE = "/tmp/heater_data.json"

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# ============================================================================
# GLOBAL STATE
# ============================================================================

heater_target_temp = None
serial_handler = None
state_machine = None
data_manager = None
reader_thread = None
logging_thread = None

# ============================================================================
# ENUMS
# ============================================================================

class SystemState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"

class LoggingState(Enum):
    IDLE = "idle"
    LOGGING = "logging"
    PAUSED = "paused"

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class StateMachine:
    def __init__(self):
        self.system_state = SystemState.IDLE
        self.logging_state = LoggingState.IDLE
        self.error = None
    
    def get_state(self):
        return self.system_state, self.logging_state, self.error
    
    def set_system_state(self, state):
        self.system_state = state
    
    def set_logging_state(self, state):
        self.logging_state = state
    
    def set_error(self, error):
        self.error = error

# ============================================================================
# DATA MANAGEMENT
# ============================================================================

class DataManager:
    def __init__(self):
        self.sensors = {}
        self.sensor_names = {}
    
    def add_sensor(self, sensor_id, name=None):
        if sensor_id not in self.sensors:
            self.sensors[sensor_id] = deque(maxlen=1000)
            self.sensor_names[sensor_id] = name or sensor_id
    
    def add_reading(self, sensor_id, value, timestamp=None):
        if sensor_id not in self.sensors:
            self.add_sensor(sensor_id)
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        self.sensors[sensor_id].append({'value': value, 'timestamp': timestamp})
    
    def get_sensors(self):
        result = {}
        for sensor_id, readings in self.sensors.items():
            if readings:
                result[sensor_id] = {
                    'name': self.sensor_names[sensor_id],
                    'current_value': readings[-1]['value'],
                    'timestamp': readings[-1]['timestamp']
                }
        return result
    
    def get_sensor_name(self, sensor_id):
        return self.sensor_names.get(sensor_id, sensor_id)
    
    def rename_sensor(self, sensor_id, new_name):
        if sensor_id in self.sensor_names:
            self.sensor_names[sensor_id] = new_name
    
    def delete_sensor(self, sensor_id):
        if sensor_id in self.sensors:
            del self.sensors[sensor_id]
            del self.sensor_names[sensor_id]

# ============================================================================
# SERIAL COMMUNICATION
# ============================================================================

class SerialHandler:
    def __init__(self, port=SERIAL_PORT, baud=SERIAL_BAUD, use_mock=False):
        self.port = port
        self.baud = baud
        self.use_mock = use_mock
        self.ser = None
        self.is_connected = False
        self.connect()
    
    def connect(self):
        if self.use_mock:
            self.is_connected = True
            return True
        
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=SERIAL_TIMEOUT)
            time.sleep(2)  # Wait for Arduino to reset
            self.is_connected = True
            return True
        except Exception as e:
            print(f"Serial connection failed: {e}")
            self.is_connected = False
            return False
    
    def read_line(self):
        if self.use_mock:
            return self.get_mock_data()
        
        try:
            if self.ser and self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8').strip()
                return line
        except Exception as e:
            print(f"Serial read error: {e}")
            self.is_connected = False
        
        return None
    
    def get_mock_data(self):
        import random
        sensors = ['28ABC123ABC123ABC', '28DEF456DEF456DEF', '28GHI789GHI789GHI']
        temp1 = 23 + random.uniform(-0.5, 0.5)
        temp2 = 24 + random.uniform(-0.5, 0.5)
        temp3 = 22 + random.uniform(-0.5, 0.5)
        return f"{sensors[0]}:{temp1:.2f},{sensors[1]}:{temp2:.2f},{sensors[2]}:{temp3:.2f}"
    
    def disconnect(self):
        if self.ser:
            self.ser.close()
            self.is_connected = False

# ============================================================================
# DATA LOGGING
# ============================================================================

class DataLogger:
    def __init__(self, log_folder="/home/pi/temperature_logs", include_heater=False):
        self.log_folder = Path(log_folder)
        self.log_folder.mkdir(parents=True, exist_ok=True)
        self.include_heater = include_heater
        self.current_file = None
        self.file_handle = None
    
    def start_logging(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_file = self.log_folder / f"temperature_log_{timestamp}.csv"
        
        # Prepare header
        sensor_names = list(data_manager.sensor_names.values())
        
        header_cols = ["Timestamp"]
        if self.include_heater:
            header_cols.append("Heater Thermistor (°C)")
        header_cols.extend(sensor_names)
        
        try:
            self.file_handle = open(self.current_file, 'w')
            self.file_handle.write(','.join(header_cols) + '\n')
            self.file_handle.flush()
            return True
        except Exception as e:
            print(f"Error starting log: {e}")
            return False
    
    def log_reading(self, sensors_dict, heater_temp=None):
        if not self.file_handle:
            return False
        
        try:
            timestamp = datetime.now().isoformat()
            row = [timestamp]
            
            if self.include_heater:
                heater_str = f"{heater_temp:.2f}" if heater_temp is not None else ""
                row.append(heater_str)
            
            for sensor_name in data_manager.sensor_names.values():
                # Find sensor by name
                sensor_id = None
                for sid, sname in data_manager.sensor_names.items():
                    if sname == sensor_name:
                        sensor_id = sid
                        break
                
                if sensor_id in sensors_dict:
                    row.append(f"{sensors_dict[sensor_id]['current_value']:.2f}")
                else:
                    row.append("")
            
            self.file_handle.write(','.join(row) + '\n')
            self.file_handle.flush()
            return True
        except Exception as e:
            print(f"Error logging reading: {e}")
            return False
    
    def stop_logging(self):
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None
            return True
        return False

# ============================================================================
# READER THREADS
# ============================================================================

class SerialReaderThread(threading.Thread):
    def __init__(self, handler, data_mgr, state_mgr, logger=None):
        super().__init__(daemon=True)
        self.handler = handler
        self.data_manager = data_mgr
        self.state_machine = state_mgr
        self.logger = logger
        self.running = True
    
    def run(self):
        print("Serial reader thread started")
        while self.running:
            line = self.handler.read_line()
            
            if line:
                try:
                    # Parse sensor data: "28ABC:23.45,28DEF:24.12,..."
                    pairs = line.split(',')
                    sensors = {}
                    
                    for pair in pairs:
                        if ':' in pair:
                            sensor_id, value = pair.split(':')
                            sensor_id = sensor_id.strip()
                            value = float(value.strip())
                            
                            self.data_manager.add_sensor(sensor_id)
                            self.data_manager.add_reading(sensor_id, value)
                            sensors[sensor_id] = {
                                'name': self.data_manager.get_sensor_name(sensor_id),
                                'current_value': value
                            }
                    
                    # Log if logging is active
                    if self.state_machine.logging_state == LoggingState.LOGGING:
                        if self.logger:
                            heater_temp = get_heater_temp_from_file()
                            self.logger.log_reading(sensors, heater_temp)
                
                except Exception as e:
                    print(f"Error parsing data: {e}")
            
            time.sleep(0.1)
    
    def stop(self):
        self.running = False

class LoggingThread(threading.Thread):
    def __init__(self, data_mgr, state_mgr, logger, interval=60):
        super().__init__(daemon=True)
        self.data_manager = data_mgr
        self.state_machine = state_mgr
        self.logger = logger
        self.interval = interval
        self.running = True
    
    def run(self):
        print("Logging thread started")
        last_log = time.time()
        
        while self.running:
            if self.state_machine.logging_state == LoggingState.LOGGING:
                current_time = time.time()
                
                if current_time - last_log >= self.interval:
                    sensors = self.data_manager.get_sensors()
                    if sensors:
                        heater_temp = get_heater_temp_from_file()
                        self.logger.log_reading(sensors, heater_temp)
                    last_log = current_time
            
            time.sleep(1)
    
    def stop(self):
        self.running = False

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_heater_temp_from_file():
    """Read heater temperature from file written by heating_control.py"""
    try:
        heater_file = Path(HEATER_STATUS_FILE)
        if heater_file.exists():
            with open(heater_file, 'r') as f:
                data = json.load(f)
                return data.get('temperature_c')
    except:
        pass
    return None

def get_heater_relay_state_from_file():
    """Read heater relay state from file written by heating_control.py"""
    try:
        heater_file = Path(HEATER_STATUS_FILE)
        if heater_file.exists():
            with open(heater_file, 'r') as f:
                data = json.load(f)
                return data.get('relay_state')
    except:
        pass
    return None

# ============================================================================
# FLASK ROUTES - System
# ============================================================================

@app.route('/api/system/status', methods=['GET'])
def system_status():
    """Get system status including heater info"""
    state, logging_state, error = state_machine.get_state()
    
    # Read heater info from file
    heater_current = None
    heater_relay = None
    try:
        heater_file = Path(HEATER_STATUS_FILE)
        if heater_file.exists():
            with open(heater_file, 'r') as f:
                data = json.load(f)
                heater_current = data.get('temperature_c')
                heater_relay = data.get('relay_state')
    except:
        pass
    
    return jsonify({
        "system_state": state.value,
        "logging_state": logging_state.value,
        "error": error,
        "serial_connected": serial_handler.is_connected,
        "mock_mode": serial_handler.use_mock,
        "heater_target_temp": heater_target_temp,
        "heater_current_temp": heater_current,
        "heater_relay_state": heater_relay
    })

# ============================================================================
# FLASK ROUTES - Sensors
# ============================================================================

@app.route('/api/sensors', methods=['GET'])
def get_sensors():
    """Get all sensor data"""
    sensors = data_manager.get_sensors()
    return jsonify(sensors)

@app.route('/api/sensor/<sensor_id>/rename', methods=['POST'])
def rename_sensor(sensor_id):
    """Rename a sensor"""
    try:
        data = request.get_json()
        new_name = data.get('name')
        
        if not new_name:
            return jsonify({"error": "Name required"}), 400
        
        data_manager.rename_sensor(sensor_id, new_name)
        return jsonify({"status": "ok", "sensor_id": sensor_id, "new_name": new_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sensor/<sensor_id>/delete', methods=['POST'])
def delete_sensor(sensor_id):
    """Delete a sensor"""
    try:
        data_manager.delete_sensor(sensor_id)
        return jsonify({"status": "ok", "sensor_id": sensor_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# FLASK ROUTES - Heater Control
# ============================================================================

@app.route('/api/heater/status', methods=['GET'])
def get_heater_status():
    """Get heater current status - reads from daemon-written file"""
    global heater_target_temp
    
    current_temp = None
    relay_state = None
    
    # Try to read from shared file written by heating_control.py
    try:
        heater_file = Path(HEATER_STATUS_FILE)
        if heater_file.exists():
            with open(heater_file, 'r') as f:
                data = json.load(f)
                current_temp = data.get('temperature_c')
                relay_state = data.get('relay_state')
    except Exception as e:
        print(f"[HEATER] Error reading heater file: {e}")
        current_temp = None
    
    return jsonify({
        "target_temp": heater_target_temp,
        "current_temp": current_temp,
        "relay_state": relay_state
    })

@app.route('/api/heater/set', methods=['POST'])
def set_heater_temperature():
    """Set heater target temperature (stores in memory and file)"""
    global heater_target_temp
    
    try:
        data = request.get_json()
        target_temp = data.get('target_temp')
        
        if target_temp is None:
            return jsonify({"error": "Missing target_temp"}), 400
        
        target_temp = float(target_temp)
        
        # Validate range
        if target_temp < 0 or target_temp > 80:
            return jsonify({"error": "Temperature must be between 0-80°C"}), 400
        
        # Store in memory
        heater_target_temp = target_temp
        
        # Write to file for heating_control.py to read
        target_file = Path(HEATER_TARGET_FILE)
        with open(target_file, 'w') as f:
            json.dump({"target_temp": target_temp}, f)
        
        return jsonify({
            "status": "ok",
            "heater_target_temp": target_temp,
            "message": "Target temperature set"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# FLASK ROUTES - Logging Control
# ============================================================================

@app.route('/api/logging/start', methods=['POST'])
def start_logging():
    """Start temperature logging"""
    try:
        data = request.get_json()
        log_folder = data.get('folder', '/home/pi/temperature_logs')
        interval = int(data.get('interval', 60))
        include_heater = data.get('include_heater', False)
        
        if interval < 1:
            return jsonify({"error": "Interval must be at least 1 second"}), 400
        
        global logging_thread
        
        # Create logger
        logger = DataLogger(log_folder, include_heater)
        if not logger.start_logging():
            return jsonify({"error": "Failed to start logging"}), 500
        
        # Start logging thread
        state_machine.set_logging_state(LoggingState.LOGGING)
        logging_thread = LoggingThread(data_manager, state_machine, logger, interval)
        logging_thread.start()
        
        return jsonify({
            "status": "ok",
            "message": "Logging started",
            "folder": log_folder,
            "interval": interval,
            "include_heater": include_heater
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logging/stop', methods=['POST'])
def stop_logging():
    """Stop temperature logging"""
    try:
        state_machine.set_logging_state(LoggingState.IDLE)
        return jsonify({"status": "ok", "message": "Logging stopped"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# FLASK ROUTES - Web Pages
# ============================================================================

@app.route('/')
def index():
    """Serve main dashboard"""
    return render_template('index.html')

# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize_app():
    """Initialize the Flask application"""
    global serial_handler, state_machine, data_manager, reader_thread
    
    print("Initializing application...")
    
    # Initialize managers
    state_machine = StateMachine()
    data_manager = DataManager()
    
    # Initialize serial handler (use mock mode if no port)
    use_mock = len(sys.argv) > 1 and sys.argv[1] == 'mock'
    serial_handler = SerialHandler(use_mock=use_mock)
    
    if serial_handler.is_connected:
        print(f"✓ Serial connected on {SERIAL_PORT}")
    else:
        print("⚠ Serial connection failed - using mock mode")
        serial_handler.use_mock = True
    
    # Start serial reader thread
    reader_thread = SerialReaderThread(serial_handler, data_manager, state_machine)
    reader_thread.start()
    
    print("✓ Application initialized")

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    initialize_app()
    print("\n" + "="*60)
    print("Flask Web Server Starting")
    print("="*60)
    print("Access dashboard at: http://localhost:5000/")
    print("API endpoints: /api/system/status, /api/sensors, /api/heater/status")
    print("="*60 + "\n")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n✓ Shutting down...")
        if reader_thread:
            reader_thread.stop()
        if serial_handler:
            serial_handler.disconnect()

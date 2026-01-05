# Temperature Monitoring System - Flask Backend (v6.7 - COLON DELIMITER FIX)
# The heating_control.py program should write heater temp to: /tmp/heater_thermistor.json

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

# ============================================================================
# HEATER THERMISTOR READER
# ============================================================================

class HeaterThermistorReader:
    """
    Reads heater thermistor temperature from a JSON file written by heating_control.py
    File format: {"temperature_c": 25.5, "timestamp": 1234567890.123}
    """
    def __init__(self, temp_file="/tmp/heater_thermistor.json"):
        self.temp_file = Path(temp_file)
        self.last_temp = None
        self.last_timestamp = None
        self.lock = threading.Lock()

    def get_temperature(self):
        """
        Read latest heater thermistor temperature
        Returns: dict with 'temperature' and 'status', or None if unavailable
        """
        with self.lock:
            try:
                if self.temp_file.exists():
                    with open(self.temp_file, 'r') as f:
                        data = json.load(f)
                        temp = data.get('temperature_c')
                        if temp is not None:
                            self.last_temp = temp
                            self.last_timestamp = time.time()
                            return {'temperature': temp, 'status': 'online'}

                # If file doesn't exist or no valid data, return last known or None
                if self.last_temp is not None:
                    return {'temperature': self.last_temp, 'status': 'cached'}
                return None
            except Exception as e:
                print(f"[HEATER] Error reading thermistor: {e}")
                return None

# ============================================================================
# STATE MACHINE
# ============================================================================

class SystemState(Enum):
    """System states for the state machine"""
    IDLE = "idle"
    WAITING_FOR_SERIAL = "waiting_for_serial"
    READING = "reading"
    LOGGING = "logging"
    ERROR = "error"

class LoggingState(Enum):
    """Logging sub-states"""
    IDLE = "idle"
    LOGGING = "logging"
    STOPPING = "stopping"

# ============================================================================
# SERIAL MESSAGE QUEUE
# ============================================================================

class SerialMessageQueue:
    """
    Store and manage incoming serial messages for Serial Monitor display.
    Automatically caps at max_messages to prevent memory bloat.
    """
    def __init__(self, max_messages=100):
        self.messages = []
        self.max_messages = max_messages
        self.lock = threading.Lock()

    def add(self, message, msg_type="info", timestamp=None):
        """
        Add message with type classification
        msg_type options:
        - "temperature": Temperature readings
        - "info": Info messages (RESCAN_COMPLETE, etc)
        - "warning": Warning messages (OFFLINE, etc)
        - "error": Error messages (CRC_FAILED, etc)
        - "unknown": Could not classify
        """
        with self.lock:
            self.messages.append({
                "timestamp": timestamp or time.time(),
                "message": message,
                "type": msg_type
            })

            # Keep only last N messages to prevent memory bloat
            if len(self.messages) > self.max_messages:
                self.messages.pop(0)

    def get_all(self):
        """Get all messages"""
        with self.lock:
            return list(self.messages)

    def get_filtered(self, msg_type=None):
        """Get messages filtered by type"""
        with self.lock:
            if msg_type:
                return [m for m in self.messages if m["type"] == msg_type]
            return list(self.messages)

    def clear(self):
        """Clear all messages"""
        with self.lock:
            self.messages.clear()

# ============================================================================
# STATE MACHINE MANAGER
# ============================================================================

class TemperatureSystemStateMachine:
    """
    Robust state machine for temperature monitoring system.
    Handles transitions and enforces valid state changes.
    """
    def __init__(self):
        self.current_state = SystemState.WAITING_FOR_SERIAL
        self.logging_state = LoggingState.IDLE
        self.error_message = None
        self.state_lock = threading.Lock()

    def set_state(self, new_state, error_msg=None):
        """Safely transition to a new state"""
        with self.state_lock:
            old_state = self.current_state
            self.current_state = new_state
            self.error_message = error_msg
            print(f"[STATE] {old_state.value} → {new_state.value}")
            if error_msg:
                print(f"[ERROR] {error_msg}")

    def set_logging_state(self, new_state):
        """Transition logging sub-state"""
        with self.state_lock:
            self.logging_state = new_state

    def get_state(self):
        """Get current state safely"""
        with self.state_lock:
            return self.current_state, self.logging_state, self.error_message

    def can_start_logging(self):
        """Check if system is in state to start logging"""
        with self.state_lock:
            return self.current_state == SystemState.READING

    def can_receive_data(self):
        """Check if system can receive sensor data"""
        with self.state_lock:
            return self.current_state in [SystemState.READING, SystemState.LOGGING]

# ============================================================================
# SERIAL HANDLER
# ============================================================================

class SerialHandler:
    """
    Handles serial communication with Arduino.
    Supports both real and mock sensor modes for testing.
    """
    def __init__(self, port="/dev/ttyACM0", baudrate=9600, use_mock=False):
        self.port = port
        self.baudrate = baudrate
        self.use_mock = use_mock
        self.ser = None
        self.is_connected = False
        self.mock_counter = 0
        self.lock = threading.Lock()

    def connect(self):
        """Attempt to connect to Arduino"""
        try:
            if self.use_mock:
                self.is_connected = True
                print("[SERIAL] Mock mode enabled")
                return True
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.is_connected = True
            print(f"[SERIAL] Connected to {self.port} at {self.baudrate} baud")
            time.sleep(2)
            return True
        except Exception as e:
            print(f"[SERIAL] Connection failed: {e}")
            self.is_connected = False
            return False

    def readline(self):
        """Read a line from serial or mock data"""
        try:
            if self.use_mock:
                return self.generate_mock_data()
            if self.ser and self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8').strip()
                return line if line else None
            return None
        except Exception as e:
            print(f"[SERIAL] Read error: {e}")
            return None

    def generate_mock_data(self):
        """Generate mock sensor data for testing"""
        self.mock_counter += 1
        import random
        num_sensors = random.randint(2, 5)
        sensors = []
        for i in range(num_sensors):
            sensor_id = f"28{i:016x}"
            temp = 20 + random.uniform(-5, 15) + self.mock_counter * 0.01
            sensors.append(f"{sensor_id}:{temp:.2f}")
        data = ",".join(sensors)
        time.sleep(0.5)
        return data

    def disconnect(self):
        """Close serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.is_connected = False
            print("[SERIAL] Disconnected")

# ============================================================================
# SENSOR DATA MANAGER
# ============================================================================

class SensorDataManager:
    """
    Manages sensor data storage, validation, and retrieval.
    Stores current readings and historical data.
    """
    def __init__(self):
        self.sensors = {}
        self.history = {}
        self.lock = threading.Lock()
        self.mock_sensor_counter = 0

    def update_sensor(self, sensor_id, temperature, status="online"):
        """Update sensor reading"""
        with self.lock:
            if sensor_id not in self.sensors:
                # New sensor detected
                if sensor_id.startswith("280000"):
                    self.mock_sensor_counter += 1
                    name = f"Mock Probe {self.mock_sensor_counter}"
                else:
                    name = f"Probe {sensor_id[:8]}"
                self.sensors[sensor_id] = {
                    "temperature": temperature,
                    "status": status,
                    "last_update": time.time(),
                    "name": name
                }
            else:
                self.sensors[sensor_id]["temperature"] = temperature
                self.sensors[sensor_id]["status"] = status
                self.sensors[sensor_id]["last_update"] = time.time()

    def set_offline(self, sensor_id):
        """Mark sensor as offline"""
        with self.lock:
            if sensor_id in self.sensors:
                self.sensors[sensor_id]["status"] = "offline"

    def add_to_history(self, sensor_id, temperature, timestamp=None):
        """Add reading to history"""
        with self.lock:
            if sensor_id not in self.history:
                self.history[sensor_id] = []
            self.history[sensor_id].append({
                "temperature": temperature,
                "timestamp": timestamp or time.time()
            })

    def get_sensors(self):
        """Get all sensor data"""
        with self.lock:
            return dict(self.sensors)

    def get_history(self):
        """Get historical data"""
        with self.lock:
            return dict(self.history)

    def rename_sensor(self, sensor_id, name):
        """Rename a sensor"""
        with self.lock:
            if sensor_id in self.sensors:
                self.sensors[sensor_id]["name"] = name
                print(f"[SENSOR] Renamed {sensor_id} to {name}")
                return True
            return False

    def delete_sensor(self, sensor_id):
        """Delete a sensor from tracking"""
        with self.lock:
            if sensor_id in self.sensors:
                name = self.sensors[sensor_id]["name"]
                del self.sensors[sensor_id]
                if sensor_id in self.history:
                    del self.history[sensor_id]
                print(f"[SENSOR] Deleted {sensor_id} ({name})")
                return True
            return False

    def detect_disconnected(self, current_ids, timeout=30):
        """Detect sensors that haven't reported recently"""
        with self.lock:
            current_time = time.time()
            for sensor_id in self.sensors:
                if sensor_id not in current_ids:
                    last_update = self.sensors[sensor_id]["last_update"]
                    if current_time - last_update > timeout:
                        self.sensors[sensor_id]["status"] = "offline"

# ============================================================================
# DATA LOGGER
# ============================================================================

class DataLogger:
    """
    Handles CSV file creation and data logging with proper timestamps.
    NOW INCLUDES SENSOR NAMES IN COLUMN HEADERS (not just IDs)!
    """
    def __init__(self, folder="/home/vbio/TemperatureMonitor/temperatureMonitor/RPi/logs"):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.current_file = None
        self.current_handle = None
        self.lock = threading.Lock()
        self.sensor_mapping = {}

    def start_session(self, sensors):
        """Create new logging session file with sensor NAMES in headers"""
        with self.lock:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"temperature_log_{timestamp}.csv"
            filepath = self.folder / filename
            try:
                self.current_handle = open(filepath, "w")
                self.current_file = filepath

                # Store sensor mapping for later use
                self.sensor_mapping = {sid: (s["name"], sid) for sid, s in sensors.items()}

                header_parts = ["Timestamp"]
                for sensor_id in sorted(sensors.keys()):
                    sensor = sensors[sensor_id]
                    # Use friendly name directly (no ID suffix)
                    sensor_name = sensor.get("name") or f"Probe-{sensor_id[:8]}"
                    header_parts.append(sensor_name)

                # PLUS heater thermistor at the end
                header_parts.append("Heater Thermistor (C)")
                header = ",".join(header_parts)
                self.current_handle.write(header + "\n")
                self.current_handle.flush()

                print(f"[LOGGER] Started new session: {filename}")
                print(f"[LOGGER] Logging to {filepath}")
                print(f"[LOGGER] Column headers: {header}")
                return filename
            except Exception as e:
                print(f"[LOGGER] Error starting session: {e}")
                return None

    def log_reading(self, sensors_dict, heater_temp=None):
        """Log current sensor readings plus heater temperature"""
        with self.lock:
            if not self.current_handle:
                return False
            try:
                timestamp = datetime.now().isoformat()
                row = timestamp

                # Add sensor values in same order as header
                for sensor_id in sorted(sensors_dict.keys()):
                    sensor = sensors_dict[sensor_id]
                    if sensor["status"] == "online":
                        value = f"{sensor['temperature']:.2f}"
                    else:
                        value = "N/C"
                    row += f",{value}"

                # Log heater thermistor column
                if heater_temp is not None:
                    heater_value = f"{heater_temp:.2f}"
                else:
                    heater_value = "N/C"
                row += f",{heater_value}"

                self.current_handle.write(row + "\n")
                self.current_handle.flush()
                return True
            except Exception as e:
                print(f"[LOGGER] Error logging reading: {e}")
                return False

    def end_session(self):
        """Close current logging session and return filename"""
        with self.lock:
            if self.current_handle:
                try:
                    self.current_handle.close()
                    filename = self.current_file.name
                    self.current_handle = None
                    self.current_file = None
                    self.sensor_mapping = {}
                    print(f"[LOGGER] Session ended: {filename}")
                    return filename
                except Exception as e:
                    print(f"[LOGGER] Error closing session: {e}")
                    return None
            return None

    def load_session_data(self, filename):
        """Load data from a specific session file"""
        try:
            filepath = self.folder / filename
            if not filepath.exists():
                print(f"[LOGGER] File not found: {filepath}")
                return None
            data = []
            with open(filepath, 'r') as f:
                lines = f.readlines()
                if not lines:
                    return None
                headers = lines[0].strip().split(',')[1:]
                for line in lines[1:]:
                    values = line.strip().split(',')
                    if len(values) > 1:
                        timestamp = values[0]
                        readings = {}
                        # Log heater thermistor temperature
                        for i, header in enumerate(headers):
                            try:
                                val = values[i + 1]
                                readings[header] = float(val) if val != "N/C" else None
                            except (ValueError, IndexError):
                                readings[header] = None
                        data.append({"timestamp": timestamp, "readings": readings})
            print(f"[LOGGER] Loaded {len(data)} rows from {filename}")
            return data
        except Exception as e:
            print(f"[LOGGER] Error loading session {filename}: {e}")
            return None

    def get_log_folder(self):
        """Get the logging folder path"""
        return str(self.folder)

# ============================================================================
# SERIAL READER THREAD
# ============================================================================

class SerialReaderThread(threading.Thread):
    """
    Continuously reads from Arduino and updates sensor data.
    Now with improved message handling and Serial Monitor support.
    """
    def __init__(self, serial_handler, data_manager, state_machine, logger, message_queue, heater_reader):
        super().__init__(daemon=True)
        self.serial_handler = serial_handler
        self.data_manager = data_manager
        self.state_machine = state_machine
        self.logger = logger
        self.message_queue = message_queue
        self.heater_reader = heater_reader
        self.running = True
        self.disconnect_timeout = 30

    def run(self):
        """Main thread loop"""
        last_rescan = 0
        while self.running:
            # Connection management
            if not self.serial_handler.is_connected:
                if not self.serial_handler.connect():
                    self.state_machine.set_state(SystemState.WAITING_FOR_SERIAL, "No Arduino connection")
                    time.sleep(5)
                    continue
                else:
                    self.state_machine.set_state(SystemState.READING)

            # Read data from Arduino
            line = self.serial_handler.readline()
            if not line:
                time.sleep(0.1)
                continue

            # Log raw data to Serial Monitor
            self.message_queue.add(line, "raw")
            print(f"[SERIAL] Raw line received: {line}")

            try:
                current_ids = set()
                readings = line.split(",")
                for reading in readings:
                    reading = reading.strip()

                    # Skip empty readings
                    if not reading:
                        continue

                    # VALIDATION: Check if this looks like a temperature reading (colon, space, or comma separated)
                    if any(sep in reading for sep in [":", " ", ","]) and not any(x in reading.upper() for x in ["ERROR", "WARN", "FAIL", "INFO"]):
                        # Try colon first, then comma, then space
                        if ":" in reading:
                            parts = reading.split(":")
                        elif "," in reading:
                            parts = reading.split(",")
                        else:
                            parts = reading.split()
                        
                        if len(parts) >= 2:
                            sensor_id = parts[0].strip()
                            temp_str = parts[1].strip()

                            # TEMPERATURE DATA VALIDATION - accept any hex string 8+ chars with valid float temp
                            is_valid_sensor = False
                            try:
                                # Try to parse as float first to validate temperature
                                temp = float(temp_str)
                                # Check if sensor_id looks valid (hex chars, at least 8 chars)
                                if len(sensor_id) >= 8 and all(c in "0123456789ABCDEFabcdef" for c in sensor_id):
                                    is_valid_sensor = True
                            except ValueError:
                                pass  # Not a valid temperature value

                            if not is_valid_sensor:
                                msg = f"[PARSE] Raw reading rejected: '{reading}' - sensor_id='{sensor_id}' (need 8+ hex chars), temp='{temp_str}' (need valid number)"
                                self.message_queue.add(msg, "warning")
                                print(msg)
                                continue

                            current_ids.add(sensor_id)
                            try:
                                temp = float(temp_str)
                                self.data_manager.update_sensor(sensor_id, temp, "online")
                                self.message_queue.add(reading, "temperature")
                                print(f"[PARSE] ✓ Sensor {sensor_id[:8]}... temp={temp:.2f}°C")

                                # Log if currently logging
                                if self.state_machine.logging_state == LoggingState.LOGGING:
                                    heater_temp = None
                                    heater_data = self.heater_reader.get_temperature()
                                    if heater_data:
                                        heater_temp = heater_data["temperature"]
                                    self.logger.log_reading(self.data_manager.get_sensors(), heater_temp)
                            except ValueError:
                                msg = f"Invalid temperature value: {temp_str}"
                                self.message_queue.add(msg, "warning")
                                print(f"[PARSE] {msg}")

                    # ERROR MESSAGES
                    elif "ERROR" in reading.upper() or "FAIL" in reading.upper():
                        self.message_queue.add(reading, "error")
                        print(f"[ARDUINO-ERROR] {reading}")

                    # WARNING MESSAGES
                    elif "WARN" in reading.upper() or "OFFLINE" in reading.upper():
                        self.message_queue.add(reading, "warning")
                        print(f"[ARDUINO-WARN] {reading}")
                    elif "Invalid" in reading:
                        self.message_queue.add(reading, "warning")
                        print(f"[ARDUINO-WARN] {reading}")

                    # INFO MESSAGES
                    elif "INFO" in reading.upper() or any(x in reading.upper() for x in ["RESCAN", "FOUND", "COMPLETE"]):
                        self.message_queue.add(reading, "info")
                        print(f"[ARDUINO-INFO] {reading}")

                    # UNKNOWN FORMAT
                    else:
                        self.message_queue.add(reading, "unknown")
                        print(f"[ARDUINO-UNKNOWN] {reading}")

                # Update state if needed
                if self.state_machine.current_state == SystemState.WAITING_FOR_SERIAL:
                    self.state_machine.set_state(SystemState.READING)

                self.data_manager.detect_disconnected(current_ids, self.disconnect_timeout)
            except Exception as e:
                msg = f"Parse error: {e}"
                self.message_queue.add(msg, "error")
                print(f"[READER] {msg}")
            time.sleep(0.1)

    def stop(self):
        """Stop the reader thread"""
        self.running = False

# ============================================================================
# LOGGING THREAD
# ============================================================================

class LoggingThread(threading.Thread):
    """
    Manages timed logging sessions.
    Handles duration limits and periodic saves.
    """
    def __init__(self, data_manager, logger, state_machine, heater_reader, duration=None, interval=60):
        super().__init__(daemon=True)
        self.data_manager = data_manager
        self.logger = logger
        self.state_machine = state_machine
        self.heater_reader = heater_reader
        self.duration = duration
        self.interval = interval
        self.running = False
        self.start_time = None

    def run(self):
        """Main logging loop"""
        self.running = True
        self.start_time = time.time()
        last_log = self.start_time
        while self.running:
            current_time = time.time()
            elapsed = current_time - self.start_time
            if self.duration and elapsed > self.duration:
                print("[LOGGER] Duration limit reached")
                self.running = False
                break
            if current_time - last_log > self.interval:
                sensors = self.data_manager.get_sensors()
                if sensors:
                    heater_temp = None
                    heater_data = self.heater_reader.get_temperature()
                    if heater_data:
                        heater_temp = heater_data["temperature"]
                    self.logger.log_reading(sensors, heater_temp)
                last_log = current_time
            time.sleep(0.5)

    def stop(self):
        """Stop logging thread"""
        self.running = False

# ============================================================================
# FLASK APP SETUP
# ============================================================================

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Global managers
state_machine = TemperatureSystemStateMachine()
serial_handler = SerialHandler(use_mock=False)
data_manager = SensorDataManager()
logger = DataLogger()
serial_message_queue = SerialMessageQueue(max_messages=100)
heater_reader = HeaterThermistorReader()

logging_thread = None

# Config
SERIAL_PORT = "/dev/ttyACM0"
SERIAL_BAUDRATE = 9600
LOG_FOLDER = "/home/vbio/TemperatureMonitor/temperatureMonitor/RPi/logs"

# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route("/")
def index():
    """Serve main dashboard"""
    return render_template("index.html")

@app.route("/api/sensors", methods=["GET"])
def get_sensors():
    """Get all current sensor readings"""
    sensors = data_manager.get_sensors()
    return jsonify(sensors=sensors)

@app.route("/api/probes/rescan", methods=["POST"])
def rescan_probes():
    """Trigger Arduino to rescan for probes"""
    try:
        if serial_handler.ser and serial_handler.ser.is_open:
            serial_handler.ser.write(b"RESCAN\n")
        sensors = data_manager.get_sensors()
        return jsonify(status="ok", sensors=sensors)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route("/api/probes/rename", methods=["POST"])
def rename_probe():
    """Rename a probe"""
    try:
        data = request.get_json()
        sensor_id = data.get("sensorid")
        name = data.get("name")
        if not sensor_id or not name:
            return jsonify(error="Missing parameters"), 400
        success = data_manager.rename_sensor(sensor_id, name)
        if success:
            sensors = data_manager.get_sensors()
            return jsonify(status="ok", sensors=sensors)
        else:
            return jsonify(error="Sensor not found"), 404
    except Exception as e:
        print(f"[API] Rename error: {e}")
        return jsonify(error=str(e)), 500

@app.route("/api/probes/delete", methods=["POST"])
def delete_probe():
    """Delete a probe"""
    try:
        data = request.get_json()
        sensor_id = data.get("sensorid")
        if not sensor_id:
            return jsonify(error="Missing sensorid"), 400
        success = data_manager.delete_sensor(sensor_id)
        if success:
            sensors = data_manager.get_sensors()
            return jsonify(status="ok", sensors=sensors)
        else:
            return jsonify(error="Sensor not found"), 404
    except Exception as e:
        print(f"[API] Delete error: {e}")
        return jsonify(error=str(e)), 500

@app.route("/api/logging/start", methods=["POST"])
def start_logging():
    """Start data logging session"""
    global logging_thread, logger

    if not state_machine.can_start_logging():
        return jsonify(error="System not ready for logging"), 400

    try:
        data = request.get_json()
        folder = data.get("folder", str(LOG_FOLDER)).strip()
        duration = data.get("duration")
        interval = data.get("interval", 60)

        # Validate and create folder
        if not folder:
            folder = LOG_FOLDER
        logger = DataLogger(folder)
        sensors = data_manager.get_sensors()
        filename = logger.start_session(sensors)
        if not filename:
            return jsonify(error="Failed to create log file"), 500

        logging_thread = LoggingThread(data_manager, logger, state_machine, heater_reader, duration, interval)
        logging_thread.start()
        state_machine.set_logging_state(LoggingState.LOGGING)
        state_machine.set_state(SystemState.LOGGING)

        return jsonify(
            status="ok",
            filename=filename,
            folder=folder,
            startTime=int(time.time() * 1000),
            duration=duration,
            interval=interval
        )
    except Exception as e:
        print(f"[API] Logging start error: {e}")
        return jsonify(error=str(e)), 500

@app.route("/api/logging/stop", methods=["POST"])
def stop_logging():
    """Stop current logging session"""
    global logging_thread, logger
    try:
        if logging_thread and logging_thread.running:
            logging_thread.stop()
            logging_thread.join(timeout=5)
        filename = logger.end_session()
        state_machine.set_logging_state(LoggingState.IDLE)
        state_machine.set_state(SystemState.READING)
        if filename:
            return jsonify(status="ok", filename=filename)
        else:
            return jsonify(status="error", error="Failed to close log file"), 500
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route("/api/graphs/data", methods=["GET"])
def get_graph_data():
    """Get historical graph data"""
    try:
        log_folder = Path(LOG_FOLDER)
        log_folder.mkdir(parents=True, exist_ok=True)

        requested_file = request.args.get("file")
        csv_files = sorted(log_folder.glob("temperature_log_*.csv"))

        # Validate and create folder
        def load_and_parse(requested_path=None):
            if requested_file:
                requested_path = log_folder / requested_file
                if requested_path.exists():
                    csv_files_to_parse = [requested_path]
                else:
                    csv_files_to_parse = csv_files
            else:
                csv_files_to_parse = csv_files

            sessions = {}
            for csv_file in csv_files_to_parse:
                data = []
                try:
                    with open(csv_file, 'r') as f:
                        lines = f.readlines()
                        if not lines:
                            continue
                        headers = lines[0].strip().split(',')[1:]
                        for line in lines[1:]:
                            values = line.strip().split(',')
                            if len(values) > 1:
                                timestamp = values[0]
                                readings = {}
                                for i, header in enumerate(headers):
                                    try:
                                        val = values[i + 1]
                                        readings[header] = float(val) if val != "N/C" else None
                                    except (ValueError, IndexError):
                                        readings[header] = None
                                data.append({"timestamp": timestamp, "readings": readings})
                    if data:
                        sessions[csv_file.name] = data
                except Exception as e:
                    print(f"[GRAPHS] Error loading {csv_file.name}: {e}")

            return sessions

        if not csv_files:
            return jsonify(sessions={}, files=[])

        sessions = load_and_parse()
        files_list = [f.name for f in csv_files]

        if not requested_file:
            requested_file = None

        return jsonify(sessions=sessions, files=files_list)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route("/api/graphs/download", methods=["GET"])
def download_graph_csv():
    """Download historical data as CSV"""
    try:
        log_folder = Path(LOG_FOLDER)
        log_folder.mkdir(parents=True, exist_ok=True)
        csv_files = sorted(log_folder.glob("temperature_log_*.csv"))

        if not csv_files:
            return jsonify(error="No data available"), 404

        combined_file = log_folder / "combined_export.csv"
        with open(combined_file, "w") as outfile:
            for csv_file in csv_files:
                with open(csv_file, "r") as infile:
                    outfile.write(infile.read())

        return send_file(combined_file, as_attachment=True, download_name="temperature_data.csv")
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route("/api/mock/enable", methods=["POST"])
def enable_mock_mode():
    """Enable mock mode"""
    global serial_handler
    try:
        serial_handler.use_mock = True
        msg = "Mock mode ENABLED - generating test data"
        serial_message_queue.add(msg, "info")
        print(f"[MOCK] {msg}")
        return jsonify(status="ok", message=msg)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route("/api/mock/disable", methods=["POST"])
def disable_mock_mode():
    """Disable mock mode"""
    global serial_handler, data_manager
    try:
        serial_handler.use_mock = False
        data_manager.sensors.clear()
        msg = "Mock mode DISABLED - waiting for Arduino"
        serial_message_queue.add(msg, "info")
        print(f"[MOCK] {msg}")
        return jsonify(status="ok", message=msg)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route("/api/serial/messages", methods=["GET"])
def get_serial_messages():
    """Get serial monitor messages with optional type filter"""
    msg_type = request.args.get("type")
    messages = serial_message_queue.get_filtered(msg_type)
    return jsonify(messages=messages)

@app.route("/api/serial/messages", methods=["DELETE"])
def clear_serial_messages():
    """Clear all serial messages"""
    serial_message_queue.clear()
    return jsonify(status="ok")

@app.route("/api/system/status", methods=["GET"])
def system_status():
    """Get system status - INCLUDES mock_mode field"""
    state, logging_state, error = state_machine.get_state()
    return jsonify(
        system_state=state.value,
        logging_state=logging_state.value,
        error=error,
        serial_connected=serial_handler.is_connected,
        mock_mode=serial_handler.use_mock
    )

# ============================================================================
# STARTUP
# ============================================================================

def startup_sequence():
    """Initialize system on startup"""
    print("[STARTUP] Initializing Temperature Monitoring System v6.7 WITH HEATER THERMISTOR + COLON DELIMITER")
    print(f"[STARTUP] Log folder: {LOG_FOLDER}")
    print("[STARTUP] Serial Message Queue: 100 messages max")
    print("[STARTUP] CSV logging: Now includes sensor NAMES (not just IDs) AND heater thermistor!")
    print("[STARTUP] Heater thermistor source: /tmp/heater_thermistor.json")
    print("[STARTUP] Probe management: Includes DELETE functionality!")
    print("[STARTUP] Parser: Accepts hex sensor IDs (8+ chars) with colon, space, or comma separator")
    Path(LOG_FOLDER).mkdir(parents=True, exist_ok=True)

    reader = SerialReaderThread(serial_handler, data_manager, state_machine, logger, serial_message_queue, heater_reader)
    reader.start()
    print("[STARTUP] Serial reader thread started")
    print("[STARTUP] System ready!")

if __name__ == "__main__":
    startup_sequence()
    app.run(host="0.0.0.0", port=5000, debug=False)

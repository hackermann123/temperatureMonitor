# Temperature Monitoring System - Flask Backend (v6.1 - FIXED)
# Complete implementation with SerialMessageQueue and improved data handling
# FIXES: 
# 1. Added mock_mode to system_status response
# 2. Better mock sensor naming with counters
# 3. Improved sensor data management

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
# SERIAL COMMUNICATION HANDLER
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

    def read_line(self):
        """Read a line from serial (or mock data)"""
        try:
            if self.use_mock:
                return self._generate_mock_data()
            if self.ser and self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8').strip()
                return line if line else None
            return None
        except Exception as e:
            print(f"[SERIAL] Read error: {e}")
            return None

    def _generate_mock_data(self):
        """Generate mock sensor data for testing"""
        self.mock_counter += 1
        import random
        num_sensors = random.randint(2, 5)
        sensors = []
        for i in range(num_sensors):
            sensor_id = f"28{i:016x}"
            temp = 20 + random.uniform(-5, 15) + (self.mock_counter % 100) * 0.01
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
        self.mock_sensor_counter = {}  # Track mock sensor names

    def update_sensor(self, sensor_id, temperature, status="online"):
        """Update sensor reading"""
        with self.lock:
            if sensor_id not in self.sensors:
                # Generate better name for mock sensors
                if sensor_id.startswith('28000'):
                    # This is a mock sensor
                    mock_index = len([s for s in self.sensors if s.startswith('28000')])
                    name = f"Mock Probe {mock_index + 1}"
                else:
                    name = f"Probe {sensor_id[:8]}"
                
                self.sensors[sensor_id] = {
                    "temperature": temperature,
                    "status": status,
                    "lastUpdate": time.time(),
                    "name": name
                }
            else:
                self.sensors[sensor_id]["temperature"] = temperature
                self.sensors[sensor_id]["status"] = status
                self.sensors[sensor_id]["lastUpdate"] = time.time()

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

    def detect_disconnected(self, current_ids, timeout=30):
        """Detect sensors that haven't reported recently"""
        with self.lock:
            current_time = time.time()
            for sensor_id in self.sensors:
                if sensor_id not in current_ids:
                    last_update = self.sensors[sensor_id]["lastUpdate"]
                    if current_time - last_update > timeout:
                        self.sensors[sensor_id]["status"] = "offline"

# ============================================================================
# DATA LOGGER
# ============================================================================

class DataLogger:
    """
    Handles CSV file creation and data logging with proper timestamps.
    """
    def __init__(self, folder="/home/pi/temperature_logs/"):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.current_file = None
        self.current_handle = None
        self.lock = threading.Lock()

    def start_session(self, sensors):
        """Create new logging session file"""
        with self.lock:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"temperature_log_{timestamp}.csv"
            filepath = self.folder / filename
            try:
                self.current_handle = open(filepath, 'w')
                self.current_file = filepath
                header = "Timestamp," + ",".join([f"{name}" for name in sorted(sensors.keys())])
                self.current_handle.write(header + "\n")
                self.current_handle.flush()
                print(f"[LOGGER] Started new session: {filename}")
                return filename
            except Exception as e:
                print(f"[LOGGER] Error starting session: {e}")
                return None

    def log_reading(self, sensors_dict):
        """Log current sensor readings"""
        with self.lock:
            if not self.current_handle:
                return False
            try:
                timestamp = datetime.now().isoformat()
                row = timestamp
                for sensor_id in sorted(sensors_dict.keys()):
                    sensor = sensors_dict[sensor_id]
                    if sensor["status"] == "online":
                        value = f"{sensor['temperature']:.2f}"
                    else:
                        value = "NC"
                    row += f",{value}"
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
                        for i, header in enumerate(headers):
                            try:
                                val = values[i + 1]
                                readings[header] = float(val) if val != "NC" else None
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
    def __init__(self, serial_handler, data_manager, state_machine, logger, message_queue):
        super().__init__(daemon=True)
        self.serial_handler = serial_handler
        self.data_manager = data_manager
        self.state_machine = state_machine
        self.logger = logger
        self.message_queue = message_queue
        self.running = True
        self.disconnect_timeout = 30

    def run(self):
        """Main thread loop"""
        last_rescan = 0
        while self.running:
            # Connection management
            if not self.serial_handler.is_connected:
                if not self.serial_handler.connect():
                    self.state_machine.set_state(SystemState.WAITING_FOR_SERIAL,
                                                 "No Arduino connection")
                    time.sleep(5)
                    continue
                else:
                    self.state_machine.set_state(SystemState.READING)

            # Read data from Arduino
            line = self.serial_handler.read_line()
            if not line:
                time.sleep(0.1)
                continue

            # Log raw data to Serial Monitor
            self.message_queue.add(line, "raw")

            try:
                current_ids = set()
                readings = line.split(',')
                for reading in readings:
                    reading = reading.strip()
                    # Skip empty readings
                    if not reading:
                        continue

                    # ===== TEMPERATURE DATA =====
                    if ':' in reading and not any(x in reading.upper() for x in ['ERROR', 'WARN', 'FAIL', 'INFO']):
                        parts = reading.split(':')
                        if len(parts) == 2:
                            sensor_id, temp_str = parts
                            current_ids.add(sensor_id)
                            try:
                                temp = float(temp_str)
                                self.data_manager.update_sensor(sensor_id, temp, "online")
                                self.message_queue.add(reading, "temperature")
                                # Log if currently logging
                                if self.state_machine.logging_state == LoggingState.LOGGING:
                                    self.logger.log_reading(self.data_manager.get_sensors())
                            except ValueError:
                                msg = f"Invalid temperature value: {temp_str}"
                                self.message_queue.add(msg, "warning")
                                print(f"[PARSE] {msg}")

                    # ===== ERROR MESSAGES =====
                    elif 'ERROR' in reading.upper() or 'FAIL' in reading.upper():
                        self.message_queue.add(reading, "error")
                        print(f"[ARDUINO_ERROR] {reading}")

                    # ===== WARNING MESSAGES =====
                    elif 'WARN' in reading.upper() or 'OFFLINE' in reading.upper():
                        self.message_queue.add(reading, "warning")
                        print(f"[ARDUINO_WARN] {reading}")
                    elif 'Invalid' in reading:
                        self.message_queue.add(reading, "warning")
                        print(f"[ARDUINO_WARN] {reading}")

                    # ===== INFO MESSAGES =====
                    elif 'INFO' in reading.upper() or any(x in reading.upper() for x in ['RESCAN', 'FOUND', 'COMPLETE']):
                        self.message_queue.add(reading, "info")
                        print(f"[ARDUINO_INFO] {reading}")

                    # ===== UNKNOWN FORMAT =====
                    else:
                        self.message_queue.add(reading, "unknown")
                        print(f"[ARDUINO_UNKNOWN] {reading}")

                # Update state if needed
                if self.state_machine.current_state == SystemState.WAITING_FOR_SERIAL:
                    self.state_machine.set_state(SystemState.READING)

                # Detect disconnected sensors
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
    def __init__(self, data_manager, logger, state_machine, duration=None, interval=60):
        super().__init__(daemon=True)
        self.data_manager = data_manager
        self.logger = logger
        self.state_machine = state_machine
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
            if current_time - last_log >= self.interval:
                sensors = self.data_manager.get_sensors()
                if sensors:
                    self.logger.log_reading(sensors)
                last_log = current_time
            time.sleep(0.5)

    def stop(self):
        """Stop logging thread"""
        self.running = False

# ============================================================================
# FLASK APPLICATION
# ============================================================================

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Global managers
state_machine = TemperatureSystemStateMachine()
serial_handler = SerialHandler(use_mock=False)
data_manager = SensorDataManager()
logger = DataLogger()
serial_message_queue = SerialMessageQueue(max_messages=100)

# Global logging thread
logging_thread = None

# Config
SERIAL_PORT = "/dev/ttyACM0"
SERIAL_BAUDRATE = 9600
LOG_FOLDER = "/home/pi/temperature_logs/"

# ============================================================================
# ROUTES - API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    """Serve main dashboard"""
    return render_template('index.html')

@app.route('/api/sensors', methods=['GET'])
def get_sensors():
    """Get all current sensor readings"""
    sensors = data_manager.get_sensors()
    return jsonify({"sensors": sensors})

@app.route('/api/probes/rescan', methods=['POST'])
def rescan_probes():
    """Trigger Arduino to rescan for probes"""
    try:
        if serial_handler.ser and serial_handler.ser.is_open:
            serial_handler.ser.write(b"RESCAN\n")
        sensors = data_manager.get_sensors()
        return jsonify({"status": "ok", "sensors": sensors})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/probes/rename', methods=['POST'])
def rename_probe():
    """Rename a probe"""
    data = request.get_json()
    sensor_id = data.get('sensor_id')
    name = data.get('name')
    if not sensor_id or not name:
        return jsonify({"error": "Missing parameters"}), 400
    data_manager.rename_sensor(sensor_id, name)
    return jsonify({"status": "ok"})

@app.route('/api/logging/start', methods=['POST'])
def start_logging():
    """Start data logging session"""
    global logging_thread, logger
    if not state_machine.can_start_logging():
        return jsonify({"error": "System not ready for logging"}), 400
    data = request.get_json()
    folder = data.get('folder', LOG_FOLDER)
    duration = data.get('duration')
    interval = data.get('interval', 60)
    try:
        logger = DataLogger(folder)
        sensors = data_manager.get_sensors()
        filename = logger.start_session(sensors)
        if not filename:
            return jsonify({"error": "Failed to create log file"}), 500
        logging_thread = LoggingThread(data_manager, logger, state_machine, duration, interval)
        logging_thread.start()
        state_machine.set_logging_state(LoggingState.LOGGING)
        state_machine.set_state(SystemState.LOGGING)
        return jsonify({
            "status": "ok",
            "filename": filename,
            "startTime": int(time.time() * 1000),
            "duration": duration,
            "interval": interval
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logging/stop', methods=['POST'])
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
            return jsonify({"status": "ok", "filename": filename})
        else:
            return jsonify({"status": "error", "error": "Failed to close log file"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/graphs/data', methods=['GET'])
def get_graph_data():
    """Get historical graph data"""
    try:
        log_folder = Path(LOG_FOLDER)
        log_folder.mkdir(parents=True, exist_ok=True)
        requested_file = request.args.get('file')
        csv_files = sorted(log_folder.glob("temperature_log_*.csv"))
        if not csv_files:
            return jsonify({"sessions": {}, "files": []})
        files_list = [f.name for f in csv_files]
        if requested_file:
            requested_path = log_folder / requested_file
            if requested_path.exists():
                csv_files = [requested_path]
            else:
                csv_files = []
        sessions = {}
        for csv_file in csv_files:
            data = []
            try:
                with open(csv_file, "r") as f:
                    lines = f.readlines()
                    if not lines:
                        continue
                    headers = lines[0].strip().split(",")[1:]
                    for line in lines[1:]:
                        values = line.strip().split(",")
                        if len(values) > 1:
                            timestamp = values[0]
                            readings = {}
                            for i, header in enumerate(headers):
                                try:
                                    val = values[i + 1]
                                    readings[header] = float(val) if val != "NC" else None
                                except (ValueError, IndexError):
                                    readings[header] = None
                            data.append({"timestamp": timestamp, "readings": readings})
                if data:
                    sessions[csv_file.name] = data
            except Exception as e:
                print(f"[GRAPHS] Error loading {csv_file.name}: {e}")
        return jsonify({"sessions": sessions, "files": files_list})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/graphs/download', methods=['GET'])
def download_graph_csv():
    """Download historical data as CSV"""
    try:
        log_folder = Path(LOG_FOLDER)
        log_folder.mkdir(parents=True, exist_ok=True)
        csv_files = sorted(log_folder.glob("temperature_log_*.csv"))
        if not csv_files:
            return jsonify({"error": "No data available"}), 404
        combined_file = log_folder / "combined_export.csv"
        with open(combined_file, 'w') as outfile:
            for csv_file in csv_files:
                with open(csv_file, 'r') as infile:
                    outfile.write(infile.read())
        return send_file(combined_file, as_attachment=True, download_name="temperature_data.csv")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mock/enable', methods=['POST'])
def enable_mock_mode():
    """Enable mock mode"""
    global serial_handler
    try:
        serial_handler.use_mock = True
        msg = "Mock mode ENABLED - generating test data"
        serial_message_queue.add(msg, "info")
        print(f"[MOCK] {msg}")
        return jsonify({"status": "ok", "message": msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mock/disable', methods=['POST'])
def disable_mock_mode():
    """Disable mock mode"""
    global serial_handler, data_manager
    try:
        serial_handler.use_mock = False
        data_manager.sensors.clear()
        msg = "Mock mode DISABLED - waiting for Arduino"
        serial_message_queue.add(msg, "info")
        print(f"[MOCK] {msg}")
        return jsonify({"status": "ok", "message": msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/serial/messages', methods=['GET'])
def get_serial_messages():
    """Get serial monitor messages with optional type filter"""
    msg_type = request.args.get('type')
    messages = serial_message_queue.get_filtered(msg_type)
    return jsonify({"messages": messages})

@app.route('/api/serial/messages', methods=['DELETE'])
def clear_serial_messages():
    """Clear all serial messages"""
    serial_message_queue.clear()
    return jsonify({"status": "ok"})

@app.route('/api/system/status', methods=['GET'])
def system_status():
    """Get system status - INCLUDES mock_mode field"""
    state, logging_state, error = state_machine.get_state()
    return jsonify({
        "system_state": state.value,
        "logging_state": logging_state.value,
        "error": error,
        "serial_connected": serial_handler.is_connected,
        "mock_mode": serial_handler.use_mock
    })

# ============================================================================
# STARTUP & SHUTDOWN
# ============================================================================

def startup_sequence():
    """Initialize system on startup"""
    print("[STARTUP] Initializing Temperature Monitoring System v6.1")
    print(f"[STARTUP] Log folder: {LOG_FOLDER}")
    print("[STARTUP] Serial Message Queue: 100 messages max")
    Path(LOG_FOLDER).mkdir(parents=True, exist_ok=True)
    reader = SerialReaderThread(serial_handler, data_manager, state_machine, logger, serial_message_queue)
    reader.start()
    print("[STARTUP] Serial reader thread started")
    print("[STARTUP] System ready")

if __name__ == '__main__':
    startup_sequence()
    app.run(host='0.0.0.0', port=5000, debug=False)

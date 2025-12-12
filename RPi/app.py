from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import serial
import threading
import time
import json
import os
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
CORS(app)

# ============================================================================
# CONFIGURATION
# ============================================================================

SERIAL_PORT = '/dev/ttyUSB0'  # Change for your system
SERIAL_BAUD = 9600
SERIAL_TIMEOUT = 1

LOG_FOLDER = '/home/pi/temperature_logs/'
if not os.path.exists(LOG_FOLDER):
    os.makedirs(LOG_FOLDER)

# ============================================================================
# GLOBAL STATE
# ============================================================================

class SensorDataManager:
    def __init__(self):
        self.sensors = {}
        self.sensor_names = {}
        self.lock = threading.Lock()
        self.mock_mode = False
        self.mock_sensor_counter = 0
    
    def update_sensor(self, sensor_id, temperature, status="online"):
        with self.lock:
            if sensor_id not in self.sensors:
                if sensor_id.startswith('280000'):
                    self.mock_sensor_counter += 1
                    name = f"Mock Probe {self.mock_sensor_counter}"
                else:
                    name = f"Probe {sensor_id[:8]}"
                self.sensor_names[sensor_id] = name
            
            self.sensors[sensor_id] = {
                'temperature': temperature,
                'status': status,
                'name': self.sensor_names.get(sensor_id, f"Probe {sensor_id[:8]}"),
                'last_update': datetime.now().isoformat()
            }
    
    def get_sensors(self):
        with self.lock:
            return self.sensors.copy()
    
    def rename_sensor(self, sensor_id, new_name):
        with self.lock:
            if sensor_id in self.sensors:
                self.sensor_names[sensor_id] = new_name
                self.sensors[sensor_id]['name'] = new_name
                return True
            return False
    
    def delete_sensor(self, sensor_id):
        """Delete a sensor from the system"""
        with self.lock:
            if sensor_id in self.sensors:
                del self.sensors[sensor_id]
                if sensor_id in self.sensor_names:
                    del self.sensor_names[sensor_id]
                print(f"[SensorManager] Deleted sensor: {sensor_id}")
                return True
            print(f"[SensorManager] Sensor not found: {sensor_id}")
            return False
    
    def mark_offline(self, sensor_id):
        with self.lock:
            if sensor_id in self.sensors:
                self.sensors[sensor_id]['status'] = 'offline'
    
    def clear_all(self):
        with self.lock:
            self.sensors.clear()
            self.sensor_names.clear()
    
    def add_mock_sensor(self):
        import random
        self.mock_sensor_counter += 1
        sensor_id = f"28000000{self.mock_sensor_counter:06d}"
        temp = round(20 + random.uniform(-2, 5), 2)
        self.update_sensor(sensor_id, temp, "online")
    
    def get_mock_sensors_count(self):
        count = 0
        for sid in self.sensors:
            if sid.startswith('280000'):
                count += 1
        return count
    
    def enable_mock_mode(self, count=3):
        self.mock_mode = True
        self.clear_all()
        for i in range(count):
            self.add_mock_sensor()
    
    def disable_mock_mode(self):
        self.mock_mode = False
        with self.lock:
            mock_ids = [id for id in self.sensors if id.startswith('280000')]
            for id in mock_ids:
                del self.sensors[id]
                if id in self.sensor_names:
                    del self.sensor_names[id]

class DataLogger:
    def __init__(self, folder=LOG_FOLDER):
        self.folder = folder
        if not os.path.exists(folder):
            os.makedirs(folder)
        self.filename = None
        self.file_handle = None
        self.is_logging = False
        self.sensor_mapping = {}
    
    def start(self, sensors, interval=60):
        if self.is_logging:
            return False
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.filename = os.path.join(self.folder, f'temperature_log_{timestamp}.csv')
        
        # Capture sensor names at logging start
        self.sensor_mapping = {id: sensor['name'] for id, sensor in sensors.items()}
        
        # Create CSV with sensor names as headers
        try:
            self.file_handle = open(self.filename, 'w', newline='')
            sorted_ids = sorted(self.sensor_mapping.keys())
            headers = ['Timestamp'] + [f"{self.sensor_mapping[id]} ({id[:8]})" for id in sorted_ids]
            self.file_handle.write(','.join(headers) + '\n')
            self.file_handle.flush()
            self.is_logging = True
            print(f"[Logger] Started logging to {self.filename}")
            return True
        except Exception as e:
            print(f"[Logger] Error starting logging: {e}")
            return False
    
    def log_reading(self, sensors):
        if not self.is_logging or not self.file_handle:
            return False
        
        try:
            timestamp = datetime.now().isoformat()
            sorted_ids = sorted(self.sensor_mapping.keys())
            row = [timestamp]
            
            for sensor_id in sorted_ids:
                if sensor_id in sensors:
                    temp = sensors[sensor_id].get('temperature', 'NC')
                    row.append(str(temp))
                else:
                    row.append('NC')
            
            self.file_handle.write(','.join(row) + '\n')
            self.file_handle.flush()
            return True
        except Exception as e:
            print(f"[Logger] Error logging reading: {e}")
            return False
    
    def stop(self):
        if not self.is_logging:
            return False
        
        try:
            if self.file_handle:
                self.file_handle.close()
            self.is_logging = False
            print(f"[Logger] Stopped logging")
            return True
        except Exception as e:
            print(f"[Logger] Error stopping logging: {e}")
            return False

# Global managers
data_manager = SensorDataManager()
data_logger = DataLogger()
serial_thread = None
serial_messages = []
MAX_SERIAL_MESSAGES = 1000
logging_thread = None
logging_stop_event = threading.Event()

# ============================================================================
# SERIAL COMMUNICATION
# ============================================================================

def read_serial():
    global serial_thread
    
    ser = None
    while True:
        try:
            if ser is None or not ser.is_open:
                try:
                    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
                    print("[Serial] Connected")
                except:
                    time.sleep(2)
                    continue
            
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                
                # Log to serial buffer
                msg_type = 'unknown'
                if line.startswith('[INFO]'):
                    msg_type = 'info'
                    line = line[7:].strip()
                elif line.startswith('[ERROR]'):
                    msg_type = 'error'
                    line = line[8:].strip()
                elif line.startswith('[WARN]'):
                    msg_type = 'warning'
                    line = line[7:].strip()
                elif ':' in line and ',' in line:
                    msg_type = 'temperature'
                
                add_serial_message(line, msg_type)
                
                # Parse temperature data
                if ':' in line and ',' in line:
                    try:
                        readings = line.split(',')
                        for reading in readings:
                            parts = reading.split(':')
                            if len(parts) == 2:
                                sensor_id = parts[0].strip()
                                temp = float(parts[1].strip())
                                data_manager.update_sensor(sensor_id, temp, "online")
                    except:
                        pass
        
        except Exception as e:
            print(f"[Serial] Error: {e}")
            if ser:
                try:
                    ser.close()
                except:
                    pass
                ser = None
            time.sleep(2)

def add_serial_message(message, msg_type='unknown'):
    global serial_messages
    serial_messages.append({
        'timestamp': time.time(),
        'message': message,
        'type': msg_type
    })
    if len(serial_messages) > MAX_SERIAL_MESSAGES:
        serial_messages.pop(0)

def logging_worker():
    """Background worker for data logging"""
    global logging_stop_event
    
    while not logging_stop_event.is_set():
        if data_logger.is_logging:
            sensors = data_manager.get_sensors()
            data_logger.log_reading(sensors)
        time.sleep(1)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/sensors')
def get_sensors():
    sensors = data_manager.get_sensors()
    return jsonify({"sensors": sensors})

@app.route('/api/probes/rename', methods=['POST'])
def rename_probe():
    try:
        data = request.get_json()
        sensor_id = data.get('sensor_id')
        name = data.get('name')
        
        if not sensor_id or not name:
            return jsonify({"error": "Missing parameters"}), 400
        
        success = data_manager.rename_sensor(sensor_id, name)
        if success:
            sensors = data_manager.get_sensors()
            return jsonify({"status": "ok", "sensors": sensors})
        else:
            return jsonify({"error": "Sensor not found"}), 404
    except Exception as e:
        print(f"[API] Rename error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/probes/delete', methods=['POST'])
def delete_probe():
    """Delete a temperature probe from the system"""
    try:
        data = request.get_json()
        sensor_id = data.get('sensor_id')
        
        if not sensor_id:
            return jsonify({"error": "Missing sensor_id"}), 400
        
        # Remove sensor from data manager
        success = data_manager.delete_sensor(sensor_id)
        
        if success:
            # Return updated sensor list
            sensors = data_manager.get_sensors()
            return jsonify({"status": "ok", "sensors": sensors})
        else:
            return jsonify({"error": "Sensor not found"}), 404
            
    except Exception as e:
        print(f"[API] Delete probe error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/probes/rescan', methods=['POST'])
def rescan_probes():
    return jsonify({"status": "ok"})

@app.route('/api/mock/enable', methods=['POST'])
def enable_mock():
    data_manager.enable_mock_mode(3)
    sensors = data_manager.get_sensors()
    return jsonify({"status": "ok", "sensors": sensors})

@app.route('/api/mock/disable', methods=['POST'])
def disable_mock():
    data_manager.disable_mock_mode()
    sensors = data_manager.get_sensors()
    return jsonify({"status": "ok", "sensors": sensors})

@app.route('/api/logging/start', methods=['POST'])
def start_logging():
    try:
        data = request.get_json()
        folder = data.get('folder', LOG_FOLDER).strip()
        interval = data.get('interval', 60)
        
        if not folder:
            folder = LOG_FOLDER
        
        logger = DataLogger(folder)
        sensors = data_manager.get_sensors()
        
        if logger.start(sensors, interval):
            global data_logger
            data_logger = logger
            return jsonify({"status": "ok", "filename": logger.filename})
        else:
            return jsonify({"error": "Failed to start logging"}), 500
    except Exception as e:
        print(f"[API] Logging start error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/logging/stop', methods=['POST'])
def stop_logging():
    global data_logger
    if data_logger.stop():
        return jsonify({"status": "ok", "filename": data_logger.filename})
    return jsonify({"error": "Logging not active"}), 400

@app.route('/api/system/status')
def system_status():
    return jsonify({
        "system_state": "running",
        "logging_state": "logging" if data_logger.is_logging else "stopped",
        "serial_connected": True,
        "mock_mode": data_manager.mock_mode,
        "sensor_count": len(data_manager.get_sensors())
    })

@app.route('/api/graphs/data')
def get_graph_data():
    sessions = {}
    files = []
    
    try:
        if os.path.exists(LOG_FOLDER):
            for f in sorted(os.listdir(LOG_FOLDER), reverse=True)[:10]:
                if f.endswith('.csv'):
                    files.append(f)
                    file_path = os.path.join(LOG_FOLDER, f)
                    sessions[f] = parse_csv(file_path)
    except Exception as e:
        print(f"[API] Graph data error: {e}")
    
    return jsonify({"sessions": sessions, "files": files})

def parse_csv(filepath):
    data = []
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            if len(lines) < 2:
                return data
            
            headers = lines[0].strip().split(',')
            
            for line in lines[1:]:
                parts = line.strip().split(',')
                if len(parts) >= 1:
                    readings = {}
                    for i, header in enumerate(headers[1:]):
                        if i + 1 < len(parts):
                            try:
                                if parts[i + 1] != 'NC':
                                    readings[header.split('(')[1].strip(')')] = float(parts[i + 1])
                            except:
                                pass
                    
                    data.append({
                        'timestamp': parts[0],
                        'readings': readings
                    })
    except Exception as e:
        print(f"[Parse CSV] Error: {e}")
    
    return data

@app.route('/api/graphs/download')
def download_graphs():
    try:
        file_path = os.path.join(LOG_FOLDER, 'combined_logs.csv')
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name='temperature_logs.csv')
        return jsonify({"error": "No logs available"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/serial/messages')
def get_serial_messages():
    msg_type = request.args.get('type', '')
    
    if msg_type:
        messages = [m for m in serial_messages if m['type'] == msg_type]
    else:
        messages = serial_messages
    
    return jsonify({"messages": messages[-100:]})

@app.route('/api/serial/messages', methods=['DELETE'])
def delete_serial_messages():
    global serial_messages
    serial_messages = []
    return jsonify({"status": "ok"})

# ============================================================================
# STARTUP
# ============================================================================

if __name__ == '__main__':
    print("[System] Starting temperature monitoring system...")
    
    # Start serial thread
    serial_thread = threading.Thread(target=read_serial, daemon=True)
    serial_thread.start()
    
    # Start logging worker thread
    logging_stop_event.clear()
    logging_thread = threading.Thread(target=logging_worker, daemon=True)
    logging_thread.start()
    
    # Run Flask
    app.run(host='0.0.0.0', port=5000, debug=False)

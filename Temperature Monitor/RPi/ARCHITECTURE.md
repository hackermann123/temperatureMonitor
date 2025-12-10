# System Architecture & Modularization Guide

## High-Level Architecture

```
┌────────────────────────────────────────────────────────────┐
│                   Web Browser (Dashboard)                  │
│         HTML5 + JavaScript + Chart.js (Frontend)           │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP/JSON
                         ↓
┌────────────────────────────────────────────────────────────┐
│              Flask Web Server (app.py)                      │
│                  Route Handlers & API                       │
└────────────────────────┬─────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ↓                ↓                ↓
  ┌──────────────┐  ┌──────────┐  ┌──────────────┐
  │   Managers   │  │ Threads  │  │    State     │
  │              │  │          │  │   Machine    │
  └──────────────┘  └──────────┘  └──────────────┘
        ↓                ↓
  ┌──────────────┐  ┌──────────────────┐
  │ Serial Comm. │  │  Data Processing │
  │ Handlers     │  │  & Logging       │
  └──────────────┘  └──────────────────┘
        ↓
  ┌──────────────────────────────────┐
  │    Arduino + DS18B20 Sensors     │
  └──────────────────────────────────┘
```

---

## Module Breakdown

### 1. **State Machine Module** (Embedded in app.py)

**Classes:**
- `SystemState` (Enum): WAITING_FOR_SERIAL, READING, LOGGING, ERROR
- `LoggingState` (Enum): IDLE, LOGGING, STOPPING
- `TemperatureSystemStateMachine`: State transitions

**Responsibility:**
- Track system state
- Enforce valid transitions
- Thread-safe state access

**How to extend:**
```python
# Add new state
class SystemState(Enum):
    IDLE = "idle"
    WAITING_FOR_SERIAL = "waiting_for_serial"
    READING = "reading"
    LOGGING = "logging"
    CALIBRATING = "calibrating"  # NEW
    ERROR = "error"

# Add transition logic
def can_calibrate(self):
    return self.current_state == SystemState.READING
```

---

### 2. **Serial Communication Module** (SerialHandler)

**Location:** app.py

**Methods:**
- `connect()`: Open serial port
- `read_line()`: Read from Arduino
- `disconnect()`: Close connection
- `_generate_mock_data()`: Mock mode

**Responsibility:**
- USB/serial port management
- Non-blocking data reading
- Auto-reconnection
- Mock data generation for testing

**How to extend:**

**Option A: Add baudrate auto-detection**
```python
def auto_detect_baudrate(self):
    """Try common baudrates to find Arduino"""
    baudrates = [9600, 115200, 230400]
    for rate in baudrates:
        try:
            self.ser = serial.Serial(self.port, rate, timeout=1)
            self.ser.write(b"PING\n")
            response = self.ser.readline()
            if response:
                self.baudrate = rate
                return True
            self.ser.close()
        except:
            pass
    return False
```

**Option B: Add protocol formats**
```python
class SerialProtocol(Enum):
    COMMA_SEPARATED = "28ABC:25.50,28DEF:26.75"
    JSON = '{"28ABC": 25.50, "28DEF": 26.75}'
    NEWLINE_DELIMITED = "28ABC:25.50\n28DEF:26.75"

def parse_data(self, line):
    if self.protocol == SerialProtocol.JSON:
        return json.loads(line)
    elif self.protocol == SerialProtocol.COMMA_SEPARATED:
        return self._parse_csv(line)
```

---

### 3. **Sensor Data Manager Module** (SensorDataManager)

**Location:** app.py

**Methods:**
- `update_sensor()`: Update reading
- `set_offline()`: Mark offline
- `add_to_history()`: Store historical data
- `get_sensors()`: Retrieve all data
- `rename_sensor()`: Change probe name
- `detect_disconnected()`: Find offline probes

**Responsibility:**
- Store current sensor state
- Maintain temperature history
- Track online/offline status
- Thread-safe data access

**How to extend:**

**Option A: Add statistics**
```python
def get_sensor_stats(self, sensor_id):
    """Return min/max/avg temperature"""
    history = self.history.get(sensor_id, [])
    temps = [h['temperature'] for h in history]
    return {
        'min': min(temps),
        'max': max(temps),
        'avg': sum(temps) / len(temps),
        'count': len(temps)
    }
```

**Option B: Add alert thresholds**
```python
def __init__(self):
    self.sensors = {}
    self.thresholds = {}  # {sensor_id: {'high': 30, 'low': 15}}
    
def check_thresholds(self, sensor_id, temperature):
    """Check if temperature exceeds limits"""
    if sensor_id not in self.thresholds:
        return None
    
    threshold = self.thresholds[sensor_id]
    if temperature > threshold['high']:
        return 'HIGH'
    elif temperature < threshold['low']:
        return 'LOW'
    return None
```

---

### 4. **Data Logger Module** (DataLogger)

**Location:** app.py

**Methods:**
- `start_session()`: Create CSV file
- `log_reading()`: Write data row
- `end_session()`: Close file
- `load_session_data()`: Read historical data

**Responsibility:**
- CSV file creation and management
- Timestamp handling
- Session tracking

**How to extend:**

**Option A: Add JSON logging**
```python
def log_reading_json(self, sensors_dict):
    """Log as JSON instead of CSV"""
    data = {
        'timestamp': datetime.now().isoformat(),
        'sensors': {}
    }
    for sensor_id, sensor in sensors_dict.items():
        data['sensors'][sensor_id] = {
            'temperature': sensor['temperature'],
            'status': sensor['status']
        }
    self.current_handle.write(json.dumps(data) + '\n')
    self.current_handle.flush()
```

**Option B: Add compression**
```python
import gzip

def start_session(self, sensors):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"temperature_log_{timestamp}.csv.gz"
    filepath = self.folder / filename
    
    self.current_handle = gzip.open(filepath, 'wt')
    # ... rest of code
```

**Option C: Add database backend**
```python
class DatabaseLogger:
    def __init__(self, db_url="sqlite:///temperatures.db"):
        from sqlalchemy import create_engine, Column, DateTime, Float, String
        self.engine = create_engine(db_url)
        
    def log_reading(self, sensors_dict):
        """Store in database instead of CSV"""
        for sensor_id, sensor in sensors_dict.items():
            record = SensorReading(
                sensor_id=sensor_id,
                temperature=sensor['temperature'],
                timestamp=datetime.now()
            )
            db.session.add(record)
        db.session.commit()
```

---

### 5. **Serial Reader Thread Module** (SerialReaderThread)

**Location:** app.py

**Methods:**
- `run()`: Main thread loop
- `_trigger_arduino_rescan()`: Send rescan command
- `stop()`: Shutdown thread

**Responsibility:**
- Background serial reading
- Data parsing
- Sensor state updates
- Periodic rescans

**How to extend:**

**Option A: Add data validation**
```python
def _validate_reading(self, sensor_id, temp):
    """Reject out-of-range temperatures"""
    # DS18B20 physical limits: -55 to 125°C
    if temp < -55 or temp > 125:
        return False
    
    # Check for sudden jumps (possible noise)
    if sensor_id in self.data_manager.sensors:
        last_temp = self.data_manager.sensors[sensor_id]['temperature']
        if abs(temp - last_temp) > 5:  # 5°C max change
            return False
    
    return True

# In run() loop
if self._validate_reading(sensor_id, temp):
    self.data_manager.update_sensor(sensor_id, temp)
else:
    print(f"Rejected invalid reading for {sensor_id}: {temp}")
```

**Option B: Add averaging filter**
```python
def __init__(self, ...):
    # ...
    self.reading_buffer = {}  # Store last N readings
    self.buffer_size = 5
    
def _get_average_temp(self, sensor_id):
    """Return average of last N readings"""
    if sensor_id not in self.reading_buffer:
        return None
    temps = self.reading_buffer[sensor_id]
    return sum(temps) / len(temps)
```

---

### 6. **Logging Thread Module** (LoggingThread)

**Location:** app.py

**Methods:**
- `run()`: Main logging loop
- `stop()`: Shutdown thread

**Responsibility:**
- Timed data logging
- Duration management
- Interval scheduling

**How to extend:**

**Option A: Add early stop detection**
```python
def run(self):
    # ...
    while self.running:
        # Stop if detected error condition
        if self.detect_error_condition():
            print("[LOGGER] Error detected, stopping")
            self.running = False
            break

def detect_error_condition(self):
    """Check if we should abort logging"""
    sensors = self.data_manager.get_sensors()
    online_count = sum(1 for s in sensors.values() if s['status'] == 'online')
    
    # Stop if all sensors offline
    if online_count == 0:
        return True
    
    return False
```

**Option B: Add dynamic interval adjustment**
```python
def run(self):
    self.running = True
    self.start_time = time.time()
    last_log = self.start_time
    
    while self.running:
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Adapt interval based on conditions
        adaptive_interval = self._calculate_adaptive_interval()
        
        if current_time - last_log >= adaptive_interval:
            sensors = self.data_manager.get_sensors()
            if sensors:
                self.logger.log_reading(sensors)
                last_log = current_time
        
        time.sleep(0.5)

def _calculate_adaptive_interval(self):
    """Adjust interval based on conditions"""
    sensors = self.data_manager.get_sensors()
    
    # Faster sampling if large changes detected
    for sensor in sensors.values():
        if sensor['status'] == 'offline':
            return self.interval * 2  # Slower if sensors offline
    
    return self.interval
```

---

## Creating New Feature Modules

### Example 1: Email Alert System

**File:** `email_alerts.py`

```python
import smtplib
from email.mime.text import MIMEText

class EmailAlertManager:
    def __init__(self, smtp_host, smtp_user, smtp_pass):
        self.smtp_host = smtp_host
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.alerts_sent = {}
    
    def send_alert(self, sensor_id, sensor_name, temperature, threshold_type):
        """Send email alert for threshold breach"""
        # Throttle alerts (max 1 per hour per sensor)
        if self._should_throttle(sensor_id):
            return
        
        message = f"""
Temperature Alert!

Sensor: {sensor_name} ({sensor_id})
Temperature: {temperature}°C
Threshold Breached: {threshold_type}

Timestamp: {datetime.now().isoformat()}
"""
        
        try:
            server = smtplib.SMTP(self.smtp_host, 587)
            server.starttls()
            server.login(self.smtp_user, self.smtp_pass)
            
            msg = MIMEText(message)
            msg['Subject'] = f"Temperature Alert: {sensor_name}"
            
            server.send_message(msg)
            server.quit()
            
            self._record_alert(sensor_id)
        except Exception as e:
            print(f"Failed to send alert: {e}")
    
    def _should_throttle(self, sensor_id):
        """Check if alert was sent recently"""
        if sensor_id not in self.alerts_sent:
            return False
        
        return time.time() - self.alerts_sent[sensor_id] < 3600
    
    def _record_alert(self, sensor_id):
        """Record when alert was sent"""
        self.alerts_sent[sensor_id] = time.time()

# Usage in app.py
from email_alerts import EmailAlertManager

alert_manager = EmailAlertManager("smtp.gmail.com", "user@gmail.com", "password")

# In SerialReaderThread.run()
for sensor_id, reading in readings.items():
    status = data_manager.check_thresholds(sensor_id, reading['temperature'])
    if status == 'HIGH':
        alert_manager.send_alert(sensor_id, reading['name'], reading['temperature'], 'HIGH')
```

---

### Example 2: Database Backend

**File:** `database.py`

```python
from sqlalchemy import create_engine, Column, DateTime, Float, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class SensorReading(Base):
    __tablename__ = 'sensor_readings'
    
    id = Column(Integer, primary_key=True)
    sensor_id = Column(String, index=True)
    sensor_name = Column(String)
    temperature = Column(Float)
    timestamp = Column(DateTime, index=True, default=datetime.utcnow)

class DatabaseManager:
    def __init__(self, db_url="sqlite:///temperatures.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def log_reading(self, sensors_dict):
        """Store sensor reading in database"""
        session = self.Session()
        try:
            for sensor_id, sensor in sensors_dict.items():
                reading = SensorReading(
                    sensor_id=sensor_id,
                    sensor_name=sensor.get('name'),
                    temperature=sensor['temperature']
                )
                session.add(reading)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Database error: {e}")
        finally:
            session.close()
    
    def get_readings(self, sensor_id, hours=24):
        """Retrieve readings for specified period"""
        session = self.Session()
        from datetime import timedelta
        
        since = datetime.utcnow() - timedelta(hours=hours)
        readings = session.query(SensorReading).filter(
            SensorReading.sensor_id == sensor_id,
            SensorReading.timestamp >= since
        ).order_by(SensorReading.timestamp).all()
        
        session.close()
        return readings

# Usage in app.py
from database import DatabaseManager

db_manager = DatabaseManager()

# Replace DataLogger with database
# In logging thread
db_manager.log_reading(data_manager.get_sensors())
```

---

### Example 3: Web-Based Configuration

**File:** `config_manager.py`

```python
import json
from pathlib import Path

class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = Path(config_file)
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from JSON"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return self._default_config()
    
    def _default_config(self):
        return {
            'serial_port': '/dev/ttyACM0',
            'baudrate': 9600,
            'sampling_interval': 2000,
            'log_folder': '/home/pi/temperature_logs/',
            'probes': {}
        }
    
    def save_config(self):
        """Save configuration to JSON"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def set(self, key, value):
        self.config[key] = value
        self.save_config()

# Usage in app.py
config = ConfigManager()

serial_handler = SerialHandler(
    port=config.get('serial_port'),
    baudrate=config.get('baudrate')
)

logger = DataLogger(folder=config.get('log_folder'))

# Add API endpoint for configuration
@app.route('/api/config', methods=['GET', 'POST'])
def manage_config():
    if request.method == 'GET':
        return jsonify(config.config)
    else:
        data = request.get_json()
        for key, value in data.items():
            config.set(key, value)
        return jsonify({'status': 'ok'})
```

---

## Best Practices for Extensions

1. **Maintain Thread Safety**
   - Use locks for shared state
   - Avoid blocking operations
   - Use queues for inter-thread communication

2. **Error Handling**
   - Catch exceptions in threads
   - Log errors with context
   - Don't let one module crash the system

3. **Configuration**
   - Make values configurable
   - Use sensible defaults
   - Avoid hardcoded paths

4. **Testing**
   - Test with mock data first
   - Implement unit tests
   - Test edge cases

5. **Performance**
   - Profile before optimizing
   - Avoid unnecessary logging
   - Use appropriate data structures

---

## Dependency Injection Pattern

For cleaner code and better testability:

```python
class SerialReaderThread(threading.Thread):
    def __init__(self, serial_handler, data_manager, state_machine, logger):
        # Dependencies injected
        self.serial_handler = serial_handler
        self.data_manager = data_manager
        self.state_machine = state_machine
        self.logger = logger

# Usage
reader = SerialReaderThread(
    serial_handler=SerialHandler(),
    data_manager=SensorDataManager(),
    state_machine=TemperatureSystemStateMachine(),
    logger=DataLogger()
)
reader.start()

# Easy to swap implementations for testing
reader = SerialReaderThread(
    serial_handler=MockSerialHandler(),
    data_manager=SensorDataManager(),
    state_machine=TemperatureSystemStateMachine(),
    logger=MockDataLogger()
)
```

---

## File Organization Recommendation

```
~/temperature_monitor/
├── app.py                          # Main Flask app
├── requirements.txt
├── arduino_sketch.ino
│
├── modules/                        # New modules
│   ├── __init__.py
│   ├── state_machine.py           # Extract StateMachine classes
│   ├── serial_handler.py          # Extract SerialHandler
│   ├── sensor_manager.py          # Extract SensorDataManager
│   ├── data_logger.py             # Extract DataLogger
│   ├── email_alerts.py            # New feature
│   └── database.py                # New feature
│
├── templates/
│   └── index.html
│
├── static/
│   └── style.css                  # Optional separate CSS
│
├── tests/                          # Unit tests
│   ├── test_state_machine.py
│   ├── test_serial_handler.py
│   └── test_sensor_manager.py
│
├── docs/
│   ├── SETUP_GUIDE.md
│   ├── QUICK_START.md
│   └── ARCHITECTURE.md
│
└── logs/                           # Created at runtime
    └── (CSV files)
```

---

**The system is designed for easy extension. Start simple and add features as needed!**

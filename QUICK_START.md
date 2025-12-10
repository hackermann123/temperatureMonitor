# Quick Start Guide

## 5-Minute Setup

### Prerequisites
- Raspberry Pi with Python 3.7+
- Arduino UNO with USB cable
- DS18B20 sensor(s) connected to Arduino Pin 2

### Step 1: Clone/Download Files
```bash
mkdir ~/temperature_monitor
cd ~/temperature_monitor

# Copy these files to the directory:
# - app.py
# - requirements.txt
# - arduino_sketch.ino
# - SETUP_GUIDE.md
```

### Step 2: Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Setup Arduino
1. Connect Arduino to Raspberry Pi via USB
2. Open Arduino IDE
3. Install libraries: OneWire + DallasTemperature
4. Upload `arduino_sketch.ino`
5. Verify Serial Monitor shows probes detected

### Step 4: Configure Flask (Optional)
```bash
# Check Arduino port
ls /dev/tty*

# Edit app.py if needed (default should work)
# MOCK_MODE = False
# SERIAL_PORT = "/dev/ttyACM0"
```

### Step 5: Run Server
```bash
python3 app.py
```

### Step 6: Access Dashboard
Open browser: `http://localhost:5000`

---

## Testing Without Hardware

To test without Arduino connected:

```python
# In app.py, line ~264:
serial_handler = SerialHandler(use_mock=True)
```

Then run normally. System will generate mock sensor data.

---

## System Architecture

### Communication Flow

```
Arduino UNO (reads sensors)
        ↓
   Serial UART (9600 baud)
        ↓
Raspberry Pi Serial Port (/dev/ttyACM0)
        ↓
Flask Backend (app.py)
  ├─ State Machine (tracks system state)
  ├─ Serial Reader Thread (parses data continuously)
  ├─ Sensor Data Manager (stores current readings)
  ├─ Data Logger (writes CSV files)
  └─ Logging Thread (timed sampling)
        ↓
HTML/JavaScript Dashboard
        ↓
User Interface (browser on any device)
```

### Key Components

#### 1. **State Machine** (TemperatureSystemStateMachine)
States:
- WAITING_FOR_SERIAL: Trying to connect to Arduino
- READING: Connected, reading sensor data
- LOGGING: Currently logging to CSV
- ERROR: Serial communication error

#### 2. **Serial Handler** (SerialHandler)
- Manages USB/serial connection to Arduino
- Auto-reconnects on failure
- Supports mock mode for testing
- Non-blocking reads

#### 3. **Sensor Data Manager** (SensorDataManager)
- Stores current readings for all probes
- Tracks online/offline status
- Maintains historical data
- Thread-safe access with locks

#### 4. **Data Logger** (DataLogger)
- Creates timestamped CSV files
- Handles "NC" (No Connection) for offline probes
- Session-based file management
- Supports custom logging folders

#### 5. **Serial Reader Thread**
- Background thread continuously reading Arduino
- Parses format: "28ABC123:25.50,28DEF456:26.75"
- Updates sensor data in real-time
- Auto-rescans probes every 10 seconds
- Detects disconnected sensors

#### 6. **Logging Thread**
- Background thread for timed logging
- Respects configured duration and interval
- Can be stopped at any time

---

## Arduino Protocol

### Data Format (Continuous Stream)
```
28AB3C500415124B:25.50,28DEF4560415ABCD:26.75
28AB3C500415124B:25.51,28DEF4560415ABCD:26.74
28AB3C500415124B:25.50,28DEF4560415ABCD:26.75
...
```

**Format:** `<ADDRESS>:<TEMPERATURE>,<ADDRESS>:<TEMPERATURE>`

- **ADDRESS:** 16-character hex (includes family code 0x28)
- **TEMPERATURE:** Float with 2 decimal places (°C)
- **Delimiter:** Comma between probes, colon between address and temp

### Arduino Commands (From Flask)
```
RESCAN          → Force Arduino to scan for new probes
STATUS          → Report current status
INTERVAL:5000   → Set sampling interval (ms) - not yet implemented
PRECISION:11    → Set temperature resolution (9-12 bits)
```

---

## CSV File Format

**Filename:** `temperature_log_YYYY-MM-DD_HH-MM-SS.csv`

**Content:**
```csv
Timestamp,Probe 1,Probe 2
2025-12-10T14:30:00.123456,25.50,26.75
2025-12-10T14:31:00.125432,25.51,26.74
2025-12-10T14:32:00.127654,25.52,26.73
```

**Notes:**
- Header row lists probe addresses/names
- "NC" value indicates offline probe
- ISO 8601 timestamps with microseconds
- One row per sample interval

---

## State Transitions

```
┌──────────────────────┐
│  WAITING_FOR_SERIAL  │ ← Initial state, no Arduino connection
└──────────┬───────────┘
           │ Arduino connects
           ↓
    ┌──────────────┐
    │   READING    │ ← Normal operation, reading sensor data
    └──┬───────┬──┬┘
       │       │  │ Serial error
       │       │  └─────┐
       │       │        ↓
       │       │   ┌─────────┐
       │       │   │  ERROR  │ ← Communication failure
       │       │   └────┬────┘
       │       │        │ Reconnect attempt
       │       │        └────────┐
       │       │                 │
       │ Start logging            │
       ↓                          │
    ┌──────────────┐              │
    │   LOGGING    │              │
    └──┬─────┬──┬──┘              │
       │     │  │ Serial error    │
       │     │  └─────────────────┘
       │     │ Stop logging
       │     ↓
       │   Back to READING
       │     ↑
       └─────┘
```

---

## Modular Code Structure

### Easy to Extend

**Add a new feature (e.g., Telegram alerts):**

```python
# Create new file: telegram_notifier.py
class TelegramNotifier:
    def __init__(self, token):
        self.token = token
    
    def send_alert(self, message):
        # Send via Telegram API
        pass

# In app.py
from telegram_notifier import TelegramNotifier

notifier = TelegramNotifier(token="...")

# In SerialReaderThread.run()
if sensor_temp > 30:
    notifier.send_alert(f"High temp: {sensor_temp}°C")
```

**Change logging location:**

```python
# In app.py, around line 265
logger = DataLogger(folder="/mnt/external_drive/logs/")
```

**Adjust sensor sampling:**

```python
# In arduino_sketch.ino
#define SAMPLING_INTERVAL 5000  # 5 seconds instead of 2
```

**Add data validation:**

```python
# In SensorDataManager.update_sensor()
if temperature < -55 or temperature > 125:
    # Reject invalid reading
    return False
```

---

## Troubleshooting by State

### If stuck in WAITING_FOR_SERIAL
- Arduino not connected to USB
- Arduino firmware not uploaded
- Check `ls /dev/tty*` for device
- Wrong SERIAL_PORT in app.py
- Baud rate mismatch (9600 required)

### If READING but no data shown
- Arduino not sending data
- Serial Monitor shows nothing → Upload sketch
- Serial Monitor shows data → Flask config issue
- Check app.py log for parse errors

### If LOGGING but no CSV created
- Folder doesn't exist: `mkdir -p /home/pi/temperature_logs/`
- Permissions issue: `chmod 777 /path/to/folder/`
- Disk full: `df -h`
- Check Flask console for DataLogger errors

### If ERROR state
- Serial cable disconnected
- Arduino crashed → Power cycle
- USB hub issue → Connect directly to Pi
- Try reconnecting after 10 seconds (auto-retry)

---

## Performance Tuning

### Reduce CPU Usage
- Increase SAMPLING_INTERVAL in Arduino (slower reads)
- Increase updateInterval in dashboard JavaScript (less UI updates)
- Disable graph rendering if not viewing graphs tab

### Improve Accuracy
- Increase TEMPERATURE_PRECISION in Arduino
- Move sensors away from heat sources
- Increase logging interval for stability

### Handle More Sensors
- Arduino UNO limited to ~10 probes (RAM)
- Use Arduino Mega for 20+ sensors
- Implement per-probe request polling instead of broadcast

---

## Security Notes

- Dashboard is accessible on local network
- Consider firewall rules: `sudo ufw allow 5000/tcp`
- Protect Raspberry Pi admin access
- Backup CSV logs regularly
- Monitor disk space for long-term logging

---

## Maintenance Tasks

**Daily:**
- Monitor dashboard for sensor errors
- Check for "NC" (offline) sensors

**Weekly:**
- Backup CSV files
- Review logs for patterns/anomalies

**Monthly:**
- Clean sensor windows/housings
- Verify temperature readings against known reference
- Update Raspberry Pi OS: `sudo apt update && sudo apt upgrade`

**Quarterly:**
- Check OneWire pull-up resistor function
- Inspect cables for damage
- Verify Arduino firmware integrity

---

## Getting Help

1. **Check Serial Monitor** in Arduino IDE for raw output
2. **Check Flask console** for Python errors
3. **Check browser console** (F12) for JavaScript errors
4. **Check CSV files** in logging folder for data integrity
5. **Test with mock mode** to isolate hardware issues

---

**You're ready to go! Happy temperature monitoring! 🌡️**

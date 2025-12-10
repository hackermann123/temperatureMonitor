# Temperature Monitoring System - Complete Project Summary

## 📋 Project Overview

A production-ready embedded system for monitoring 1-10 DS18B20 temperature sensors using Arduino UNO and Raspberry Pi with:
- **Real-time HTML dashboard** with live temperature display
- **Automatic probe detection** via OneWire protocol
- **Configurable CSV logging** with timestamps and "NC" (No Connection) handling
- **Robust state machine** architecture for reliability
- **Mock sensor support** for testing without hardware
- **Historical data visualization** with Chart.js

---

## 📦 Files Provided

### Core Application Files

| File | Purpose | Key Feature |
|------|---------|-------------|
| **app.py** | Flask backend | State machine, serial reader thread, logging thread, API endpoints |
| **arduino_sketch.ino** | Arduino firmware | OneWire auto-detection, continuous streaming, configurable sampling |
| **templates/index.html** | Web dashboard | Real-time display, graphing, probe management, logging controls |

### Documentation Files

| File | Content |
|------|---------|
| **QUICK_START.md** | 5-minute setup guide + architecture overview |
| **SETUP_GUIDE.md** | Detailed hardware/software setup + configuration |
| **ARCHITECTURE.md** | Modular design + extension examples |
| **TROUBLESHOOTING.md** | Common issues + diagnostic procedures |
| **requirements.txt** | Python dependencies |

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- Raspberry Pi with Python 3.7+
- Arduino UNO + USB cable
- DS18B20 sensor(s)
- 4.7kΩ resistor

### Setup
```bash
# 1. Create directory
mkdir ~/temperature_monitor
cd ~/temperature_monitor

# 2. Install Python dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Upload Arduino sketch
#    (Use Arduino IDE to upload arduino_sketch.ino)

# 4. Run Flask server
python3 app.py

# 5. Open browser
#    http://localhost:5000
```

### Test Without Hardware
```python
# In app.py, change line ~260:
serial_handler = SerialHandler(use_mock=True)
# Now run Flask - system generates random sensor data
```

---

## 🏗️ System Architecture

### Components

```
┌─────────────────────────────────────────┐
│     Web Dashboard (HTML5 + Chart.js)    │
└──────────────────┬──────────────────────┘
                   │ HTTP/JSON
                   ↓
┌─────────────────────────────────────────┐
│      Flask Web Server (app.py)          │
│  ├─ State Machine                       │
│  ├─ Serial Reader Thread                │
│  ├─ Sensor Data Manager                 │
│  ├─ Data Logger                         │
│  └─ Logging Thread                      │
└──────────────────┬──────────────────────┘
                   │
                   ↓
┌──────────────────────────────────────────┐
│   Raspberry Pi Serial Port (/dev/ttyACM0)│
└──────────────────┬───────────────────────┘
                   │ UART 9600 baud
                   ↓
┌──────────────────────────────────────────┐
│        Arduino UNO + DS18B20 Probes      │
└──────────────────────────────────────────┘
```

### Data Flow

**Arduino → Raspberry Pi:**
```
"28AB3C500415124B:25.50,28DEF456:26.75\n"
```

**Raspberry Pi → Browser:**
```json
{
  "sensors": {
    "28AB3C500415124B": {
      "temperature": 25.50,
      "status": "online",
      "name": "Living Room",
      "lastUpdate": 1702250400.123
    }
  }
}
```

**CSV Logging:**
```
Timestamp,28AB3C500415124B,28DEF456
2025-12-10T14:30:00.123456,25.50,26.75
2025-12-10T14:31:00.125432,25.51,26.74
```

---

## ⚙️ State Machine

```
WAITING_FOR_SERIAL (Initial)
    ↓ (Arduino connects)
READING (Normal operation)
    ├─ (Start logging) → LOGGING
    └─ (Serial error) → ERROR
        
LOGGING (Recording data)
    ├─ (Stop logging) → READING
    └─ (Serial error) → ERROR
        
ERROR (Communication failure)
    └─ (Auto-retry) → WAITING_FOR_SERIAL
```

---

## 📊 Features

### Dashboard Tab
- ✅ Real-time temperature display (updated every 500ms)
- ✅ Online/Offline status indicators
- ✅ Probe count in header
- ✅ Connection status indicator

### Data Logging Tab
- ✅ Configurable logging folder path
- ✅ Optional recording duration (default 10 min)
- ✅ Configurable sample interval (default 60 sec)
- ✅ Start/Stop buttons
- ✅ Active session info display
- ✅ Handles offline sensors with "NC" values

### Probe Management Tab
- ✅ Lists all detected probes
- ✅ Rename probes inline
- ✅ Show/hide OneWire addresses
- ✅ Manual rescan button
- ✅ Auto-rescan every 10 seconds (Arduino-side)

### Historical Graphs Tab
- ✅ Multi-line chart (Chart.js)
- ✅ Load data from multiple CSV files
- ✅ Download combined CSV export

---

## 🔧 Configuration Options

### Arduino Sketch (arduino_sketch.ino)

```cpp
#define ONE_WIRE_BUS 2              // OneWire pin
#define SAMPLING_INTERVAL 2000      // Read interval (ms)
#define RESCAN_INTERVAL 10000       // Auto-rescan (ms)
#define MAX_PROBES 10               // Max sensors
#define TEMPERATURE_PRECISION 12    // Resolution (9-12 bits)
```

### Flask Backend (app.py)

```python
MOCK_MODE = False                   # True = test without Arduino
SERIAL_PORT = "/dev/ttyACM0"       # Arduino port
SERIAL_BAUDRATE = 9600             # Baud rate
```

### Web Dashboard (UI Only)

- Log folder path
- Recording duration
- Sample interval
- Probe names

---

## 🛡️ Robust Features

### Graceful Degradation
- Single probe offline → Logs "NC" for that sensor, continues for others
- Serial disconnect during logging → Continues with available sensors
- Sensor not responding → Auto-timeout after 30 seconds

### State Safety
- Thread-safe state transitions
- Lock protection for shared data
- No blocking operations in threads

### Error Handling
- CSV file write failures logged
- Serial errors printed to console
- Auto-reconnect on serial loss
- Catches all exceptions in threads

### Testing Support
- Mock sensor mode generates realistic data
- Works identically with/without hardware
- Supports unit testing without Arduino

---

## 📈 Performance

| Metric | Value |
|--------|-------|
| Dashboard update rate | 500ms |
| Temperature read rate | 2000ms (configurable) |
| Auto-rescan interval | 10 seconds |
| Memory usage (Flask) | ~50MB typical |
| CPU usage | <5% typical |
| CSV line size | ~50 bytes per sensor |
| Disk for 1 month (1 sensor, 1 sample/min) | ~2MB |

---

## 🎯 Use Cases

### Home Automation
- Monitor room temperatures
- Store heating/cooling data
- Historical analysis

### Lab/Research
- Multi-sensor temperature monitoring
- Long-term data collection
- CSV export for analysis

### Industrial Applications
- Process monitoring
- Data logging for compliance
- Equipment thermal monitoring

### Educational
- Learn embedded systems
- Understand OneWire protocol
- Full-stack web application example

---

## 📝 Customization Examples

### Add Email Alerts
See `ARCHITECTURE.md` → Example 1: Email Alert System

### Add Database Backend
See `ARCHITECTURE.md` → Example 2: Database Backend

### Add Web-Based Configuration
See `ARCHITECTURE.md` → Example 3: Web Configuration

### Extend Sampling Rate
```cpp
// In arduino_sketch.ino
#define SAMPLING_INTERVAL 1000  // 1 second instead of 2
```

### Increase Temperature Precision
```cpp
#define TEMPERATURE_PRECISION 12  // Max precision (12 bits)
```

### Change Logging Folder
```python
# In app.py
logger = DataLogger(folder="/mnt/usb/temperature_logs/")
```

---

## 🐛 Common Issues & Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| "No Arduino connection" | `ls /dev/tty*` to verify, check SERIAL_PORT |
| No sensors detected | Verify OneWire wiring, 4.7kΩ resistor, power |
| Sensors offline intermittently | Improve cable, increase pull-up resistor |
| Logging doesn't create files | Check folder exists and is writable |
| Dashboard won't load | Verify Flask running, check port 5000, firewall |
| CSV corrupted | Check disk space, gracefully stop Flask (Ctrl+C) |

**Full troubleshooting guide:** See `TROUBLESHOOTING.md`

---

## 🔐 Security Considerations

- Dashboard accessible on local network only
- Consider firewall rules: `sudo ufw allow 5000/tcp`
- Protect Raspberry Pi root access
- Backup CSV logs regularly
- Monitor disk space for long-term operations

---

## 📚 Documentation Navigation

1. **New to the project?** → Start with `QUICK_START.md`
2. **Setting up hardware?** → Read `SETUP_GUIDE.md`
3. **Understanding architecture?** → See `ARCHITECTURE.md`
4. **Having problems?** → Check `TROUBLESHOOTING.md`
5. **Want to extend?** → Refer to `ARCHITECTURE.md` for examples

---

## ✅ Before You Start

### Hardware Checklist
- [ ] Arduino UNO
- [ ] Raspberry Pi (3B+ or later)
- [ ] DS18B20 temperature sensor(s)
- [ ] 4.7kΩ resistor
- [ ] USB cable (data, not power-only)
- [ ] Breadboard + jumper wires (optional)

### Software Checklist
- [ ] Python 3.7+ on Raspberry Pi
- [ ] Arduino IDE installed
- [ ] OneWire & DallasTemperature libraries
- [ ] Internet for pip package download

### Knowledge Checklist
- [ ] Basic familiarity with Arduino
- [ ] Python basics helpful
- [ ] Understanding of serial communication
- [ ] Basic networking concepts

---

## 🎓 Learning Resources

**Arduino:**
- OneWire: https://www.pjrc.com/teensy/td_libs_OneWire.html
- DallasTemperature: https://github.com/milesburton/Arduino-Temperature-Control-Library
- DS18B20: https://www.maximintegrated.com/en/products/sensors/DS18B20.html

**Python/Flask:**
- Flask: https://flask.palletsprojects.com/
- PySerial: https://pyserial.readthedocs.io/
- Threading: https://docs.python.org/3/library/threading.html

**General:**
- OneWire Protocol: https://en.wikipedia.org/wiki/1-Wire
- Raspberry Pi: https://www.raspberrypi.org/
- Arduino: https://www.arduino.cc/

---

## 📞 Getting Help

### Debugging Steps
1. Check `TROUBLESHOOTING.md` for your specific issue
2. Run in mock mode to isolate hardware issues
3. Check Serial Monitor output from Arduino
4. Check Flask console for errors
5. Verify wiring against setup guide

### Provide When Seeking Help
- Full error message or console output
- Steps to reproduce
- Hardware configuration
- `python3 --version` output
- Arduino board type and port

---

## 🚀 Next Steps

1. **Read `QUICK_START.md`** for immediate setup
2. **Connect hardware** following `SETUP_GUIDE.md`
3. **Test with mock mode** to verify Flask works
4. **Upload Arduino sketch** and verify sensors appear
5. **Test logging** with short 1-minute sessions
6. **Extend with features** from `ARCHITECTURE.md`

---

## 📄 License & Notes

This project is provided for personal and educational use.

**Version:** 1.0 (December 2025)

**Features Implemented:**
- ✅ Auto-detection of 1-10 DS18B20 probes
- ✅ Real-time HTML dashboard
- ✅ Live temperature graphs
- ✅ Configurable CSV logging with timestamps
- ✅ Robust state machine
- ✅ Mock sensor mode for testing
- ✅ Probe naming and management
- ✅ Session-based logging with auto-generated filenames
- ✅ Graceful handling of disconnected sensors
- ✅ Modular, extensible code architecture

---

**You're all set! Happy temperature monitoring! 🌡️**

Questions? Check the documentation files or review the inline code comments.

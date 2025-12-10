# File Index & Implementation Guide

## 📁 Complete File Manifest

### Application Files (Required)

```
~/temperature_monitor/
│
├── 📄 app.py (Flask Backend)
│   ├─ TemperatureSystemStateMachine - State machine with thread-safe transitions
│   ├─ SystemState / LoggingState - Enums for states
│   ├─ SerialHandler - USB/serial communication with mock support
│   ├─ SensorDataManager - In-memory sensor data storage & history
│   ├─ DataLogger - CSV file creation & session management
│   ├─ SerialReaderThread - Background thread for continuous reading
│   ├─ LoggingThread - Background thread for timed logging
│   └─ Flask Routes - 9 API endpoints + main HTML route
│   Size: ~600 lines | Status: Production-ready
│
├── 📄 arduino_sketch.ino (Arduino Firmware)
│   ├─ OneWire bus setup on Pin 2
│   ├─ scanProbes() - Auto-detect all DS18B20 sensors
│   ├─ readAndTransmitTemperatures() - Continuous data streaming
│   ├─ handleSerialCommands() - RESCAN, STATUS, PRECISION commands
│   └─ Configuration: Sampling, precision, max probes
│   Size: ~300 lines | Status: Production-ready
│
├── 📄 templates/index.html (Web Dashboard)
│   ├─ Header with status indicator
│   ├─ 4 tabs: Dashboard, Logging, Probes, Graphs
│   ├─ Real-time sensor cards with live updates
│   ├─ Logging configuration panel
│   ├─ Probe management list
│   ├─ Historical graph viewer
│   └─ Complete HTML5 + CSS + JavaScript
│   Size: ~1000 lines | Status: Production-ready
│
└── 📄 requirements.txt
    ├─ Flask==2.3.2
    ├─ pyserial==3.5
    └─ Werkzeug==2.3.7
    Status: Ready to use
```

### Documentation Files (Recommended)

```
~/temperature_monitor/
│
├── 📖 PROJECT_SUMMARY.md
│   Quick overview of entire project
│   ├─ Features checklist
│   ├─ Quick start (5 min)
│   ├─ Architecture diagram
│   ├─ Common issues & fixes
│   └─ Next steps
│   Best for: Project orientation
│
├── 📖 QUICK_START.md
│   Fast setup & testing guide
│   ├─ 5-minute setup steps
│   ├─ Testing without hardware
│   ├─ System architecture
│   ├─ Key components explanation
│   ├─ State machine diagram
│   ├─ Arduino protocol details
│   └─ CSV format reference
│   Best for: Getting running quickly
│
├── 📖 SETUP_GUIDE.md
│   Comprehensive hardware & software guide
│   ├─ Hardware requirements & wiring
│   ├─ Raspberry Pi Flask setup (step-by-step)
│   ├─ Arduino sketch upload procedure
│   ├─ Configuration parameters
│   ├─ Testing & validation
│   ├─ Common issues (detailed troubleshooting)
│   ├─ Performance notes
│   └─ Safety & best practices
│   Best for: Initial system setup
│
├── 📖 ARCHITECTURE.md
│   Deep dive into modular design
│   ├─ High-level architecture
│   ├─ Module breakdown (6 core modules)
│   ├─ Extension examples:
│   │  ├─ Email alerts system
│   │  ├─ Database backend
│   │  ├─ Web-based configuration
│   │  └─ Data validation & filtering
│   ├─ Creating new feature modules
│   ├─ Dependency injection pattern
│   └─ Recommended file organization
│   Best for: Understanding code structure & extending
│
├── 📖 TROUBLESHOOTING.md
│   Comprehensive issue resolution guide
│   ├─ Pre-launch checklist (20 items)
│   ├─ 8 common issues with step-by-step diagnosis
│   ├─ Solution paths for each issue
│   ├─ Testing checklist
│   ├─ Emergency commands
│   └─ When to seek help (with resources)
│   Best for: Debugging problems
│
└── 📖 FILE_INDEX.md (This File)
    Navigation guide for all files
```

---

## 🎯 Getting Started Path

### Path 1: Immediate Setup (30 minutes)
1. **Read:** `PROJECT_SUMMARY.md` (5 min)
2. **Read:** `QUICK_START.md` (5 min)
3. **Follow:** Hardware wiring from `SETUP_GUIDE.md` (10 min)
4. **Run:** `python3 app.py` (5 min)
5. **Test:** Dashboard at `http://localhost:5000`

### Path 2: Detailed Understanding (2-3 hours)
1. **Read:** `PROJECT_SUMMARY.md`
2. **Read:** `SETUP_GUIDE.md` completely
3. **Study:** `ARCHITECTURE.md`
4. **Review:** Code comments in `app.py` and `arduino_sketch.ino`
5. **Test:** Mock mode, then real hardware

### Path 3: Advanced Customization (variable)
1. **Complete:** Path 2 above
2. **Study:** `ARCHITECTURE.md` extension examples
3. **Implement:** Your custom modules
4. **Debug:** Using `TROUBLESHOOTING.md` as reference

---

## 🔑 Key Concepts Map

### By Topic

**Serial Communication**
- Arduino Protocol: `QUICK_START.md` → Arduino protocol section
- SerialHandler Code: `app.py` lines 90-130
- Debugging: `TROUBLESHOOTING.md` → Issue 1

**State Machine**
- Design: `QUICK_START.md` → State Machine section
- Implementation: `app.py` lines 22-72
- Diagram: `QUICK_START.md` → State Transitions

**Temperature Logging**
- CSV Format: `QUICK_START.md` → CSV File Format
- DataLogger Code: `app.py` lines 155-225
- Config: `SETUP_GUIDE.md` → Configuration section

**Web Dashboard**
- Features: `PROJECT_SUMMARY.md` → Features section
- Code: `templates/index.html` (entire file)
- Tabs: Dashboard, Logging, Probes, Graphs

**Extensions**
- Email Alerts: `ARCHITECTURE.md` → Example 1
- Database: `ARCHITECTURE.md` → Example 2
- Web Config: `ARCHITECTURE.md` → Example 3

---

## 💡 Feature Reference

| Feature | How to Use | Where Documented |
|---------|-----------|-------------------|
| **Auto-detect probes** | Plugin sensor, wait 10s | SETUP_GUIDE.md |
| **Monitor temperatures** | View Dashboard tab | index.html |
| **Rename probes** | Manage Probes tab | QUICK_START.md |
| **Start logging** | Data Logging tab | SETUP_GUIDE.md |
| **View history** | Historical Graphs tab | QUICK_START.md |
| **Change sampling rate** | Arduino config | SETUP_GUIDE.md |
| **Adjust precision** | TEMPERATURE_PRECISION | arduino_sketch.ino |
| **Test without hardware** | MOCK_MODE = True | QUICK_START.md |
| **Handle offline sensors** | "NC" in CSV | SETUP_GUIDE.md |
| **Extend system** | Create modules | ARCHITECTURE.md |

---

## 🚨 Emergency Reference

### System Won't Start
1. Check: `TROUBLESHOOTING.md` → Pre-launch checklist
2. Run: `python3 app.py` and look for errors
3. Test: Mock mode with `MOCK_MODE = True`

### No Sensors Showing
1. Verify: Wiring against `SETUP_GUIDE.md` → Wiring Diagram
2. Check: Arduino Serial Monitor output
3. Debug: `TROUBLESHOOTING.md` → Issue 2

### Logging Not Working
1. Verify: Folder exists `mkdir -p /home/pi/temperature_logs/`
2. Check: `TROUBLESHOOTING.md` → Issue 5
3. Test: Mock mode logging first

### Dashboard Not Loading
1. Check: `ps aux | grep app.py` (Flask running?)
2. Verify: `sudo lsof -i :5000` (port 5000 in use?)
3. Test: `http://localhost:5000` from Pi directly

---

## 📊 Code Statistics

| Component | Lines | Type | Complexity |
|-----------|-------|------|-----------|
| app.py | ~600 | Python | Medium |
| arduino_sketch.ino | ~300 | C++ | Low |
| index.html | ~1000 | HTML5/JS | Medium |
| Documentation | ~5000+ | Markdown | N/A |
| **Total** | **~6900** | Mixed | Production |

---

## 🔄 Typical Workflow

### Daily Operation
```
1. Open browser → http://localhost:5000
2. Check Dashboard tab for current readings
3. Verify all sensors show "ONLINE"
4. If starting logging:
   - Go to Data Logging tab
   - Set duration, interval
   - Click Start Logging
5. Can switch tabs while logging continues
6. Click Stop Logging when done
7. CSV file auto-created with timestamp
```

### Adding New Sensor
```
1. Connect new DS18B20 to Pin 2 (parallel with existing)
2. Wait 10 seconds (auto-rescan triggers)
3. New sensor appears in Dashboard & Probe Management
4. Click on Manage Probes tab
5. Rename if desired
6. Close dialog - ready to log
```

### Extending System
```
1. Study ARCHITECTURE.md → Your use case
2. Create new Python file in modules/
3. Implement your class (e.g., EmailAlertManager)
4. Import in app.py: from modules.email_alerts import EmailAlertManager
5. Integrate into SerialReaderThread or logging flow
6. Test with mock mode first
```

---

## 📋 Implementation Checklist

### Phase 1: Setup
- [ ] Read PROJECT_SUMMARY.md
- [ ] Read QUICK_START.md
- [ ] Verify hardware: Arduino, sensors, resistor, wiring
- [ ] Install Python dependencies: `pip install -r requirements.txt`

### Phase 2: Hardware
- [ ] Upload arduino_sketch.ino to Arduino UNO
- [ ] Verify Serial Monitor shows "[SCAN] Probes found"
- [ ] Check Arduino port: `ls /dev/tty*`
- [ ] Note the port name (e.g., /dev/ttyACM0)

### Phase 3: Configuration
- [ ] Edit app.py: Set SERIAL_PORT to correct port
- [ ] Create log folder: `mkdir -p /home/pi/temperature_logs/`
- [ ] Verify MOCK_MODE = False (unless testing)

### Phase 4: Testing
- [ ] Run `python3 app.py`
- [ ] Open `http://localhost:5000` in browser
- [ ] Verify sensors appear in Dashboard
- [ ] Test Logging with 1-minute duration
- [ ] Check CSV file created in log folder

### Phase 5: Validation
- [ ] Test online/offline by unplugging sensor
- [ ] Test CSV contains "NC" for offline sensors
- [ ] Test renaming probes in Manage Probes tab
- [ ] Test historical graphs with multiple sessions

### Phase 6: Optional Extensions
- [ ] Study ARCHITECTURE.md for extension ideas
- [ ] Implement email alerts / database / etc.
- [ ] Integrate with home automation
- [ ] Set up long-term logging

---

## 🔗 Cross-References

### If You Want To...

**Understand the overall project:**
→ Start with PROJECT_SUMMARY.md

**Get it running quickly:**
→ Follow QUICK_START.md

**Set up hardware correctly:**
→ Use SETUP_GUIDE.md → Hardware section

**Debug a problem:**
→ Go to TROUBLESHOOTING.md, find your issue

**Extend the system:**
→ Read ARCHITECTURE.md with examples

**Understand why something works:**
→ Check code comments in app.py / arduino_sketch.ino

**Configure sampling behavior:**
→ See SETUP_GUIDE.md → Configuration section

**Write your own module:**
→ Review ARCHITECTURE.md → Module Breakdown

**Troubleshoot serial issues:**
→ Check TROUBLESHOOTING.md → Issue 1

**Fix logging problems:**
→ Check TROUBLESHOOTING.md → Issue 5

---

## 📞 Documentation Quality Checklist

Each document has been reviewed for:
- ✅ Clarity and logical flow
- ✅ Step-by-step instructions
- ✅ Code examples with explanations
- ✅ Common pitfalls and solutions
- ✅ Cross-references to other docs
- ✅ Real terminal command examples
- ✅ Troubleshooting procedures
- ✅ Extension/customization guidance

---

## 🎓 Learning Resources in Each File

**PROJECT_SUMMARY.md**
- Overall system architecture
- Feature overview
- Performance metrics
- Use cases
- Learning resources links

**QUICK_START.md**
- System components
- Data format protocol
- State machine diagram
- API reference
- Modular structure

**SETUP_GUIDE.md**
- Hardware theory
- OneWire protocol details
- Wiring diagrams
- Pin configuration
- Resolution trade-offs

**ARCHITECTURE.md**
- Design patterns (dependency injection)
- Extension examples
- Module interfaces
- Best practices
- File organization

**TROUBLESHOOTING.md**
- Diagnosis methodology
- Systematic debugging
- Hardware diagnostics
- Emergency recovery
- Performance tuning

---

## ⚡ Quick Command Reference

```bash
# Check Arduino appears
ls /dev/tty*

# Install dependencies
pip install -r requirements.txt

# Run Flask server
python3 app.py

# Monitor Arduino raw output
cat /dev/ttyACM0

# Find Flask process
ps aux | grep python3

# Check port 5000 in use
sudo lsof -i :5000

# Create log folder
mkdir -p /home/pi/temperature_logs/

# List CSV files
ls /home/pi/temperature_logs/

# View latest CSV
tail /home/pi/temperature_logs/temperature_log_*.csv

# Test with mock
# (Edit app.py: MOCK_MODE = True, then run)
```

---

## 🏁 You're Ready!

**Next Steps:**
1. Choose your path: Immediate (30min), Detailed (2-3h), or Advanced
2. Follow the documentation in order
3. Test each step as you go
4. Refer to TROUBLESHOOTING.md if needed
5. Extend with custom modules from ARCHITECTURE.md

**All files are provided and fully documented. Happy monitoring!** 🌡️

# Troubleshooting Checklist & Common Issues

## Pre-Launch Checklist

### Hardware Setup
- [ ] Arduino UNO connected to Raspberry Pi via USB
- [ ] DS18B20 sensor(s) connected to Arduino Pin 2
- [ ] 4.7kΩ resistor connected between Pin 2 and +5V
- [ ] +5V and GND properly connected on all components
- [ ] USB cable is data cable (not power-only)
- [ ] No loose connections or damaged wires

### Software Setup
- [ ] Python 3.7+ installed on Raspberry Pi
- [ ] Flask and pyserial installed: `pip install -r requirements.txt`
- [ ] Arduino sketch uploaded to Arduino UNO
- [ ] OneWire and DallasTemperature libraries installed
- [ ] Serial Monitor shows temperature readings from Arduino
- [ ] Flask can find the Arduino port: `ls /dev/tty*`

### Configuration
- [ ] SERIAL_PORT matches Arduino (usually `/dev/ttyACM0` or `/dev/ttyUSB0`)
- [ ] SERIAL_BAUDRATE = 9600 in app.py
- [ ] MOCK_MODE = False (unless testing without hardware)
- [ ] Log folder path exists and is writable

### Network
- [ ] Raspberry Pi has network connectivity
- [ ] No firewall blocking port 5000
- [ ] Browser can reach `http://localhost:5000`

---

## Issue: "No Arduino connection" or "Waiting for serial"

### Symptom
- Dashboard shows "⚪ Disconnected" status
- Serial Monitor in Flask shows repeated connection attempts

### Diagnosis Steps

**Step 1: Verify Arduino appears on system**
```bash
ls /dev/tty*
# Should see: /dev/ttyACM0 or /dev/ttyUSB0
```

**If nothing shows:**
- [ ] Unplug USB cable, wait 5 seconds, plug back in
- [ ] Try different USB port
- [ ] Try different USB cable
- [ ] Check if Arduino needs driver (Windows users)
- [ ] Verify Arduino is powered (check LED on board)

**Step 2: Check Arduino Serial Monitor**
```bash
# Terminal 1: Start Flask
python3 app.py

# Terminal 2: Check what Arduino is sending
cat /dev/ttyACM0
# Should see lines like: 28AB3C500415124B:25.50,28DEF456:26.75

# If nothing, the Arduino sketch isn't uploading properly
```

**Step 3: Verify permissions**
```bash
# Test read permission
cat /dev/ttyACM0

# If "Permission denied":
sudo usermod -a -G dialout $USER
# Then logout and login again
```

**Step 4: Check app.py configuration**
```python
# In app.py, around line 260, verify:
SERIAL_PORT = "/dev/ttyACM0"      # Match your system
SERIAL_BAUDRATE = 9600             # Must match Arduino
MOCK_MODE = False                  # Real mode
```

**Step 5: Try mock mode to isolate hardware**
```python
# In app.py:
serial_handler = SerialHandler(use_mock=True)
# Run Flask - should work without Arduino
```

### Solution Path
1. Arduino not found → Check USB connection, drivers, permissions
2. Arduino found but no data → Check sketch upload, Serial Monitor
3. Wrong baud rate → Verify 9600 in both Arduino and Flask
4. Still failing → Enable mock mode, verify Flask works, then debug hardware

---

## Issue: Arduino detected, but no sensors shown

### Symptom
- "Connected ✓" but sensor grid shows "No sensors connected"
- Serial Monitor shows data flowing

### Diagnosis Steps

**Step 1: Check Arduino Serial Monitor directly**
```bash
# Kill Flask first
# Ctrl+C in Flask terminal

# Monitor raw Arduino output
cat /dev/ttyACM0
# Should see: 28AB3C500415124B:25.50 ...
# If nothing: Arduino sketch not uploading
```

**Step 2: Verify OneWire wiring**
```
Arduino Pin 2 ------→ DS18B20 Data (DQ)
                     ↓
                   4.7kΩ resistor
                     ↓
Arduino +5V --------→ DS18B20 +5V (VDD)
Arduino GND --------→ DS18B20 GND
```

Check:
- [ ] Pin 2 connected to DQ (not 3 or other)
- [ ] Resistor properly connected
- [ ] Power connections secure
- [ ] Sensor isn't damaged (test with different sensor)

**Step 3: Upload correct Arduino code**
1. Copy entire `arduino_sketch.ino` into Arduino IDE
2. Verify board selected: Arduino Uno
3. Verify port selected: /dev/ttyACM0 (or correct port)
4. Click Upload
5. Wait for "Done uploading"
6. Open Serial Monitor, set 9600 baud
7. Check for "[SCAN] Probe found" messages

**Step 4: Check Arduino Serial output format**
```
# Expected output:
[SCAN] Starting probe detection...
[SCAN] Probe 1 Address: 28AB3C500415124B
[SCAN] Total probes found: 1
System Ready!

28AB3C500415124B:25.50
28AB3C500415124B:25.51
...

# If different format → Wrong sketch uploaded
```

### Solution Path
1. No Arduino output → Upload sketch again
2. Arduino output wrong format → Check `arduino_sketch.ino` line 120
3. No probe detection → Check OneWire wiring, 4.7kΩ resistor, sensor power
4. Probe found but no temperature → Sensor may be bad, test with different one

---

## Issue: Temperature readings incorrect or flickering

### Symptom
- Dashboard shows "25.5°C" then "NC" then "25.6°C"
- Values fluctuate wildly
- Some sensors show "NC" intermittently

### Diagnosis Steps

**Step 1: Check OneWire signal integrity**
```bash
# Measure voltage on DQ line with multimeter
# Should be 5V when idle, can be 0V during communication
# If floating around 2.5V: pull-up resistor issue

# Check resistance between DQ and +5V:
# Should be ~4.7kΩ (4700 ohms)
```

**Step 2: Improve cable quality**
- [ ] Shorten cable length (<1 meter if possible)
- [ ] Use shielded twisted pair cable
- [ ] Connect shield to GND at one end only
- [ ] Keep away from high-current wires, power supplies

**Step 3: Increase pull-up resistor**
- Default: 4.7kΩ
- For longer runs: try 6.8kΩ or 10kΩ
- Change resistor and test

**Step 4: Reduce sampling rate**
```cpp
// In arduino_sketch.ino:
#define SAMPLING_INTERVAL 3000  // Changed from 2000
```

**Step 5: Increase temperature resolution**
```cpp
// In arduino_sketch.ino:
#define TEMPERATURE_PRECISION 12  // Already maximum
// Increase sampling interval to give more conversion time
#define SAMPLING_INTERVAL 1000  // 750ms conversion + margin
```

**Step 6: Check sensor placement**
- [ ] Not touching hot surfaces
- [ ] Shielded from direct sunlight
- [ ] Immersed properly if in liquid
- [ ] Stable temperature source for testing

### Solution Path
1. Flickering on/offline → Check voltage, cable quality, shield it
2. Wild temperature swings → Check sensor stability, reduce sample rate
3. Systematic offset (always 1°C high) → Sensor calibration issue
4. Intermittent "NC" on multiple sensors → Pull-up resistor not strong enough

---

## Issue: Logging starts but no CSV file created

### Symptom
- Click "Start Logging" → Shows "Logging active..."
- Stop logging → Status changes but no file appears
- Dashboard shows logging info but folder is empty

### Diagnosis Steps

**Step 1: Check folder exists and is writable**
```bash
# Create folder
mkdir -p /home/pi/temperature_logs/

# Test write permission
touch /home/pi/temperature_logs/test.txt
# If fails: permission issue
rm /home/pi/temperature_logs/test.txt

# Fix permissions
chmod 777 /home/pi/temperature_logs/
```

**Step 2: Check Flask logs for errors**
```bash
# Kill Flask and restart with verbose output
python3 -u app.py 2>&1 | tee flask.log

# Look for [LOGGER] error messages
```

**Step 3: Verify logging folder path in dashboard**
- [ ] Path in UI matches actual folder
- [ ] Path has trailing slash: `/home/pi/temperature_logs/`
- [ ] No typos in path

**Step 4: Check disk space**
```bash
df -h
# If /home partition is 100% full: delete old logs
rm /home/pi/temperature_logs/*.csv
```

**Step 5: Verify sensors are online**
- [ ] Logging only works if sensors connected
- [ ] At least one sensor showing "ONLINE"
- [ ] Sensor readings update on dashboard

### Solution Path
1. Folder doesn't exist → Create with `mkdir -p`
2. Permission denied → Run Flask with `sudo` or fix permissions
3. File created but empty → Wait longer, sensors might be offline
4. Flask logs show errors → Check error message and app.py line numbers

---

## Issue: Dashboard won't load in browser

### Symptom
- `http://localhost:5000` shows "Connection refused"
- Browser says "Can't reach this page"
- From another computer: `http://pi-ip:5000` fails

### Diagnosis Steps

**Step 1: Verify Flask is running**
```bash
# Check if Flask process exists
ps aux | grep flask
# Should show: python3 app.py

# If not running:
python3 app.py
# Check for startup errors
```

**Step 2: Check if port 5000 is in use**
```bash
# See what's listening on port 5000
sudo lsof -i :5000
# Should show: python3 app.py

# If something else: stop it and change Flask port in app.py
# app.run(port=5001)
```

**Step 3: Verify Flask bound to all interfaces**
```python
# In app.py, last line should be:
app.run(host='0.0.0.0', port=5000, debug=False)
# host='0.0.0.0' = accessible from any IP
# If host='127.0.0.1' = local only
```

**Step 4: Check firewall**
```bash
# Check firewall status
sudo ufw status

# If active, allow port 5000
sudo ufw allow 5000/tcp

# Reload
sudo ufw reload
```

**Step 5: Get Raspberry Pi IP address**
```bash
hostname -I
# Use this IP to access from other computer
# Example: http://192.168.1.100:5000
```

### Solution Path
1. Flask not running → Start with `python3 app.py`
2. Port in use → Kill other process or change port in app.py
3. Can't access from other computer → Check firewall, binding
4. Port 5000 blocked by ISP → Use port 8080 or 3000 instead

---

## Issue: CSV file corrupt or won't open

### Symptom
- CSV file created but empty
- Excel/LibreOffice can't open file
- File size 0 bytes
- Timestamps missing

### Diagnosis Steps

**Step 1: Check file content**
```bash
cat /home/pi/temperature_logs/temperature_log_*.csv
# Should show:
# Timestamp,28AB3C500415124B
# 2025-12-10T14:30:00.123456,25.50
```

**Step 2: Verify data was actually logged**
- [ ] Check that logging really happened
- [ ] Look at multiple CSV files
- [ ] Check timestamps span expected duration

**Step 3: Check for sensor status during logging**
- If all sensors "NC" → No data to log
- If offline during logging → Will show "NC" in CSV

**Step 4: Verify CSV format**
```bash
# Check first few lines
head -5 /home/pi/temperature_logs/temperature_log_*.csv

# Should have:
# Line 1: Timestamp,<sensor_ids>
# Line 2+: ISO timestamp,temperature,temperature,...
```

**Step 5: Check disk I/O errors**
```bash
# Check for disk errors
dmesg | grep -i error | tail -20
# Look for I/O or write errors
```

### Solution Path
1. File empty → Logging didn't actually run, check Flask logs
2. Corrupted CSV → Disk space issue, fix and re-log
3. Wrong format → Check DataLogger.log_reading() in app.py
4. Truncated → Kill Flask gracefully (Ctrl+C) to flush files

---

## Issue: Performance degradation over time

### Symptom
- Dashboard becomes slow after hours of operation
- High CPU usage
- Memory usage increases

### Diagnosis Steps

**Step 1: Check system resources**
```bash
# Monitor in real-time
top
# Look for: %CPU, %MEM for python3 app.py

# Check disk space
df -h
# If full: delete old logs
```

**Step 2: Check Flask memory usage**
```bash
# Run with memory profiling
python3 -m memory_profiler app.py
# Identify memory leaks
```

**Step 3: Review sensor history size**
```python
# In app.py, SensorDataManager might store all history in RAM
# Add periodic cleanup:
def cleanup_old_history(self, hours=24):
    current_time = time.time()
    for sensor_id in self.history:
        self.history[sensor_id] = [
            h for h in self.history[sensor_id]
            if current_time - h['timestamp'] < hours * 3600
        ]
```

**Step 4: Check log file size**
```bash
du -sh /home/pi/temperature_logs/
# If very large: rotate old files
find /home/pi/temperature_logs/ -name "*.csv" -mtime +30 -delete
```

**Step 5: Reduce sampling rate**
```cpp
// In arduino_sketch.ino:
#define SAMPLING_INTERVAL 5000  // Slower sampling
```

### Solution Path
1. Disk full → Clean up old logs
2. Memory leak → Add history cleanup to SensorDataManager
3. High CPU → Reduce sampling rate or disable graph updates
4. Slow dashboard → Use pagination for historical data

---

## Testing Checklist

### Test in Mock Mode
```bash
# Modify app.py:
serial_handler = SerialHandler(use_mock=True)

# Run and verify:
python3 app.py
# Dashboard shows random sensor data
# Logging works without Arduino
```

### Test with Single Sensor
- [ ] Connect only one DS18B20
- [ ] Verify it appears on dashboard
- [ ] Test logging with one sensor
- [ ] Test renaming probe

### Test with Multiple Sensors
- [ ] Connect 2-3 sensors
- [ ] Verify all appear
- [ ] Verify rescan finds new sensors
- [ ] Test that removing sensor shows "NC" after 30s

### Test Logging
- [ ] Start logging with 1 minute duration, 10 second interval
- [ ] Check CSV file created
- [ ] Verify timestamps and values
- [ ] Stop logging early and check file
- [ ] Verify new file for next session

### Test Recovery
- [ ] Unplug Arduino mid-logging
- [ ] Verify CSV shows "NC" entries
- [ ] Plug back in and verify resumes
- [ ] Stop logging normally

### Test Edge Cases
- [ ] Very high temperature (>100°C): verify displays correctly
- [ ] Very low temperature (<0°C): verify negative sign
- [ ] Rapidly changing temperature: verify no glitches
- [ ] Very long probe names: verify UI doesn't break

---

## Emergency Commands

### Kill Flask Server Gracefully
```bash
# Find Flask process
ps aux | grep python3

# Kill by PID
kill -TERM <PID>

# If stuck, force kill
kill -9 <PID>
```

### Reset Serial Connection
```bash
# Disconnect and reconnect Arduino
sudo modprobe -r usbserial
sudo modprobe usbserial

# Or simply power cycle Arduino
```

### Clear Corrupted CSV
```bash
# Backup before deleting
cp /home/pi/temperature_logs/*.csv /home/pi/backup/

# Delete all logs
rm /home/pi/temperature_logs/*.csv

# Restart Flask
```

### Extract Data From Corrupt File
```bash
# If CSV is partially corrupt
tail -n +1 /home/pi/temperature_logs/corrupted.csv | head -n -5 > fixed.csv
# Removes last 5 lines which might be corrupt
```

### Monitor Serial in Real-Time
```bash
# Install screen (optional)
sudo apt-get install screen

# Monitor serial port
screen /dev/ttyACM0 9600

# Exit: Ctrl+A, then :quit
```

---

## When to Seek Help

**Provide:**
- [ ] Flask console output (all errors)
- [ ] Arduino Serial Monitor output
- [ ] System info: `uname -a`
- [ ] Python version: `python3 --version`
- [ ] Exact steps to reproduce

**Resources:**
- Arduino: https://forum.arduino.cc/
- Flask: https://flask.palletsprojects.com/
- DS18B20: https://www.maximintegrated.com/en/products/sensors/DS18B20.html
- OneWire: https://www.pjrc.com/teensy/td_libs_OneWire.html

---

**Stay calm, test systematically, isolate the problem layer by layer!**

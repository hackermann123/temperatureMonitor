# Setup Guide - Temperature Monitoring System

Complete step-by-step guide to deploy the Temperature Monitoring System on a Raspberry Pi.

---

## Prerequisites

- **Hardware**: Raspberry Pi 3B+, 4, or 5 (or Linux system with Python 3.7+)
- **Arduino**: Uno, Mega, or compatible board
- **Sensors**: DS18B20 OneWire temperature sensors
- **Network**: WiFi or Ethernet connection
- **Knowledge**: Basic terminal commands, electronics fundamentals

---

## Part 1: Hardware Setup

### 1.1 Physical Wiring

**OneWire Temperature Sensor (DS18B20) Pinout:**
```
    ┌─────┐
    │ ███ │  Pin 1 (Left): GND
    │ ███ │  Pin 2 (Middle): DQ (Data)
    │ ███ │  Pin 3 (Right): VCC (+5V)
    └─────┘
```

**Arduino Connection:**
```
DS18B20 Pin 1 (GND)    → Arduino GND
DS18B20 Pin 2 (DQ)     → Arduino Digital Pin 2 + 4.7kΩ resistor to 5V
DS18B20 Pin 3 (VCC)    → Arduino 5V

Resistor: Connect 4.7kΩ resistor between Pin 2 and 5V
```

**Wiring Diagram (Text):**
```
┌─────────────────────────────────────────┐
│          Arduino Board                  │
│  ┌──────────────────────────────────┐   │
│  │ GND │ ... │ D2 │ ... │ 5V  │    │   │
│  └──────┼────────────────┼───────────┘   │
│         │                │               │
│         │                ├─── 4.7kΩ ───┤
│         │                │              │
│         │         ┌─────┐│              │
│         └────────►│Pin2 │├──────────────┤
│                   │Pin1 │
│         ┌────────►│Pin3 │
│         │         └─────┘
│        GND            ↑
│                       5V
└─────────────────────────────────────────┘
```

### 1.2 Program Arduino

1. Download Arduino IDE from [arduino.cc](https://www.arduino.cc/en/software)
2. Open sketch (or create new with code below)
3. Select Board: Tools → Board → Arduino Uno
4. Select Port: Tools → Port → /dev/ttyACM0
5. Upload: Sketch → Upload

**Arduino Sketch (temperature_reader.ino):**

```cpp
#include <OneWire.h>

#define ONE_WIRE_BUS 2

OneWire ds(ONE_WIRE_BUS);

void setup(void) {
  Serial.begin(9600);
  delay(100);
}

void loop(void) {
  byte addr[8];
  byte data[12];
  
  if (ds.search(addr)) {
    ds.reset();
    ds.select(addr);
    ds.write(0x44, 1);
    
    delay(1000);
    
    ds.reset();
    ds.select(addr);
    ds.write(0xBE);
    
    for (int i = 0; i < 9; i++) {
      data[i] = ds.read();
    }
    
    int16_t raw = (data[1] << 8) | data[0];
    byte cfg = (data[4] & 0x60);
    
    if (cfg == 0x00) raw = raw & ~7;
    else if (cfg == 0x20) raw = raw & ~3;
    else if (cfg == 0x40) raw = raw & ~1;
    
    float celsius = (float)raw / 16.0;
    
    Serial.print("28");
    for (byte i = 0; i < 8; i++) {
      if (addr[i] < 16) Serial.print('0');
      Serial.print(addr[i], HEX);
    }
    Serial.print(":");
    Serial.print(celsius, 2);
    Serial.println();
    
  } else {
    ds.reset_search();
  }
  
  delay(1000);
}
```

**Verify in Serial Monitor:**
- Tools → Serial Monitor
- Set baud rate to 9600
- Should see: `281234567890ab:25.50`

---

## Part 2: Raspberry Pi Setup

### 2.1 Initial Configuration

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and dependencies
sudo apt-get install -y python3 python3-pip python3-venv

# Check Python version
python3 --version  # Should be 3.7+
```

### 2.2 Create Project Directory

```bash
# Create project folder
mkdir -p ~/temperature-monitoring-system
cd ~/temperature-monitoring-system

# Create subdirectories
mkdir -p templates
mkdir -p /home/pi/temperature_logs

# Set permissions
chmod 755 /home/pi/temperature_logs
```

### 2.3 Set Up Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 2.4 Install Python Packages

```bash
# Install required packages
pip install flask pyserial

# Verify installation
python3 -c "import flask, serial; print('OK')"
```

---

## Part 3: Deploy Application

### 3.1 Copy Application Files

```bash
cd ~/temperature-monitoring-system

# Copy backend
# (paste app.py content into app.py)
nano app.py

# Copy frontend template
# (paste index.html content into templates/index.html)
nano templates/index.html

# Make executable
chmod +x app.py
```

### 3.2 Configure Serial Port

Identify your Arduino's serial port:

```bash
# List all USB/serial devices
ls /dev/tty*

# Usually appears as:
# /dev/ttyACM0    (most common)
# /dev/ttyUSB0
# /dev/ttyUSB1
```

Edit `app.py` and set correct port:

```python
SERIAL_PORT = "/dev/ttyACM0"      # Change if needed
SERIAL_BAUDRATE = 9600
LOG_FOLDER = "/home/pi/temperature_logs/"
```

### 3.3 Test Run

```bash
# Activate virtual environment
source venv/bin/activate

# Run application
python3 app.py

# Expected output:
# [STARTUP] Initializing Temperature Monitoring System
# [STARTUP] Log folder: /home/pi/temperature_logs/
# [STARTUP] Serial reader thread started
# [STARTUP] System ready
#  * Running on http://0.0.0.0:5000
```

Open browser: **http://localhost:5000**

Stop with: **Ctrl+C**

---

## Part 4: Enable Auto-Start

### 4.1 Create Systemd Service

```bash
# Create service file
sudo nano /etc/systemd/system/tempmon.service
```

**Paste this content:**

```ini
[Unit]
Description=Temperature Monitoring System
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/temperature-monitoring-system
Environment="PATH=/home/pi/temperature-monitoring-system/venv/bin"
ExecStart=/home/pi/temperature-monitoring-system/venv/bin/python3 /home/pi/temperature-monitoring-system/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 4.2 Enable Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start
sudo systemctl enable tempmon

# Start service
sudo systemctl start tempmon

# Check status
sudo systemctl status tempmon

# View logs
sudo journalctl -u tempmon -f
```

### 4.3 Verify Auto-Start

```bash
# Reboot and verify service starts
sudo reboot

# After reboot, check:
sudo systemctl status tempmon

# Or visit: http://localhost:5000
```

---

## Part 5: Network Configuration

### 5.1 Find Raspberry Pi IP Address

```bash
# Get IP address
hostname -I

# Or more detailed:
ip addr show | grep "inet "

# Output example: 192.168.1.100
```

### 5.2 Access from Another Computer

Once you have the IP address:

```
http://192.168.1.100:5000
```

Replace `192.168.1.100` with your actual IP.

### 5.3 Enable Remote Access (Optional)

For accessing outside your local network, use port forwarding or ngrok:

**Using ngrok (easy for testing):**

```bash
# Download and setup ngrok
cd ~
curl -s https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-stable-linux-arm.tgz | tar xz

# Run tunnel
./ngrok http 5000

# Will show public URL like: https://abc123.ngrok.io
```

---

## Part 6: Troubleshooting

### Arduino Not Detected

```bash
# Check USB connection
lsusb

# Look for "FT232R UART" or "CH340" (Arduino devices)

# List serial ports
ls -la /dev/tty*

# Try different ports in app.py:
# /dev/ttyACM0
# /dev/ttyUSB0
# /dev/ttyUSB1
```

### Permission Denied on Serial Port

```bash
# Add pi user to dialout group
sudo usermod -a -G dialout pi

# Restart service
sudo systemctl restart tempmon

# May need to reboot for group change to take effect
sudo reboot
```

### Port 5000 Already in Use

```bash
# Find process using port
sudo lsof -i :5000

# Kill the process (get PID from above)
sudo kill -9 <PID>

# Or change port in app.py:
app.run(host='0.0.0.0', port=5001)
```

### No Sensors Detected

1. **Check wiring** - Verify all connections
2. **Test Arduino** - Open Arduino IDE Serial Monitor, should see readings
3. **Check serial port** - Ensure correct port in app.py
4. **Enable mock mode** - Click 🎮 button in dashboard to test without Arduino

### Log Files Not Creating

```bash
# Check folder exists and has correct permissions
ls -la /home/pi/temperature_logs/

# Should show: drwxr-xr-x

# Fix if needed:
sudo chown pi:pi /home/pi/temperature_logs/
chmod 755 /home/pi/temperature_logs/

# Restart service
sudo systemctl restart tempmon
```

### Service Not Starting

```bash
# Check logs for errors
sudo journalctl -u tempmon -n 50

# Check syntax errors in Python files
python3 -m py_compile app.py

# Try running manually to see errors
source venv/bin/activate
python3 app.py
```

---

## Part 7: Maintenance

### Regular Tasks

**Weekly:**
```bash
# Verify service is running
sudo systemctl status tempmon

# Check disk space for logs
df -h /home/pi/temperature_logs/
```

**Monthly:**
```bash
# Check for Python updates
pip list --outdated

# Update packages
pip install --upgrade flask pyserial
```

### Backup Logs

```bash
# Backup log folder
tar -czf ~/temperature_logs_backup_$(date +%Y%m%d).tar.gz /home/pi/temperature_logs/

# Store on USB drive or cloud storage
cp ~/temperature_logs_backup_*.tar.gz /mnt/usb/
```

### Monitor System Resources

```bash
# Watch CPU and memory usage
watch -n 1 'ps aux | grep python3'

# Check temperature
/opt/vc/bin/vcgencmd measure_temp

# Monitor disk usage
du -sh /home/pi/temperature_logs/
```

---

## Part 8: Performance Tips

### Optimize Database Size

For long-running deployments, logs can grow large:

```bash
# Check log folder size
du -sh /home/pi/temperature_logs/

# Archive old logs
find /home/pi/temperature_logs/ -name "*.csv" -mtime +30 -exec gzip {} \;

# Automatically in cron (monthly):
sudo crontab -e
# Add: 0 0 1 * * find /home/pi/temperature_logs/ -name "*.csv" -mtime +30 -exec gzip {} \;
```

### Network Optimization

For stable WiFi:

```bash
# Check WiFi signal strength
iwconfig wlan0 | grep Signal

# Improve connectivity
# 1. Move router closer
# 2. Reduce obstacles (metal, water)
# 3. Use 5GHz band if available
# 4. Consider wired Ethernet for stability
```

---

## Completed Setup Checklist

- [ ] Arduino programmed with OneWire sketch
- [ ] DS18B20 sensors wired correctly
- [ ] Arduino connected via USB to Raspberry Pi
- [ ] Raspberry Pi updated and Python installed
- [ ] Project directory created
- [ ] Python packages installed
- [ ] app.py deployed and configured
- [ ] index.html deployed in templates/
- [ ] Serial port identified and configured
- [ ] Application tested manually
- [ ] Systemd service created and enabled
- [ ] Service tested with `systemctl status tempmon`
- [ ] Dashboard accessible at http://localhost:5000
- [ ] Mock mode tested with 🎮 button
- [ ] Data logging tested and CSV created
- [ ] Auto-start verified after reboot

---

## Next Steps

1. **Customize Probe Names**: In "Manage Probes" tab, rename sensors for clarity
2. **Set Up Logging Schedule**: In "Data Logging" tab, configure intervals
3. **Configure Remote Access**: Set up port forwarding or ngrok
4. **Create Backups**: Implement automated log backups
5. **Monitor Alerts**: Set up email notifications for temperature thresholds (future enhancement)

---

## Support Resources

- **Arduino Docs**: https://www.arduino.cc/reference/
- **OneWire Library**: https://www.arduino.cc/en/Reference/OneWire
- **Raspberry Pi Docs**: https://www.raspberrypi.org/documentation/
- **Flask Docs**: https://flask.palletsprojects.com/
- **Chart.js Docs**: https://www.chartjs.org/docs/latest/

---

**Last Updated:** December 10, 2025  
**Tested Configuration:** Raspberry Pi 4, Arduino Uno, Python 3.9

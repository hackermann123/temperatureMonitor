# Quick Reference Guide - Temperature Monitoring System

Fast lookup for commands, endpoints, and common tasks.

---

## Installation Quick Commands

```bash
# Clone and setup
git clone https://github.com/yourusername/temperature-monitoring-system.git
cd temperature-monitoring-system

# Python setup
python3 -m venv venv
source venv/bin/activate
pip install flask pyserial

# Create directories
mkdir -p templates /home/pi/temperature_logs

# Copy files
cp app.py .
cp templates/index.html .

# Run
python3 app.py
# Open: http://localhost:5000
```

---

## Dashboard Controls

| Button | Action | Location |
|--------|--------|----------|
| 🎮 Enable Mock Mode | Simulate sensors for testing | Dashboard → Current Status |
| ⏹️ Disable Mock Mode | Switch back to Arduino | Dashboard → Current Status |
| 🔄 Rescan Probes | Find new sensors on OneWire bus | Manage Probes → Connected Probes |
| 📥 Download CSV | Export all logged data | Historical Graphs → Download CSV |

---

## API Endpoints Quick Reference

```bash
# Get all sensors (current readings)
curl http://localhost:5000/api/sensors

# Start logging
curl -X POST http://localhost:5000/api/logging/start \
  -H "Content-Type: application/json" \
  -d '{"duration": 600, "interval": 60}'

# Stop logging
curl -X POST http://localhost:5000/api/logging/stop

# Get graph data
curl http://localhost:5000/api/graphs/data

# Rename sensor
curl -X POST http://localhost:5000/api/probes/rename \
  -H "Content-Type: application/json" \
  -d '{"sensor_id": "281234567890ab", "name": "Kitchen"}'

# Enable mock mode
curl -X POST http://localhost:5000/api/mock/enable

# Disable mock mode
curl -X POST http://localhost:5000/api/mock/disable

# Get system status
curl http://localhost:5000/api/system/status
```

---

## File Locations

| File | Path | Purpose |
|------|------|---------|
| Backend | `~/temperature-monitoring-system/app.py` | Flask server |
| Frontend | `~/temperature-monitoring-system/templates/index.html` | Web dashboard |
| Logs | `/home/pi/temperature_logs/*.csv` | Temperature data |
| Service | `/etc/systemd/system/tempmon.service` | Auto-start config |
| Arduino Sketch | `/home/pi/temperature_reader.ino` | Sensor firmware |

---

## Configuration Quick Edit

**Serial Port** (app.py, line ~500):
```python
SERIAL_PORT = "/dev/ttyACM0"      # Change if needed
SERIAL_BAUDRATE = 9600             # Don't change
LOG_FOLDER = "/home/pi/temperature_logs/"
```

**Flask Settings** (app.py, bottom):
```python
app.run(host='0.0.0.0', port=5000, debug=False)
```

---

## System Service Commands

```bash
# Check if running
sudo systemctl status tempmon

# Start service
sudo systemctl start tempmon

# Stop service
sudo systemctl stop tempmon

# Restart service
sudo systemctl restart tempmon

# View logs
sudo journalctl -u tempmon -f

# Enable auto-start
sudo systemctl enable tempmon

# Disable auto-start
sudo systemctl disable tempmon
```

---

## Troubleshooting Shortcuts

| Problem | Quick Fix |
|---------|-----------|
| No sensors in dashboard | Click 🎮 Enable Mock Mode to test |
| Arduino not detected | Check `ls /dev/ttyACM*` and update app.py |
| Port 5000 in use | `sudo lsof -i :5000` then `sudo kill -9 <PID>` |
| Permission denied | `sudo usermod -a -G dialout pi` then reboot |
| Service won't start | `sudo journalctl -u tempmon -n 50` to see error |
| Graphs not loading | Hard refresh browser: `Ctrl+Shift+R` |
| CSV files not created | `chmod 755 /home/pi/temperature_logs/` |

---

## Data Format Reference

**CSV Structure:**
```
Timestamp,Sensor_ID_1,Sensor_ID_2
2025-12-10T19:00:00.123456,25.50,26.30
2025-12-10T19:01:00.234567,25.52,26.28
```

**Sensor ID Format:**
```
28 + 12 hex characters = 16 char total
Example: 281234567890ab
```

**API Response Format:**
```json
{
  "sensors": {
    "281234567890ab": {
      "name": "Probe Name",
      "temperature": 25.50,
      "status": "online",
      "lastUpdate": 1702253800.123
    }
  }
}
```

---

## Hardware Wiring Cheat Sheet

```
DS18B20 Sensor → Arduino
Pin 1 (GND)    → GND
Pin 2 (DQ)     → Digital Pin 2 + 4.7kΩ resistor to 5V
Pin 3 (VCC)    → 5V
```

**Verify Arduino works:**
```cpp
// Minimal test - upload to Arduino
void setup() {
  Serial.begin(9600);
}

void loop() {
  Serial.println("281234567890ab:25.50");
  delay(1000);
}
```

**Check in Serial Monitor:**
- Set baud rate to 9600
- Should see: `281234567890ab:25.50`

---

## Performance Benchmarks

| Metric | Value |
|--------|-------|
| Dashboard refresh rate | 2 seconds |
| Sensor reading interval | ~1 second |
| CSV write frequency | Configurable (default 60s) |
| Memory usage | ~50 MB baseline |
| CPU usage | 2-5% idle, 10% logging |
| Max simultaneous sensors | 10-15 |
| Max data points per graph | 10,000+ |

---

## Default Credentials & Ports

| Service | Default | Notes |
|---------|---------|-------|
| Dashboard | `http://localhost:5000` | No auth required |
| SSH | `pi@raspberrypi.local` | Default Raspberry Pi user |
| Serial Port | `/dev/ttyACM0` | May vary |
| Serial Baud | `9600` | Fixed (don't change) |

---

## Environment Variables

Currently not used, but can add:

```bash
# Example future additions
export TEMP_LOG_FOLDER="/mnt/storage/logs"
export TEMP_SERIAL_PORT="/dev/ttyUSB0"
export TEMP_API_KEY="your-key-here"
```

---

## Common Logging Configurations

**Short-term monitoring (1 hour):**
```json
{"duration": 3600, "interval": 10}
```

**Full day monitoring:**
```json
{"duration": 86400, "interval": 60}
```

**Continuous monitoring (no limit):**
```json
{"duration": null, "interval": 60}
```

**High frequency (1 per second):**
```json
{"duration": 600, "interval": 1}
```

---

## Backup Commands

```bash
# Backup logs
tar -czf ~/logs_backup_$(date +%Y%m%d).tar.gz /home/pi/temperature_logs/

# Backup entire project
tar -czf ~/project_backup_$(date +%Y%m%d).tar.gz ~/temperature-monitoring-system/

# Restore
tar -xzf ~/logs_backup_*.tar.gz -C /

# Upload to cloud (example: Dropbox)
rclone copy /home/pi/temperature_logs dropbox:temperature_logs/
```

---

## Testing Scenarios

**Test 1: Mock Mode (5 min)**
1. Click 🎮 Enable Mock Mode
2. Verify sensors appear
3. Start logging for 60 seconds
4. View data in Graphs tab
5. Click ⏹️ Disable Mock Mode

**Test 2: Real Hardware (15 min)**
1. Wire Arduino + sensors
2. Upload Arduino sketch
3. Connect USB to Raspberry Pi
4. Update serial port in app.py
5. Restart Flask
6. Verify sensors in dashboard

**Test 3: Data Logging (30 min)**
1. Start logging with 60s interval
2. Wait 5 minutes
3. Stop logging
4. View CSV file: `ls /home/pi/temperature_logs/`
5. Select in Graphs tab
6. Verify chart displays data

---

## Performance Optimization Tips

**Reduce Load:**
```python
# In app.py, increase refresh interval
setInterval(updateDashboard, 5000);  # 5 seconds instead of 2
```

**Reduce Memory:**
```bash
# Archive old logs monthly
find /home/pi/temperature_logs/ -name "*.csv" -mtime +30 -exec gzip {} \;
```

**Improve Response Time:**
```python
# Use nginx as reverse proxy (caching)
# Add @app.cache.cached(timeout=5) to endpoints
```

---

## Security Checklist

- [ ] Change SSH password: `passwd`
- [ ] Disable SSH password login (key-based auth)
- [ ] Use HTTPS (Let's Encrypt SSL)
- [ ] Add authentication to Flask routes
- [ ] Use reverse proxy (nginx with rate limiting)
- [ ] Firewall (UFW): `sudo ufw allow 5000`
- [ ] Backup encryption: `gpg --encrypt backup.tar.gz`
- [ ] Monitor logs: `sudo tail -f /var/log/syslog`

---

## Git Cheat Sheet

```bash
# Clone
git clone https://github.com/yourusername/temperature-monitoring-system.git

# Commit changes
git add .
git commit -m "Description of change"
git push

# Check status
git status

# View history
git log --oneline

# Discard changes
git checkout -- filename

# Create branch for feature
git checkout -b feature/my-feature
git push -u origin feature/my-feature
```

---

## Remote Access Quick Setup

**SSH Tunnel (secure):**
```bash
ssh -L 5000:localhost:5000 pi@192.168.1.100
# Then access: http://localhost:5000
```

**Port Forwarding (router):**
- Login to router admin
- Add port forward: `5000 → 192.168.1.100:5000`
- Access: `http://your-public-ip:5000`

**ngrok Tunnel (temporary testing):**
```bash
./ngrok http 5000
# Public URL: https://abc123.ngrok.io
```

---

## Browser Developer Tools

**Access (F12):**
- **Console** - See JavaScript errors
- **Network** - Monitor API calls
- **Storage** - Clear cookies/cache
- **Performance** - Check load times

**Common fixes:**
```javascript
// Clear localStorage
localStorage.clear();

// Reload (hard refresh)
// Ctrl+Shift+R (Windows/Linux)
// Cmd+Shift+R (Mac)
```

---

## Python Virtual Environment

```bash
# Create
python3 -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install packages
pip install -r requirements.txt

# Deactivate
deactivate

# Update packages
pip install --upgrade flask pyserial
```

---

## Requirements.txt Template

```
Flask==2.3.2
pyserial==3.5
python-dateutil==2.8.2
```

---

## Emergency Procedures

**App crashed / won't start:**
```bash
# Check for Python syntax errors
python3 -m py_compile app.py

# Run manually to see errors
python3 app.py

# Check logs if using systemd
sudo journalctl -u tempmon -n 100
```

**Raspberry Pi won't boot:**
```bash
# SSH in from another device
ssh pi@raspberrypi.local

# Check disk space
df -h

# Check for filesystem errors
sudo fsck -f /dev/mmcblk0p2  # (with warnings!)
```

**Complete reset needed:**
```bash
# Backup important files
tar -czf ~/backup.tar.gz ~/temperature-monitoring-system/

# Remove app
rm -rf ~/temperature-monitoring-system/

# Reinstall from scratch
# Follow SETUP_GUIDE.md
```

---

## Version Checking

```bash
# Python version
python3 --version

# Flask version
python3 -c "import flask; print(flask.__version__)"

# Check all packages
pip list

# Upgrade outdated packages
pip list --outdated
pip install --upgrade flask
```

---

## Contact & Support

- **Issues**: GitHub Issues tab
- **Documentation**: README.md
- **Setup Help**: SETUP_GUIDE.md
- **API Reference**: API_DOCS.md
- **Architecture**: PROJECT_OVERVIEW.md

---

**Last Updated**: December 10, 2025  
**Quick Reference Version**: 1.0  
**Status**: ✅ Complete

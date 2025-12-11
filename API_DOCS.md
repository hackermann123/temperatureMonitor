# API Documentation - Temperature Monitoring System

Complete reference for all REST API endpoints available in the Temperature Monitoring System.

---

## Base URL

```
http://localhost:5000
```

Or remote:
```
http://<raspberry-pi-ip>:5000
```

---

## Endpoints Overview

| Category | Endpoint | Method | Purpose |
|----------|----------|--------|---------|
| **Sensors** | `/api/sensors` | GET | Get all sensor readings |
| **Logging** | `/api/logging/start` | POST | Start data logging session |
| | `/api/logging/stop` | POST | Stop data logging session |
| **Graphs** | `/api/graphs/data` | GET | Get historical CSV data |
| | `/api/graphs/download` | GET | Download combined CSV |
| **Probes** | `/api/probes/rescan` | POST | Trigger sensor rescan |
| | `/api/probes/rename` | POST | Rename a sensor |
| **Mock** | `/api/mock/enable` | POST | Enable mock mode |
| | `/api/mock/disable` | POST | Disable mock mode |
| **System** | `/api/system/status` | GET | Get system status |

---

## Sensor Endpoints

### GET /api/sensors

**Description:** Get all currently connected sensors and their readings

**Request:**
```bash
curl http://localhost:5000/api/sensors
```

**Response (200 OK):**
```json
{
  "sensors": {
    "281234567890ab": {
      "name": "Probe 28123456",
      "temperature": 25.50,
      "status": "online",
      "lastUpdate": 1702253800.123
    },
    "289876543210cd": {
      "name": "Probe 28987654",
      "temperature": 26.30,
      "status": "online",
      "lastUpdate": 1702253800.245
    }
  }
}
```

**Response Fields:**
- `sensors` (object): Map of sensor ID to sensor data
  - `name` (string): Display name of sensor
  - `temperature` (float): Current temperature in Celsius
  - `status` (string): "online" or "offline"
  - `lastUpdate` (float): Unix timestamp of last reading

**Status Codes:**
- `200` - Success
- `500` - Server error

**Example (Python):**
```python
import requests

response = requests.get('http://localhost:5000/api/sensors')
data = response.json()

for sensor_id, sensor in data['sensors'].items():
    print(f"{sensor['name']}: {sensor['temperature']}°C ({sensor['status']})")
```

---

## Logging Endpoints

### POST /api/logging/start

**Description:** Start a new data logging session

**Request:**
```bash
curl -X POST http://localhost:5000/api/logging/start \
  -H "Content-Type: application/json" \
  -d '{
    "folder": "/home/pi/temperature_logs/",
    "duration": 600,
    "interval": 60
  }'
```

**Request Body:**
```json
{
  "folder": "/home/pi/temperature_logs/",  // Directory for log files
  "duration": 600,                          // Seconds (0 = unlimited)
  "interval": 60                            // Seconds between samples
}
```

**Parameters:**
- `folder` (string, optional): Path to log directory
  - Default: `/home/pi/temperature_logs/`
  - Must be writable by application
- `duration` (integer, optional): Session duration in seconds
  - `0` = unlimited (must manually stop)
  - Default: `null`
- `interval` (integer, optional): Sample interval in seconds
  - Minimum: `10` seconds
  - Default: `60`

**Response (200 OK):**
```json
{
  "status": "ok",
  "filename": "temperature_log_2025-12-10_19-00-00.csv",
  "startTime": 1702253800000,
  "duration": 600,
  "interval": 60
}
```

**Response Fields:**
- `status` (string): "ok" on success
- `filename` (string): Name of created log file
- `startTime` (integer): Unix timestamp in milliseconds
- `duration` (integer): Session duration (null if unlimited)
- `interval` (integer): Sample interval in seconds

**Status Codes:**
- `200` - Success
- `400` - Bad request (not ready for logging)
- `500` - Server error

**CSV Format Created:**
```csv
Timestamp,281234567890ab,289876543210cd
2025-12-10T19:00:00.123456,25.50,26.30
2025-12-10T19:01:00.234567,25.52,26.28
```

**Example (JavaScript):**
```javascript
async function startLogging() {
  const response = await fetch('/api/logging/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      folder: '/home/pi/temperature_logs/',
      duration: 600,
      interval: 60
    })
  });
  
  const data = await response.json();
  console.log('Logging started:', data.filename);
}
```

---

### POST /api/logging/stop

**Description:** Stop the current logging session and close the file

**Request:**
```bash
curl -X POST http://localhost:5000/api/logging/stop
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "filename": "temperature_log_2025-12-10_19-00-00.csv"
}
```

**Response Fields:**
- `status` (string): "ok" on success
- `filename` (string): Name of saved log file

**Status Codes:**
- `200` - Success
- `500` - Server error

**Example (JavaScript):**
```javascript
async function stopLogging() {
  const response = await fetch('/api/logging/stop', { method: 'POST' });
  const data = await response.json();
  console.log('Logging stopped:', data.filename);
}
```

---

## Graph Endpoints

### GET /api/graphs/data

**Description:** Get historical temperature data from log files

**Request:**
```bash
# Get all data
curl http://localhost:5000/api/graphs/data

# Get specific file
curl http://localhost:5000/api/graphs/data?file=temperature_log_2025-12-10_19-00-00.csv
```

**Query Parameters:**
- `file` (string, optional): Specific CSV filename
  - If omitted: loads all CSV files and returns only first one's data
  - Format: `temperature_log_YYYY-MM-DD_HH-MM-SS.csv`

**Response (200 OK):**
```json
{
  "sessions": {
    "temperature_log_2025-12-10_19-00-00.csv": [
      {
        "timestamp": "2025-12-10T19:00:00.123456",
        "readings": {
          "281234567890ab": 25.50,
          "289876543210cd": 26.30
        }
      },
      {
        "timestamp": "2025-12-10T19:01:00.234567",
        "readings": {
          "281234567890ab": 25.52,
          "289876543210cd": 26.28
        }
      }
    ]
  },
  "files": [
    "temperature_log_2025-12-10_19-00-00.csv",
    "temperature_log_2025-12-10_20-30-45.csv"
  ]
}
```

**Response Fields:**
- `sessions` (object): Map of filename to data array
  - `timestamp` (string): ISO 8601 timestamp
  - `readings` (object): Sensor ID to temperature mapping
    - Value is float in Celsius or `null` if offline (NC)
- `files` (array): List of all available CSV files

**Status Codes:**
- `200` - Success
- `500` - Server error

**Example (JavaScript):**
```javascript
async function loadGraphData() {
  const response = await fetch('/api/graphs/data');
  const data = await response.json();
  
  const session = Object.values(data.sessions)[0];
  session.forEach(entry => {
    console.log(entry.timestamp, entry.readings);
  });
}
```

---

### GET /api/graphs/download

**Description:** Download all logged data as a combined CSV file

**Request:**
```bash
curl -O http://localhost:5000/api/graphs/download
```

**Response:** Binary CSV file named `temperature_data.csv`

**File Format:**
```csv
Timestamp,281234567890ab,289876543210cd
2025-12-10T19:00:00.123456,25.50,26.30
2025-12-10T19:01:00.234567,25.52,26.28
2025-12-10T20:30:45.345678,24.80,25.90
2025-12-10T20:31:45.456789,24.82,25.88
```

**Status Codes:**
- `200` - Success, file returned
- `404` - No data available
- `500` - Server error

**Example (Browser):**
```javascript
function downloadData() {
  window.location.href = '/api/graphs/download';
}
```

---

## Probe Endpoints

### POST /api/probes/rescan

**Description:** Trigger Arduino to search for new OneWire sensors

**Request:**
```bash
curl -X POST http://localhost:5000/api/probes/rescan
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "sensors": {
    "281234567890ab": {
      "name": "Probe 28123456",
      "temperature": 25.50,
      "status": "online",
      "lastUpdate": 1702253800.123
    }
  }
}
```

**Status Codes:**
- `200` - Success
- `500` - Server error

**Note:** Rescan takes ~2-3 seconds per sensor on the bus

---

### POST /api/probes/rename

**Description:** Rename a sensor for easier identification

**Request:**
```bash
curl -X POST http://localhost:5000/api/probes/rename \
  -H "Content-Type: application/json" \
  -d '{
    "sensor_id": "281234567890ab",
    "name": "Living Room"
  }'
```

**Request Body:**
```json
{
  "sensor_id": "281234567890ab",  // OneWire sensor address
  "name": "Living Room"             // New display name
}
```

**Parameters:**
- `sensor_id` (string, required): 16-character hex sensor address
- `name` (string, required): Custom display name (max 50 chars)

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

**Status Codes:**
- `200` - Success
- `400` - Missing parameters
- `500` - Server error

**Example (Python):**
```python
import requests

response = requests.post('http://localhost:5000/api/probes/rename', 
  json={
    'sensor_id': '281234567890ab',
    'name': 'Kitchen Temperature'
  }
)
print(response.json())
```

---

## Mock Mode Endpoints

### POST /api/mock/enable

**Description:** Enable mock mode to simulate sensors for testing

**Request:**
```bash
curl -X POST http://localhost:5000/api/mock/enable
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Mock mode enabled"
}
```

**Behavior:**
- Generates 2-5 random sensors
- Provides realistic temperature values (20-35°C)
- Simulates read delays (~0.5 seconds)
- Useful for testing without Arduino

**Status Codes:**
- `200` - Success
- `500` - Server error

**Example (cURL):**
```bash
# Enable testing
curl -X POST http://localhost:5000/api/mock/enable

# System now generates test sensors
curl http://localhost:5000/api/sensors
# Output: {"sensors": {"280000000000ab": {...}, ...}}
```

---

### POST /api/mock/disable

**Description:** Disable mock mode and return to normal Arduino listening

**Request:**
```bash
curl -X POST http://localhost:5000/api/mock/disable
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Mock mode disabled"
}
```

**Behavior:**
- Clears all mock sensors from memory
- Waits for real Arduino connection
- Resumes normal operation

**Status Codes:**
- `200` - Success
- `500` - Server error

---

## System Endpoints

### GET /api/system/status

**Description:** Get overall system health and state

**Request:**
```bash
curl http://localhost:5000/api/system/status
```

**Response (200 OK):**
```json
{
  "system_state": "reading",
  "logging_state": "idle",
  "error": null,
  "serial_connected": true
}
```

**Response Fields:**
- `system_state` (string): 
  - `idle` - Waiting to start
  - `waiting_for_serial` - No Arduino connection
  - `reading` - Sensors being read
  - `logging` - Actively logging data
  - `error` - System error
- `logging_state` (string):
  - `idle` - Not logging
  - `logging` - Logging active
  - `stopping` - Stopping current session
- `error` (string or null): Error message if any
- `serial_connected` (boolean): Arduino connection status

**Status Codes:**
- `200` - Success

---

## Error Responses

All endpoints may return error responses:

**400 Bad Request:**
```json
{
  "error": "Missing parameters"
}
```

**500 Server Error:**
```json
{
  "error": "Failed to start logging: Permission denied"
}
```

---

## Rate Limiting

No explicit rate limiting, but recommended:
- Dashboard refresh: 2-5 seconds minimum
- Graph data: 10+ seconds minimum
- Logging data: Write every 60+ seconds

---

## Data Types

### Temperature
- **Unit**: Celsius (°C)
- **Range**: -55 to +125°C (DS18B20 spec)
- **Precision**: 2 decimal places
- **Invalid**: `null` or "NC" in CSV

### Timestamps
- **Dashboard**: Unix timestamp (seconds since epoch)
- **CSV**: ISO 8601 format
  - Example: `2025-12-10T19:00:00.123456`
- **API responses**: Unix timestamp in milliseconds

### Sensor ID
- **Format**: 16 hex characters
- **Example**: `281234567890ab`
- **Meaning**: 
  - `28` = DS18B20 family code
  - Remaining 12 chars = unique serial number

---

## CORS Headers

By default, no CORS headers are set. For cross-origin requests, add to `app.py`:

```python
from flask_cors import CORS
CORS(app)
```

Then install:
```bash
pip install flask-cors
```

---

## Authentication

Currently no authentication required. For production, add:

```python
from functools import wraps

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.password != 'secret':
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/api/sensors')
@require_auth
def get_sensors():
    # ...
```

---

## Testing

**Using curl:**
```bash
# Test all sensors
curl http://localhost:5000/api/sensors | json_pp

# Start logging with 2-minute duration, 30-second interval
curl -X POST http://localhost:5000/api/logging/start \
  -H "Content-Type: application/json" \
  -d '{"duration": 120, "interval": 30}'

# Get graph data
curl http://localhost:5000/api/graphs/data | json_pp
```

**Using Python:**
```python
import requests
import json

# Test endpoint
response = requests.get('http://localhost:5000/api/sensors')
print(json.dumps(response.json(), indent=2))
```

**Using Postman:**
1. Open Postman
2. Create new collection
3. Add requests for each endpoint
4. Set variables for base URL and sensor IDs
5. Run collection tests

---

## Changelog

### v5 (Current)
- ✅ Mock enable/disable endpoints
- ✅ Per-file graph selection
- ✅ System status endpoint

### v4
- ✅ Full API documented
- ✅ CSV export endpoint

---

**Last Updated:** December 10, 2025  
**API Version:** 1.0

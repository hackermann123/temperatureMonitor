#!/usr/bin/env python3
"""
Heater Temperature Reader Daemon
Reads heater thermistor temperature and shares with Flask web app
Writes temperature to a shared file that Flask can read
"""

import time
import math
import spidev
import threading
import json
from pathlib import Path
from datetime import datetime

# ============================================================================
# THERMISTOR CONFIGURATION (COPY FROM heating_control.py)
# ============================================================================

SUPPLY_VOLTAGE = 3.3
ADC_REFERENCE_VOLTAGE = 3.3
THERMISTOR_BETA = 3984
THERMISTOR_REFERENCE_RESISTANCE = 11450
THERMISTOR_REFERENCE_TEMP = 21.60
VOLTAGE_DIVIDER_RESISTOR = 2200
VOLTAGE_DIVIDER_INVERTED = True

# Shared data file location
SHARED_DATA_FILE = "/tmp/heater_data.json"

def calculate_temperature_from_voltage(voltage):
    """Calculate temperature from measured voltage"""
    if voltage < 0 or voltage >= SUPPLY_VOLTAGE or voltage == 0:
        return None
    
    if VOLTAGE_DIVIDER_INVERTED:
        resistance = VOLTAGE_DIVIDER_RESISTOR * (SUPPLY_VOLTAGE - voltage) / voltage
    else:
        resistance = VOLTAGE_DIVIDER_RESISTOR * voltage / (SUPPLY_VOLTAGE - voltage)
    
    if resistance <= 0:
        return None
    
    T_ref_kelvin = THERMISTOR_REFERENCE_TEMP + 273.15
    temp_kelvin = 1.0 / (
        1.0 / T_ref_kelvin +
        (1.0 / THERMISTOR_BETA) * math.log(resistance / THERMISTOR_REFERENCE_RESISTANCE)
    )
    
    temp_celsius = temp_kelvin - 273.15
    return temp_celsius

def read_mcp3204_channel(spi, channel):
    """Read a single channel from MCP3204"""
    try:
        cmd = [0x06 | (channel >> 2), (channel << 6) & 0xC0, 0x00]
        response = spi.xfer2(cmd)
        raw_value = ((response[1] & 0x0F) << 8) | response[2]
        voltage = (raw_value / 4095.0) * ADC_REFERENCE_VOLTAGE
        
        if channel == 0:
            temp = calculate_temperature_from_voltage(voltage)
            return temp
        return None
    except Exception as e:
        print(f"✗ Error reading channel {channel}: {e}")
        return None

def update_shared_data(temperature, relay_state=None):
    """Write temperature to shared file for Flask app to read"""
    try:
        data = {
            "timestamp": datetime.now().isoformat(),
            "temperature_c": temperature,
            "relay_state": relay_state
        }
        
        # Write atomically
        with open(SHARED_DATA_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"✗ Error writing shared data: {e}")

def reader_thread():
    """Background thread that continuously reads heater temperature"""
    try:
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 1000000
        spi.mode = 0
        
        print("[HEATER DAEMON] SPI initialized, starting temperature reads...")
        
        while True:
            temp = read_mcp3204_channel(spi, 0)
            
            if temp is not None:
                print(f"[HEATER] {temp:.2f}°C")
                update_shared_data(temp)
            else:
                print("[HEATER] Error reading temperature")
                update_shared_data(None)
            
            time.sleep(1)
    
    except Exception as e:
        print(f"✗ HEATER DAEMON ERROR: {e}")
    finally:
        try:
            spi.close()
        except:
            pass

def main():
    print("=" * 60)
    print("Heater Temperature Reader Daemon")
    print("=" * 60)
    print(f"Shared data file: {SHARED_DATA_FILE}")
    print("Starting background temperature reader...")
    print("=" * 60)
    
    # Start background thread
    thread = threading.Thread(target=reader_thread, daemon=True)
    thread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n✓ Daemon stopped by user")

if __name__ == "__main__":
    main()

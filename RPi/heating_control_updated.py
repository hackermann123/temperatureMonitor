#!/usr/bin/env python3
"""
Heating Control System - Temperature Control via Relay
UPDATED: Now reads target temperature from web UI via shared file
         and provides feedback to the web dashboard

THERMISTOR: Vishay NTCALUG01A103J (10kΩ NTC, β=3984K)
REFERENCE RESISTOR: 2.2kΩ (voltage divider - INVERTED)
MCP3204 SUPPLY: 3.3V
ADC REFERENCE: 3.3V
RELAY: GPIO25 (Raspberry Pi Compute Module)
CIRCUIT (INVERTED): 3.3V ─── Rt ─── CH0 ─── 2.2kΩ ─── GND
"""

import time
import sys
import math
import spidev
import RPi.GPIO as GPIO
from datetime import datetime
import os
import json
from pathlib import Path

# ============================================================================
# THERMISTOR & CIRCUIT CONFIGURATION
# ============================================================================

SUPPLY_VOLTAGE = 3.3
ADC_REFERENCE_VOLTAGE = 3.3
THERMISTOR_BETA = 3984
THERMISTOR_REFERENCE_RESISTANCE = 11450
THERMISTOR_REFERENCE_TEMP = 21.60
VOLTAGE_DIVIDER_RESISTOR = 2200
VOLTAGE_DIVIDER_INVERTED = True

# ============================================================================
# GPIO & RELAY CONFIGURATION
# ============================================================================

RELAY_GPIO_PIN = 25
RELAY_ACTIVE_HIGH = True
DEBUG_MODE = True

# ============================================================================
# PID CONTROL CONFIGURATION
# ============================================================================

PID_SAMPLE_TIME = 1.0
PID_KP = 0.1106
PID_KI = 0.021
PID_KD = 0.2768
PID_OUTPUT_MIN = 0
PID_OUTPUT_MAX = 1
TEMPERATURE_DEADBAND = 0.5

# ============================================================================
# STARTUP & SAFETY CONFIGURATION
# ============================================================================

MAX_TEMPERATURE = 80.0
MIN_TEMPERATURE = -10.0
STARTUP_DELAY = 0.5
SAMPLE_RATE = 1
DEBUG_MODE = True

# ============================================================================
# SHARED DATA FILES (NEW)
# ============================================================================

HEATER_OUTPUT_FILE = "/tmp/heater_data.json"  # What we WRITE (current temp, relay state)
HEATER_INPUT_FILE = "/tmp/heater_target.json"  # What we READ (target temp from web UI)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_temperature_from_voltage(voltage):
    """Calculate temperature from measured voltage using Steinhart-Hart equation"""
    if voltage < 0 or voltage >= SUPPLY_VOLTAGE:
        return None
    if voltage == 0:
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
    return {
        'resistance': resistance,
        'temperature_c': temp_celsius
    }

def read_mcp3204_channel(spi, channel):
    """Read a single channel from MCP3204"""
    try:
        cmd = [0x06 | (channel >> 2), (channel << 6) & 0xC0, 0x00]
        response = spi.xfer2(cmd)
        raw_value = ((response[1] & 0x0F) << 8) | response[2]
        voltage = (raw_value / 4095.0) * ADC_REFERENCE_VOLTAGE
        
        temp_data = None
        if channel == 0:
            temp_data = calculate_temperature_from_voltage(voltage)
        
        return raw_value, voltage, temp_data
    except Exception as e:
        print(f"✗ Error reading channel {channel}: {e}")
        return None, None, None

def setup_gpio():
    """Initialize GPIO for relay control"""
    try:
        if DEBUG_MODE:
            print(f"[GPIO DEBUG] Attempting GPIO setup for pin {RELAY_GPIO_PIN}...")
        
        try:
            GPIO.cleanup()
            time.sleep(0.2)
        except:
            pass
        
        GPIO.setmode(GPIO.BCM)
        if DEBUG_MODE:
            print(f"[GPIO DEBUG] GPIO mode set to BCM")
        
        GPIO.setup(RELAY_GPIO_PIN, GPIO.OUT, initial=GPIO.LOW)
        if DEBUG_MODE:
            print(f"[GPIO DEBUG] GPIO{RELAY_GPIO_PIN} setup as OUTPUT (initial LOW)")
        
        state = GPIO.input(RELAY_GPIO_PIN)
        if DEBUG_MODE:
            print(f"[GPIO DEBUG] GPIO{RELAY_GPIO_PIN} read back as: {state} (should be 0)")
        
        print(f"✓ GPIO{RELAY_GPIO_PIN} initialized (Relay control)")
    except Exception as e:
        print(f"✗ GPIO initialization failed: {e}")
        print(f"✗ Make sure you are running with sudo: sudo python3 heating_control.py")
        sys.exit(1)

def set_relay(state):
    """Control relay state"""
    try:
        if RELAY_ACTIVE_HIGH:
            gpio_state = GPIO.HIGH if state else GPIO.LOW
        else:
            gpio_state = GPIO.LOW if state else GPIO.HIGH
        
        GPIO.output(RELAY_GPIO_PIN, gpio_state)
        
        if DEBUG_MODE:
            read_state = GPIO.input(RELAY_GPIO_PIN)
            print(f"[GPIO DEBUG] Set GPIO{RELAY_GPIO_PIN} to {gpio_state} (read back: {read_state})")
    except Exception as e:
        print(f"✗ Error setting relay: {e}")

def cleanup_gpio():
    """Cleanup GPIO resources"""
    try:
        GPIO.output(RELAY_GPIO_PIN, GPIO.LOW)
        GPIO.cleanup()
    except:
        pass

def read_target_temp_from_web():
    """Read target temperature that was set via web UI"""
    try:
        web_file = Path(HEATER_INPUT_FILE)
        if web_file.exists():
            with open(web_file, 'r') as f:
                data = json.load(f)
                target = data.get('target_temp')
                if target is not None:
                    return float(target)
    except Exception as e:
        # Silently ignore file read errors
        pass
    return None

def write_status_to_web(current_temp, relay_on, target_temp):
    """Write current status to shared file for web UI to read"""
    try:
        data = {
            "timestamp": datetime.now().isoformat(),
            "temperature_c": current_temp,
            "relay_state": relay_on,
            "target_temp": target_temp
        }
        
        with open(HEATER_OUTPUT_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"✗ Error writing status file: {e}")

# ============================================================================
# TEMPERATURE CONTROLLER CLASS
# ============================================================================

class TemperatureController:
    """PID-based temperature controller for heating system"""
    
    def __init__(self, target_temp, kp=PID_KP, ki=PID_KI, kd=PID_KD,
                 sample_time=PID_SAMPLE_TIME, deadband=TEMPERATURE_DEADBAND):
        self.target_temp = target_temp
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.sample_time = sample_time
        self.deadband = deadband
        self.last_error = 0
        self.integral = 0
        self.last_time = time.time()
        self.heating = False
    
    def update(self, current_temp):
        """Calculate relay output based on current temperature"""
        now = time.time()
        dt = now - self.last_time
        
        error = self.target_temp - current_temp
        p_term = self.kp * error
        
        self.integral += error * dt
        self.integral = max(-10, min(10, self.integral))
        i_term = self.ki * self.integral
        
        if dt > 0:
            d_term = self.kd * (error - self.last_error) / dt
        else:
            d_term = 0
        
        # Hysteresis control
        if self.heating:
            if current_temp >= (self.target_temp + self.deadband):
                self.heating = False
        else:
            if current_temp < self.target_temp:
                self.heating = True
        
        self.last_error = error
        self.last_time = now
        
        return self.heating
    
    def set_target(self, target_temp):
        """Set new target temperature"""
        self.target_temp = target_temp
        self.integral = 0

# ============================================================================
# MAIN PROGRAM
# ============================================================================

def main():
    print("\n" + "="*80)
    print("Heating Control System - Temperature Control via Relay")
    print("="*80)
    print(f"Relay GPIO: {RELAY_GPIO_PIN} (RPi Compute Module)")
    print(f"Relay Logic: {'ACTIVE HIGH' if RELAY_ACTIVE_HIGH else 'ACTIVE LOW'}")
    print(f"Control Method: Hysteresis (deadband: {TEMPERATURE_DEADBAND}°C)")
    print(f"Max Safe Temperature: {MAX_TEMPERATURE}°C")
    print(f"Configuration: {'INVERTED' if VOLTAGE_DIVIDER_INVERTED else 'NORMAL'}")
    print(f"Shared files:")
    print(f"  Input:  {HEATER_INPUT_FILE} (reads target from web UI)")
    print(f"  Output: {HEATER_OUTPUT_FILE} (shares status with web UI)")
    print("="*80 + "\n")
    
    # Check if running as root
    if os.geteuid() != 0:
        print("⚠ WARNING: This script should be run with sudo for GPIO control!")
        print("Usage: sudo python3 heating_control.py [target_temp]\n")
    
    # Get initial target temperature
    target_temp = None
    
    if len(sys.argv) > 1:
        try:
            target_temp = float(sys.argv[1])
        except ValueError:
            print("✗ Invalid target temperature. Usage: sudo python3 heating_control.py [temp]")
            sys.exit(1)
    else:
        print("Interactive Mode: Enter initial target temperature")
        try:
            target_temp = float(input("Target Temperature (°C): "))
        except ValueError:
            print("✗ Invalid input")
            sys.exit(1)
    
    # Validate target temperature
    if target_temp < 0 or target_temp > MAX_TEMPERATURE:
        print(f"✗ Target temperature must be between 0°C and {MAX_TEMPERATURE}°C")
        sys.exit(1)
    
    # Initialize GPIO
    setup_gpio()
    
    # Initialize controller
    controller = TemperatureController(
        target_temp=target_temp,
        kp=PID_KP,
        ki=PID_KI,
        kd=PID_KD,
        sample_time=PID_SAMPLE_TIME,
        deadband=TEMPERATURE_DEADBAND
    )
    
    print(f"✓ Initial target temperature set to {target_temp}°C")
    print(f"✓ Waiting for target changes from web UI at {HEATER_INPUT_FILE}")
    print("\nStarting temperature control loop...\n")
    
    try:
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 1000000
        spi.mode = 0
        
        print(f"✓ SPI initialized (1 MHz)")
        time.sleep(STARTUP_DELAY)
        
        # Print header
        print(f"{'Time':<10} {'Temp(°C)':<12} {'Target':<12} {'Relay':<10} {'Voltage':<12} {'Status':<20}")
        print("-" * 90)
        
        iteration = 0
        last_target_check = time.time()
        
        while True:
            iteration += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Check if web UI has updated target temperature (every 5 iterations)
            if iteration % 5 == 0:
                web_target = read_target_temp_from_web()
                if web_target is not None and web_target != target_temp:
                    target_temp = web_target
                    controller.set_target(target_temp)
                    print(f"\n[WEB UI] Target temperature updated to {target_temp}°C\n")
            
            # Read temperature from CH0
            ch0_raw, ch0_volt, ch0_temp = read_mcp3204_channel(spi, 0)
            
            if ch0_temp is None:
                print(f"{timestamp:<10} {'ERROR':<12} {target_temp:<12.2f} {'OFF':<10} {str(ch0_volt):<12} {'Sensor Error':<20}")
                set_relay(False)
                write_status_to_web(None, False, target_temp)
                time.sleep(1.0 / SAMPLE_RATE)
                continue
            
            current_temp = ch0_temp['temperature_c']
            
            # Safety check
            if current_temp > MAX_TEMPERATURE:
                print(f"{timestamp:<10} {current_temp:<12.2f} {target_temp:<12.2f} {'OFF':<10} {ch0_volt:<12.4f} {'OVERHEAT - SHUTOFF':<20}")
                set_relay(False)
                write_status_to_web(current_temp, False, target_temp)
                break
            
            if current_temp < MIN_TEMPERATURE:
                print(f"{timestamp:<10} {current_temp:<12.2f} {target_temp:<12.2f} {'OFF':<10} {ch0_volt:<12.4f} {'Sensor Error':<20}")
                set_relay(False)
                write_status_to_web(current_temp, False, target_temp)
                time.sleep(1.0 / SAMPLE_RATE)
                continue
            
            # Update controller
            relay_on = controller.update(current_temp)
            
            # Set relay state
            set_relay(relay_on)
            
            # Write status to web UI
            write_status_to_web(current_temp, relay_on, target_temp)
            
            # Status message
            error = target_temp - current_temp
            
            if abs(error) < 0.5:
                status = "✓ On target"
            elif relay_on:
                status = f"↑ Heating (+{error:.1f}°C)"
            else:
                status = f"↓ Idle ({error:.1f}°C)"
            
            relay_str = "ON" if relay_on else "OFF"
            
            # Print status line
            print(f"{timestamp:<10} {current_temp:<12.2f} {target_temp:<12.2f} {relay_str:<10} {ch0_volt:<12.4f} {status:<20}")
            
            time.sleep(1.0 / SAMPLE_RATE)
    
    except KeyboardInterrupt:
        print("\n\n✓ Stopped by user")
        set_relay(False)
    except Exception as e:
        print(f"\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        set_relay(False)
        sys.exit(1)
    finally:
        try:
            spi.close()
        except:
            pass
        cleanup_gpio()
        print("✓ Relay disabled and GPIO cleaned up")

if __name__ == "__main__":
    main()

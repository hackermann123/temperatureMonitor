import RPi.GPIO as GPIO

# Use BCM GPIO numbering
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Store pin states
gpio_pins = {}

def print_status():
    print("\n======= GPIO STATUS =======")
    if not gpio_pins:
        print("No pins initialized yet.")
    else:
        for pin, state in gpio_pins.items():
            print(f"GPIO {pin:>2}: {'ON ' if state else 'OFF'}")
    print("===========================\n")

print("\nRaspberry Pi GPIO Console (RPi.GPIO)")
print("Enter a GPIO number to toggle it")
print("Type 'q' to quit\n")

while True:
    print_status()
    user_input = input("GPIO number: ").strip()

    if user_input.lower() == 'q':
        break

    if not user_input.isdigit():
        print("Invalid input\n")
        continue

    pin = int(user_input)

    try:
        # If pin not yet configured, set it up
        if pin not in gpio_pins:
            GPIO.setup(pin, GPIO.OUT)
            gpio_pins[pin] = False  # OFF
            GPIO.output(pin, GPIO.LOW)
            print(f"GPIO {pin} initialized as OUTPUT")

        # Toggle pin
        gpio_pins[pin] = not gpio_pins[pin]
        GPIO.output(pin, GPIO.HIGH if gpio_pins[pin] else GPIO.LOW)

        print(f"GPIO {pin} -> {'ON' if gpio_pins[pin] else 'OFF'}")

    except Exception as e:
        print(f"GPIO error: {e}")

# Clean up GPIO on exit
GPIO.cleanup()
print("GPIO cleaned up. Bye!")

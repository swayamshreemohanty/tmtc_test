import RPi.GPIO as GPIO
import serial
import time
import atexit

STROBE_PIN = 23
UART_PORT = '/dev/serial0'
BAUD_RATE = 460800

def cleanup_gpio():
    try:
        GPIO.cleanup()
    except Exception:
        pass


def initialize_gpio(pin, retries=20, retry_delay_s=0.05):
    cleanup_gpio()
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    last_error = None
    for _ in range(retries):
        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            return
        except Exception as error:
            last_error = error
            cleanup_gpio()
            time.sleep(retry_delay_s)
            GPIO.setmode(GPIO.BCM)

    raise RuntimeError(f"Failed to setup GPIO {pin}: {last_error}")

# Setup Serial
ser = serial.Serial(UART_PORT, BAUD_RATE)
atexit.register(cleanup_gpio)
initialize_gpio(STROBE_PIN)

total_strobe_count = 0
payload_value = 1


def wait_for_rising_edge(pin):
    try:
        GPIO.wait_for_edge(pin, GPIO.RISING)
        return
    except Exception:
        pass

    last_state = GPIO.input(pin)

    while True:
        state = GPIO.input(pin)
        if last_state == GPIO.LOW and state == GPIO.HIGH:
            return

        last_state = state

try:
    print(f"Waiting for strobe on GPIO {STROBE_PIN}... (Press Ctrl+C to exit)")
    
    while True:
        try:
            wait_for_rising_edge(STROBE_PIN)
        except RuntimeError as error:
            if 'setup() the GPIO channel first' in str(error):
                initialize_gpio(STROBE_PIN)
                continue
            raise
        
        total_strobe_count += 1
        
        data_bytes = payload_value.to_bytes(4, byteorder='big')
        ser.write(data_bytes)
        
        # 1. Create the solid 32-bit string first
        bin_str = f"{payload_value:032b}"
        
        # 2. Slice it into four 8-bit chunks with spaces in between
        spaced_bin = f"{bin_str[0:8]} {bin_str[8:16]} {bin_str[16:24]} {bin_str[24:32]}"
        
        # Print the neatly spaced binary string
        print(f"Number Sent: {payload_value:<3} | 4 Bytes: {spaced_bin} | Total Strobe: {total_strobe_count}")
        
        payload_value += 1
        if payload_value > 0xFFFFFFFF:
            payload_value = 1

except KeyboardInterrupt:
    print("\nExiting program.")

finally:
    cleanup_gpio()
    ser.close()
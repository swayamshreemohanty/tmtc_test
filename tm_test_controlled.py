import RPi.GPIO as GPIO
import serial
import time
import sys
import atexit
import threading
import argparse
from queue import SimpleQueue, Empty

STROBE_PIN = 23
UART_PORT = '/dev/ttyAMA0'
BAUD_RATE = 921600
BOUNCE_MS = None  # set to an int (ms) if you see double triggers
strobe_queue = SimpleQueue()
total_strobe_count = 0
payload_value = 1
byte_lane_index = 0
stop_event = threading.Event()


def on_strobe(channel):  # callback from GPIO thread
    try:
        strobe_queue.put_nowait(time.monotonic())
    except Exception:
        pass

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

def get_payload_byte0(val):
    return val & 0xFF

def get_payload_scan(val, lane):
    return (val & 0xFF) << (lane * 8)

def get_payload_all(val):
    v = val & 0xFF
    return v | (v << 8) | (v << 16) | (v << 24)

def get_user_mode():
    parser = argparse.ArgumentParser(description="UART Strobe Test")
    parser.add_argument('--mode', choices=['byte0', 'scan', 'all'], help="Select mode")
    
    # Check if args are provided (excluding script name)
    if len(sys.argv) > 1:
        args = parser.parse_args()
        return args.mode
        
    print("\nSelect Transmission Mode:")
    print("  1. Byte0 (Cycle 1-255 on 1st byte only)")
    print("  2. Scan  (Cycle 1-255 on each byte sequentially)")
    print("  3. All   (Cycle 1-255 on all bytes simultaneously)")
    
    while True:
        try:
            choice = input("Enter choice (1-3): ").strip()
            if choice == '1': return 'byte0'
            if choice == '2': return 'scan'
            if choice == '3': return 'all'
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)

# MODE = get_user_mode() or "all"
MODE = "all"
print(f"Starting in MODE: {MODE}")

# Setup Serial
ser = serial.Serial(
    port=UART_PORT,
    baudrate=BAUD_RATE,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=0,
    write_timeout=0,
)
atexit.register(cleanup_gpio)
initialize_gpio(STROBE_PIN)
if BOUNCE_MS is None:
    GPIO.add_event_detect(STROBE_PIN, GPIO.RISING, callback=on_strobe)
else:
    GPIO.add_event_detect(STROBE_PIN, GPIO.RISING, callback=on_strobe, bouncetime=BOUNCE_MS)


def strobe_worker():
    global payload_value, total_strobe_count, byte_lane_index

    while not stop_event.is_set():
        try:
            strobe_queue.get(timeout=0.5)
        except Empty:
            continue
        except RuntimeError as error:
            if 'setup() the GPIO channel first' in str(error):
                initialize_gpio(STROBE_PIN)
                continue
            raise

        total_strobe_count += 1

        # Calculate 32-bit value based on mode
        val_32 = 0
        if MODE == 'byte0':
            val_32 = get_payload_byte0(payload_value)
        elif MODE == 'scan':
            val_32 = get_payload_scan(payload_value, byte_lane_index)
        elif MODE == 'all':
            val_32 = get_payload_all(payload_value)

        data_bytes = val_32.to_bytes(4, byteorder='little')  # send LSB-first
        ser.write(data_bytes)
        ser.flush()

        # Show bytes in transmit order (LSB-first)
        spaced_bin = " ".join(f"{b:08b}" for b in data_bytes)
        print(f"Sent ({MODE}): {payload_value:<3} | 4 Bytes: {spaced_bin} | Total: {total_strobe_count}")

        payload_value += 1
        if payload_value > 255:
            payload_value = 1
            if MODE == 'scan':
                byte_lane_index = (byte_lane_index + 1) % 4

try:
    print(f"Waiting for strobe on GPIO {STROBE_PIN}... (Press Ctrl+C to exit)")
    worker = threading.Thread(target=strobe_worker, daemon=True)
    worker.start()

    while worker.is_alive():
        worker.join(timeout=0.5)

except KeyboardInterrupt:
    print("\nExiting program.")
    stop_event.set()

finally:
    stop_event.set()
    try:
        GPIO.remove_event_detect(STROBE_PIN)
    except Exception:
        pass
    try:
        worker.join(timeout=1)
    except Exception:
        pass
    cleanup_gpio()
    ser.close()

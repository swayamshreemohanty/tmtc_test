import RPi.GPIO as GPIO
import serial
import time
import atexit
import threading
from queue import SimpleQueue, Empty

STROBE_PIN = 23
UART_PORT = '/dev/serial0'
BAUD_RATE = 460800
BOUNCE_MS = None  # set to an int (ms) if you see double triggers
strobe_queue = SimpleQueue()
total_strobe_count = 0
payload_value = 1
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

# Setup Serial
ser = serial.Serial(UART_PORT, BAUD_RATE)
atexit.register(cleanup_gpio)
initialize_gpio(STROBE_PIN)
if BOUNCE_MS is None:
    GPIO.add_event_detect(STROBE_PIN, GPIO.RISING, callback=on_strobe)
else:
    GPIO.add_event_detect(STROBE_PIN, GPIO.RISING, callback=on_strobe, bouncetime=BOUNCE_MS)


def strobe_worker():
    global payload_value, total_strobe_count

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

        data_bytes = payload_value.to_bytes(4, byteorder='little')  # send LSB-first
        ser.write(data_bytes)

        # Show bytes in transmit order (LSB-first)
        spaced_bin = " ".join(f"{b:08b}" for b in data_bytes)
        print(f"Number Sent: {payload_value:<3} | 4 Bytes (LSB first): {spaced_bin} | Total Strobe: {total_strobe_count}")

        payload_value += 1
        if payload_value > 255:
            payload_value = 1

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

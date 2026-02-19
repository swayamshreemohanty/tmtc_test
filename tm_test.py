import RPi.GPIO as GPIO
import serial
import atexit

STROBE_PIN = 23
UART_PORT = '/dev/serial0'
BAUD_RATE = 460800

def cleanup_gpio():
    try:
        GPIO.cleanup()
    except Exception:
        pass


def initialize_gpio(pin):
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)


def main():
    atexit.register(cleanup_gpio)
    initialize_gpio(STROBE_PIN)

    serial_port = serial.Serial(UART_PORT, BAUD_RATE)
    payload_value = 1
    total_strobe_count = 0

    print(f"Waiting for GPIO {STROBE_PIN} HIGH pulses... (Ctrl+C to exit)")

    try:
        while True:
            GPIO.wait_for_edge(STROBE_PIN, GPIO.RISING)
            total_strobe_count += 1

            data_bytes = payload_value.to_bytes(4, byteorder='big')
            bytes_written = serial_port.write(data_bytes)
            serial_port.flush()

            if bytes_written == 4:
                spaced_bin = format(payload_value, '032b')
                spaced_bin = ' '.join(spaced_bin[i:i + 8] for i in range(0, 32, 8))
                print(f"Number Sent: {payload_value:<3} | 4 Bytes: {spaced_bin} | Total Strobe: {total_strobe_count}")
                payload_value = 1 if payload_value == 0xFFFFFFFF else payload_value + 1
            else:
                print(f"Warning: wrote {bytes_written} bytes")

            GPIO.wait_for_edge(STROBE_PIN, GPIO.FALLING)

    except KeyboardInterrupt:
        print("\nExiting program.")
    finally:
        serial_port.close()
        cleanup_gpio()


if __name__ == "__main__":
    main()
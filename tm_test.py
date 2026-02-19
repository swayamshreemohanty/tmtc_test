import RPi.GPIO as GPIO
import serial

STROBE_PIN = 23
UART_PORT = '/dev/serial0'
BAUD_RATE = 9600

# Setup GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(STROBE_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Setup Serial
ser = serial.Serial(UART_PORT, BAUD_RATE)

total_strobe_count = 0
payload_value = 1

try:
    print(f"Waiting for 2ms strobe on GPIO {STROBE_PIN}... (Press Ctrl+C to exit)")
    
    while True:
        GPIO.wait_for_edge(STROBE_PIN, GPIO.RISING, bouncetime=2)
        
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
        if payload_value > 255:
            payload_value = 1

except KeyboardInterrupt:
    print("\nExiting program.")

finally:
    GPIO.cleanup()
    ser.close()
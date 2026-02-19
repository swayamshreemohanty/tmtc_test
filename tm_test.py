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

# Track the total number of times the strobe fires (keeps growing)
total_strobe_count = 0

# Track the value sent over UART (cycles from 1 to 255)
payload_value = 1

try:
    print(f"Waiting for 2ms strobe on GPIO {STROBE_PIN}... (Press Ctrl+C to exit)")
    
    while True:
        # Wait until the strobe pulse goes HIGH
        GPIO.wait_for_edge(STROBE_PIN, GPIO.RISING, bouncetime=2)
        
        # Increment the total strobe counter
        total_strobe_count += 1
        
        # Convert the 1-255 payload into exactly 4 bytes
        data_bytes = payload_value.to_bytes(4, byteorder='big')
        
        # Send the data over UART
        ser.write(data_bytes)
        
        # Print the decimal number, the 32-bit binary, and the total strobe count
        print(f"Number Sent: {payload_value:<3} | 4-byte Binary: {payload_value:032b} | Total Strobe Count: {total_strobe_count}")
        
        # Increment the payload, and reset to 1 if it exceeds 255
        payload_value += 1
        if payload_value > 255:
            payload_value = 1

except KeyboardInterrupt:
    print("\nExiting program.")

finally:
    # Safely close the port and clean up pins
    GPIO.cleanup()
    ser.close()
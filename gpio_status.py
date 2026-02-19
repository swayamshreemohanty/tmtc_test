import time
import RPi.GPIO as GPIO

GPIO_PIN = 23


def main():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    print(f"Monitoring GPIO {GPIO_PIN} state (Ctrl+C to stop)")

    try:
        while True:
            state = GPIO.input(GPIO_PIN)
            print(f"GPIO {GPIO_PIN}: {'HIGH' if state else 'LOW'}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
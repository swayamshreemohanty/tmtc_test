import time
import lgpio
import board
import busio
from adafruit_ina219 import INA219
from datetime import datetime
import csv
import threading
import sys
import termios
import tty
import subprocess
import os
import signal

# =====================================================
# SAFE AUTO CLEANUP OF OLD GPIO USERS
# =====================================================
my_pid = os.getpid()

try:
    out = subprocess.check_output("lsof /dev/gpiochip0", shell=True).decode()
    for line in out.split("\n"):
        if "python3" in line and "/dev/gpiochip0" in line:
            pid = int(line.split()[1])
            if pid != my_pid:
                print(f"[CLEANUP] Killing leftover GPIO process: {pid}")
                os.system(f"kill -9 {pid}")
except:
    pass

# =====================================================
# GLOBALS
# =====================================================
chip = None
stop_flag = False

# =====================================================
# CLEAN EXIT HANDLER
# =====================================================
def clean_exit(signum=None, frame=None):
    global chip
    print("\n[EXIT] Cleaning up GPIO and stopping...")

    try:
        for p in RELAY_PINS:
            relay_off(p)
    except:
        pass

    try:
        lgpio.gpiochip_close(chip)
        print("[EXIT] Released /dev/gpiochip0")
    except:
        pass

    sys.exit(0)

signal.signal(signal.SIGINT, clean_exit)
signal.signal(signal.SIGTERM, clean_exit)

# =====================================================
# GPIO SETUP
# =====================================================
chip = lgpio.gpiochip_open(0)

RELAY1 = 5
RELAY3 = 27
RELAY2 = 22

RELAY_PINS = [RELAY1, RELAY2, RELAY3]
ACTIVE_LOW = True

relay_state = {RELAY1: 0, RELAY2: 0, RELAY3: 0}

def relay_on(pin):
    lgpio.gpio_write(chip, pin, 0 if ACTIVE_LOW else 1)
    relay_state[pin] = 1

def relay_off(pin):
    lgpio.gpio_write(chip, pin, 1 if ACTIVE_LOW else 0)
    relay_state[pin] = 0

for p in RELAY_PINS:
    lgpio.gpio_claim_output(chip, p)
    relay_off(p)

# =====================================================
# INA219 SETUP (NO configure() – this library version doesn’t support it)
# =====================================================
i2c = busio.I2C(board.SCL, board.SDA)
ina = INA219(i2c)

SHUNT_OHMS = 0.001     # 1mΩ resistor
CALIBRATION_FACTOR = 0.866  # adjust based on real measurement

def read_current():
    shunt_v = ina.shunt_voltage
    return (shunt_v / SHUNT_OHMS) * CALIBRATION_FACTOR

# =====================================================
# CSV LOGGING
# =====================================================
CSV_FILE = "current_log_10ms_with_relays.csv"

try:
    with open(CSV_FILE, "x", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "current_A", "relay1", "relay2", "relay3"])
except FileExistsError:
    pass

# =====================================================
# NONBLOCKING KEYBOARD
# =====================================================
def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

# =====================================================
# HELP MENU
# =====================================================
def print_menu():
    print("\n\n=== Relay Control Menu ===")
    print(" 1 → Relay 1 ON")
    print(" 2 → Relay 1 OFF")
    print(" 3 → Relay 2 ON")
    print(" 4 → Relay 2 OFF")
    print(" 5 → Relay 3 ON")
    print(" 6 → Relay 3 OFF")
    print(" h → Show help menu")
    print(" q → Quit program")
    print("==========================\n")

# =====================================================
# BACKGROUND 10ms MEASUREMENT LOOP
# =====================================================
def measure_loop():
    global stop_flag
    log_interval = 0.01
    next_time = time.time()

    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)

        while not stop_flag:
            current = read_current()

            print(f"\rCurrent = {current:.3f} A    ", end="")

            writer.writerow([
                datetime.now(),
                current,
                relay_state[RELAY1],
                relay_state[RELAY2],
                relay_state[RELAY3]
            ])

            next_time += log_interval
            delay = next_time - time.time()
            if delay > 0:
                time.sleep(delay)
            else:
                next_time = time.time()

thread = threading.Thread(target=measure_loop, daemon=True)
thread.start()

print_menu()

# =====================================================
# MAIN LOOP
# =====================================================
try:
    while True:
        k = getch()

        if k == "1":
            relay_on(RELAY1)
            print("\nRelay 1 → ON")

        elif k == "2":
            relay_off(RELAY1)
            print("\nRelay 1 → OFF")

        elif k == "3":
            relay_on(RELAY2)
            print("\nRelay 2 → ON")

        elif k == "4":
            relay_off(RELAY2)
            print("\nRelay 2 → OFF")

        elif k == "5":
            relay_on(RELAY3)
            print("\nRelay 3 → ON")

        elif k == "6":
            relay_off(RELAY3)
            print("\nRelay 3 → OFF")

        elif k == "h":
            print_menu()

        elif k == "q":
            break

except KeyboardInterrupt:
    pass

# =====================================================
# CLEAN SHUTDOWN
# =====================================================
clean_exit()

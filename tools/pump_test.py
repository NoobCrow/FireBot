import RPi.GPIO as GPIO

RELAY_PIN = 9  # Physical pin 21

GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)

# Pump OFF initially
GPIO.output(RELAY_PIN, GPIO.LOW)

print("PUMP TEST")
print("O = ON")
print("F = OFF")
print("Q = QUIT")

try:
    while True:
        key = input("Command: ").strip().lower()

        if key == "o":
            GPIO.output(RELAY_PIN, GPIO.HIGH)
            print("PUMP ON")

        elif key == "f":
            GPIO.output(RELAY_PIN, GPIO.LOW)
            print("PUMP OFF")

        elif key == "q":
            break

finally:
    GPIO.output(RELAY_PIN, GPIO.LOW)
    GPIO.cleanup()
    print("Pump OFF - GPIO cleaned up")

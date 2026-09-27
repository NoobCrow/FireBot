import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# ============================================================
# ULTRASONIC SENSOR
# ============================================================

TRIG = 16   # Physical pin 36
ECHO = 20   # Physical pin 38

GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

GPIO.output(TRIG, GPIO.LOW)

time.sleep(1)

print("================================")
print("   FIREBOT ULTRASONIC TEST")
print("================================")
print("TRIG: GPIO 16 (Physical 36)")
print("ECHO: GPIO 20 (Physical 38)")
print("Press Ctrl+C to stop")
print()

try:

    while True:

        # Send 10 microsecond trigger pulse
        GPIO.output(TRIG, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(TRIG, GPIO.LOW)

        # Wait for echo to start
        start_wait = time.time()

        while GPIO.input(ECHO) == GPIO.LOW:
            pulse_start = time.time()

            if pulse_start - start_wait > 0.1:
                print("Echo start timeout")
                break

        # Wait for echo to finish
        end_wait = time.time()

        while GPIO.input(ECHO) == GPIO.HIGH:
            pulse_end = time.time()

            if pulse_end - end_wait > 0.1:
                print("Echo end timeout")
                break

        # Calculate distance
        pulse_duration = pulse_end - pulse_start

        distance = pulse_duration * 34300 / 2

        print(f"Distance: {distance:.1f} cm")

        time.sleep(0.5)

except KeyboardInterrupt:

    print("\nStopping ultrasonic test...")

finally:

    GPIO.output(TRIG, GPIO.LOW)
    GPIO.cleanup()

    print("GPIO cleaned up.")

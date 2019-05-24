#sudo apt-get install -y python-pip
#sudo pip install wiringpi

# Servo Control
import time
import wiringpi

#gpio pwm-ms
#pio pwmc 192
#gpio pwmr 2000
#gpio -g pwm 18 100 #1.0ms left
#gpio -g pwm 18 150 #1.5ms middle
#gpio -g pwm 18 200 #2.0ms right

# use 'GPIO naming'
wiringpi.wiringPiSetupGpio()
 
# set #18 to be a PWM output
wiringpi.pinMode(18, wiringpi.GPIO.PWM_OUTPUT)
 
# set the PWM mode to milliseconds stype
wiringpi.pwmSetMode(wiringpi.GPIO.PWM_MODE_MS)
 
# divide down clock for 50Hz
wiringpi.pwmSetClock(192)
wiringpi.pwmSetRange(2000)
 
delay_period = 0.01 #0.1 .. 0.001, slower .. faster
 
while True:
  for pulse in range(55, 252, 1): #50 (0.5ms) to 250 (2.5ms)
    wiringpi.pwmWrite(18, pulse)
    time.sleep(delay_period)
  for pulse in range(252, 55, -1):
    wiringpi.pwmWrite(18, pulse)
    time.sleep(delay_period)
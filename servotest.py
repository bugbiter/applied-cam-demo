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
 
# set #13 & 18 to be PWM outputs
wiringpi.pinMode(13, wiringpi.GPIO.PWM_OUTPUT)
wiringpi.pinMode(18, wiringpi.GPIO.PWM_OUTPUT)
 
# set the PWM mode to milliseconds stype
wiringpi.pwmSetMode(wiringpi.GPIO.PWM_MODE_MS)
 
# divide down clock for 50Hz
wiringpi.pwmSetClock(192)
wiringpi.pwmSetRange(2000)
 
delay_period = 0.05 #0.1 .. 0.001, slower .. faster

#55 (0.55ms) .. 252 (2.52ms) 
wiringpi.pwmWrite(13, 98)
wiringpi.pwmWrite(15, 98)

#while True:  
#  for i, j in zip(range(55, 252, 1), range(252, 55, -1)):
#    wiringpi.pwmWrite(13, i)
#    wiringpi.pwmWrite(18, j)
#    print('{}, {}'.format(i, j))
#    time.sleep(delay_period)
#  for i, j in zip(range(252, 55, -1), range(55, 252, 1)):
#    wiringpi.pwmWrite(13, i)
#    wiringpi.pwmWrite(18, j)
#    print('{}, {}'.format(i, j))
#    time.sleep(delay_period)
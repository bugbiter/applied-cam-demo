#!/usr/bin/env python3
# coding=utf-8

import configparser
import time
import wiringpi
import os
import json
from google.cloud import pubsub_v1

__version__ = '0.0.1'

# globals
# default GPIO pin assignment
tilt_pin = 13
pan_pin = 18

def main():
  # [START main]

  global tilt_pin
  global pan_pin

  # read config
  config_parser = configparser.RawConfigParser()
  config_file_path = r'$config/parameters.conf'
  try:
    config_parser.read(config_file_path)
    credentials_path = config_parser['telemetry']['credentials_path']
    print('Read credentials path from {}: {}'.format(config_file_path, credentials_path))
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    project_id = config_parser['telemetry']['project_id']
    topic_id = config_parser['telemetry']['topic_id']
    print('Read pubsub project: {}, and topic: {}'.format(project_id, topic_id))
  except:
    print('Exception when reading telemetry parameters from {}'.format(config_file_path))
  try:
    config_parser.read(config_file_path)
    tilt_pin = config_parser['io']['tilt_pin']
    pan_pin = config_parser['io']['pan_pin']
    print('Read pwm pins from {}, tilt: {}, pan: {}'.format(config_file_path, tilt_pin, pan_pin))
  except:
    print('Exception when reading io parameters from {}'.format(config_file_path))

  # sanity check
  if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
    print('$GOOGLE_APPLICATION_CREDENTIALS: {}'.format(os.environ['GOOGLE_APPLICATION_CREDENTIALS']))
  else:
    print('Could not find $GOOGLE_APPLICATION_CREDENTIALS')
    # should exit!
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/ubuntu/agent-key.json'
  
  # init GPIO
  wiringpi.wiringPiSetupGpio()
  # set GPIO13 and GPIO18  to be PWM outputs
  wiringpi.pinMode(tilt_pin, wiringpi.GPIO.PWM_OUTPUT)
  wiringpi.pinMode(pan_pin, wiringpi.GPIO.PWM_OUTPUT)
  # set PWM mode  to milliseconds
  wiringpi.pwmSetMode(wiringpi.GPIO.PWM_MODE_MS)
  # divide down clock for 20ms period
  wiringpi.pwmSetClock(192)
  wiringpi.pwmSetRange(2000)
  # set PWM outputs to center position (1.5 ms)
  wiringpi.pwmWrite(tilt_pin, 150)
  wiringpi.pwmWrite(pan_pin, 150)

  # set up PubSub subscription
  subscriber = pubsub_v1.SubscriberClient()
  topic_path = subscriber.topic_path(project_id, topic_id)
  subscription_path = subscriber.subscription_path(project_id, topic_id)
  # create the pull subscription
  try:
    subscription = subscriber.create_subscription(subscription_path, topic_path)
  except Exception as e:
    print('Failed creating subscription: {}'.format(e))
  # subscribe
  try:
    future = subscriber.subscribe(subscription_path, callback=__subscriber_callback)
    while True:
      try:
        future.result()
      except KeyboardInterrupt:
        future.cancel()
  except Exception as e:
    print('Failed subscribing to {}'.format(subscription_path))
  #  [END main]

def __subscriber_callback(message):
  # [START __subscriber_callback]
  global tilt_pin
  global pan_pin

  print(message.data)
  data = json.loads(message.data)

  #if data.type == 'tilt':
  #  setPwmAngle(data.angle, tilt_pin)
  #elif data.type == 'pan':
  #  setPwmAngle(data.angle, pan_pin)

  message.ack()
  # [END __subscriber_callback]

def __set_pwm_angle(angle, pin):
  # [START __set_pwm_angle]
  if angle < 0:
    angle = 0
  elif angle > 180:
    angle = 180

  #pw = angle*(252-55.3)/(180-0) + 55.3
  pw = angle*196.7/180. + 55.3
  print('pw, pin: ', pw, pin)
  wiringpi.pwmWrite(pin, pw)
  # [END __set_pwm_angle]


if __name__ == '__main__':
  main()
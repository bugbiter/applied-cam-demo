#!/usr/bin/env python3
# coding=utf-8

import configparser
import json
import math
import os
import time
import wiringpi
from google.cloud import pubsub_v1

__version__ = '0.0.1'

# globals
# default GPIO pin assignment
tilt_servo_max_pw = 252
tilt_servo_min_pw = 55.3
tilt_min_angle = -1.57
tilt_max_angle = 1.57
tilt_pin = 13
pan_servo_max_pw = 252
pan_servo_min_pw = 55.3
pan_min_angle = -1.57
pan_max_angle = 1.57
pan_pin = 18

def main():
  # [START main]
  global tilt_pin
  global pan_pin
  global tilt_servo_max_pw
  global tilt_servo_min_pw
  global pan_servo_max_pw
  global pan_servo_min_pw
  global tilt_max_angle
  global tilt_min_angle
  global pan_max_angle
  global pan_min_angle

  # read config
  config_parser = configparser.RawConfigParser()
  config_file_path = r'./config/parameters.conf'
  try:
    config_parser.read(config_file_path)
    credentials_path = config_parser['telemetry']['credentials_path']
    print('Read credentials path {}'.format(credentials_path))
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    project_id = config_parser['telemetry']['project_id']
    topic_id = config_parser['telemetry']['topic_id']
    print('Read pubsub project {}, and topic {}'.format(project_id, topic_id))
  except:
    print('Exception when reading telemetry parameters from {}'.format(config_file_path))
  try:
    config_parser.read(config_file_path)
    tilt_pin = int(config_parser['io']['tilt_pin'])
    pan_pin = int(config_parser['io']['pan_pin'])
    tilt_servo_max_pw = float(config_parser['io']['tilt_servo_max_pw'])
    tilt_servo_min_pw = float(config_parser['io']['tilt_servo_min_pw'])
    pan_servo_max_pw = float(config_parser['io']['pan_servo_max_pw'])
    pan_servo_min_pw = float(config_parser['io']['pan_servo_min_pw'])
    tilt_max_angle = float(config_parser['io']['tilt_max_angle'])
    tilt_min_angle = float(config_parser['io']['tilt_min_angle'])
    pan_max_angle = float(config_parser['io']['pan_max_angle'])
    pan_min_angle = float(config_parser['io']['pan_min_angle'])
    print('Tilt pin {}, servo max pw {}, servo min pw {}, max angle {}, min angle {}'.format(tilt_pin, tilt_servo_max_pw, tilt_servo_min_pw, tilt_max_angle, tilt_min_angle))
    print('Pan pin {}, servo max pw {}, servo min pw {}, max angle {}, min angle {}'.format(pan_pin, pan_servo_max_pw, pan_servo_min_pw, pan_max_angle, pan_min_angle))
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
        raise
  except Exception as e:
    print('Failed subscribing to {}'.format(subscription_path))
  #  [END main]

def __subscriber_callback(message):
  # [START __subscriber_callback]
  #{
  #  "links": [],
  #  "head": {
  #      "links": [],
  #      "type": "goggle_direction",
  #      "last_seen": 1557746562 (epoch_milliseconds)
  #  },
  #  "body": {
  #      "roll": 0.0,
  #      "pitch": 0.0, (tilt)
  #      "yaw": 0.7853981633974483 (pan)
  #  }
  #}
  print(message.data)
  data = json.loads(message.data)

  try:
    if data['head']['type'] == 'goggle_direction':
      __set_tilt_angle(data['body']['pitch']
      __set_pan_angle(data['body']['yaw']
  except Exception as e:
    print('Failed to set tilt/pan: {}'.format(e))
  message.ack()
  # [END __subscriber_callback]

def __set_tilt_angle(angle):
  # [START __set_tilt_angle]
  global tilt_servo_max_pw
  global tilt_servo_min_pw
  global tilt_max_angle
  global tilt_min_angle
  global tilt_pin

  print('Tilt angle {}'.format(angle))
  if angle < tilt_min_angle:
    angle = tilt_min_angle
    print('Truncate angle < min')
  elif angle > tilt_max_angle:
    angle = tilt_max_angle
    print('truncate angle > max')

  servo_delta = tilt_servo_max_pw - tilt_servo_min_pw
  angle_delta = tilt_max_angle - tilt_min_angle
  pw = ((angle - tilt_min_angle) * servo_delta / angle_delta) + tilt_servo_min_pw
  print('pw {} pin {}'.format(pw, tilt_pin))
  wiringpi.pwmWrite(tilt_pin, pw)
  # [END __set_tilt_angle]

def __set_pan_angle(angle):
  # [START __set_pan_angle]
  global pan_servo_max_pw
  global pan_servo_min_pw
  global pan_max_angle
  global pan_min_angle
  global pan_pin

  print('Pan angle {}'.format(angle))
  if angle < pan_min_angle:
    angle = pan_min_angle
    print('Truncate angle < min')
  elif angle > pan_max_angle:
    angle = pan_max_angle
    print('truncate angle > max')
  
  servo_delta = pan_servo_max_pw - pan_servo_min_pw
  angle_delta = pan_max_angle - pan_min_angle
  pw = ((angle - pan_min_angle) * servo_delta / angle_delta) + pan_servo_min_pw
  print('pw {}, pin {}'.format(pw, pan_pin))
  wiringpi.pwmWrite(pan_pin, pw)
  # [END __set_pan_angle]

if __name__ == '__main__':
  main()
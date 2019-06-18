#!/usr/bin/env python3
# coding=utf-8

import configparser
import json
import logging
import logging.config
import math
import os
import sys
import time
import wiringpi
from google.cloud import pubsub_v1

__version__ = '0.0.2'

# globals
# default GPIO pin assignment
tilt_servo_max_pw = 252
tilt_servo_min_pw = 55.3
tilt_min_angle = -1.57
tilt_max_angle = 1.57
tilt_ratio = 1.0
tilt_pin = 13
pan_servo_max_pw = 252
pan_servo_min_pw = 55.3
pan_min_angle = -1.57
pan_max_angle = 1.57
pan_ratio = 1.0
pan_pin = 18

def main():
  # [START main]
  global tilt_pin
  global pan_pin
  global tilt_ratio
  global pan_ratio
  global tilt_servo_max_pw
  global tilt_servo_min_pw
  global pan_servo_max_pw
  global pan_servo_min_pw
  global tilt_max_angle
  global tilt_min_angle
  global pan_max_angle
  global pan_min_angle

  # If the module is executed as a script __name__ will be '__main__' and sys.argv[0] 
  # will be the full path of the module.
  if __name__ == '__main__':
      path_here = os.path.split(sys.argv[0])[0]
  # Else the module was imported and it has a __file__ attribute that will be the full path of the module.
  else:
      path_here = os.path.split(__file__)[0]

  # configure logging
  loggerconfig_file_path = os.path.join(path_here, 'config/logging.json')
  # If applicable, delete the existing log file to generate a fresh log file during each execution
  #if path.isfile("subservologging.log"):
  #  remove("subservologging.log")
  with open(loggerconfig_file_path, 'r') as logging_configuration_file:
    config_dict = json.load(logging_configuration_file)
  logging.config.dictConfig(config_dict)
  # Log that the logger was configured
  logger = logging.getLogger(__name__)
  logger.info('Logging configured')

  # read config
  config_parser = configparser.RawConfigParser()
  config_file_path = os.path.join(path_here, 'config/parameters.conf')
  logger.info('Config path: {}'.format(config_file_path))
  try:
    config_parser.read(config_file_path)
    credentials_path = config_parser['telemetry']['credentials_path']
    logger.info('Read credentials path {}'.format(credentials_path))
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    project_id = config_parser['telemetry']['project_id']
    topic_id = config_parser['telemetry']['topic_id']
    logger.info('Read pubsub project {}, and topic {}'.format(project_id, topic_id))
  except:
    logger.error('Exception when reading telemetry parameters from {}'.format(config_file_path))
  try:
    config_parser.read(config_file_path)
    tilt_pin = int(config_parser['io']['tilt_pin'])
    pan_pin = int(config_parser['io']['pan_pin'])
    tilt_ratio = float(config_parser['io']['tilt_ratio'])
    pan_ratio = float(config_parser['io']['pan_ratio'])
    tilt_servo_max_pw = float(config_parser['io']['tilt_servo_max_pw'])
    tilt_servo_min_pw = float(config_parser['io']['tilt_servo_min_pw'])
    pan_servo_max_pw = float(config_parser['io']['pan_servo_max_pw'])
    pan_servo_min_pw = float(config_parser['io']['pan_servo_min_pw'])
    tilt_max_angle = float(config_parser['io']['tilt_max_angle'])
    tilt_min_angle = float(config_parser['io']['tilt_min_angle'])
    pan_max_angle = float(config_parser['io']['pan_max_angle'])
    pan_min_angle = float(config_parser['io']['pan_min_angle'])
    logger.info('Tilt pin {}, servo ratio {}, servo max pw {}, servo min pw {}, max angle {}, min angle {}'.format(tilt_pin, tilt_ratio, tilt_servo_max_pw, tilt_servo_min_pw, tilt_max_angle, tilt_min_angle))
    logger.info('Pan pin {}, servo ratio {}, servo max pw {}, servo min pw {}, max angle {}, min angle {}'.format(pan_pin, pan_ratio, pan_servo_max_pw, pan_servo_min_pw, pan_max_angle, pan_min_angle))
  except:
    logger.error('Exception when reading io parameters from {}'.format(config_file_path))

  # sanity check
  if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
    logger.info('$GOOGLE_APPLICATION_CREDENTIALS: {}'.format(os.environ['GOOGLE_APPLICATION_CREDENTIALS']))
  else:
    logger.error('Could not find $GOOGLE_APPLICATION_CREDENTIALS')
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
    logger.info('Failed creating subscription: {}'.format(e))
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
    logger.error('Failed subscribing to {}'.format(subscription_path))
  #  [END main]

def __subscriber_callback(message):
  # [START __subscriber_callback]
  global tilt_servo_max_pw
  global tilt_servo_min_pw
  global tilt_max_angle
  global tilt_min_angle
  global tilt_ratio
  global tilt_pin
  global pan_servo_max_pw
  global pan_servo_min_pw
  global pan_max_angle
  global pan_min_angle
  global pan_ratio
  global pan_pin

  logger = logging.getLogger(__name__)

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
  try:
    logger.debug('PubSub message received')
    data = json.loads(message.data)
    if data['head'].get('type') != 'goggle_direction':
      logger.debug('Unknown message type')
      message.ack()
      return
  except:
    logger.error('Could not understand message: {}'.format(message.data))
    message.ack()
    return
  try:
    if data['head'].get('last_seen') < __subscriber_callback.last_seen:
      logger.debug('Skip this message - out of sequence, head: {}, last seen: {}'.format(data['head']['last_seen'], __subscriber_callback.last_seen))
      message.ack()
      return
  except AttributeError:
    logger.debug('First message since the start')
  except KeyError:
    logger.info('Message does not contain head.last_seen. Skip this')
    message.ack()
    return
  except:
    logger.error('Some weird exception checking the pubsub message head.last_seen. Skip this')
    message.ack()
    return
  __subscriber_callback.last_seen = data['head']['last_seen']
  #logger.debug('Last seen {}'.format(__subscriber_callback.last_seen))

  try:
    __set_angle(tilt_pin, -data['body']['roll'], tilt_ratio, tilt_servo_max_pw, tilt_servo_min_pw, tilt_max_angle, tilt_min_angle)
    __set_angle(pan_pin, data['body']['yaw'], pan_ratio, pan_servo_max_pw, pan_servo_min_pw, pan_max_angle, pan_min_angle)
  except Exception as e:
    logger.error('Failed to set tilt/pan: {}'.format(e))
  message.ack()
  # [END __subscriber_callback]

def __set_angle(pin, angle, ratio, max_pw, min_pw, max_angle, min_angle):
  # [START __set_angle]
  logger = logging.getLogger(__name__)

  logger.debug('Angle {} on pin {}'.format(angle, pin))
  if angle < min_angle:
    angle = min_angle
    logger.debug('Truncate angle < min')
  elif angle > max_angle:
    angle = max_angle
    logger.debug('Truncate angle > max')

  #angle_scaled = angle * ratio
  #logger.debug('Angle scaled {}'.format(angle_scaled))
  servo_delta = max_pw - min_pw
  angle_delta = max_angle - min_angle
  pw = ((angle - min_angle) * servo_delta / angle_delta) + min_pw
  #logger.debug('PW {} pin {}'.format(pw, pin))
  wiringpi.pwmWrite(pin, int(pw))
  # [END __set_angle]

if __name__ == '__main__':
  main()
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

import datetime
import jwt
import paho.mqtt.client as mqtt
import random
import ssl

__version__ = '0.0.1'

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

# The initial backoff time after a disconnection occurs, in seconds.
minimum_backoff_time = 1
# The maximum backoff time before giving up, in seconds.
MAXIMUM_BACKOFF_TIME = 32
# Whether to wait with exponential backoff before publishing.
should_backoff = False

# [START iot_mqtt_jwt]
def create_jwt(project_id, private_key_file, algorithm):
  """Creates a JWT (https://jwt.io) to establish an MQTT connection.
      Args:
        project_id: The cloud project ID this device belongs to
        private_key_file: A path to a file containing either an RSA256 or
                ES256 private key.
        algorithm: The encryption algorithm to use. Either 'RS256' or 'ES256'
      Returns:
          An MQTT generated from the given project_id and private key, which
          expires in 20 minutes. After 20 minutes, your client will be
          disconnected, and a new JWT will have to be generated.
      Raises:
          ValueError: If the private_key_file does not contain a known key.
      """
  logger = logging.getLogger(__name__)

  token = {
          # The time that the token was issued at
          'iat': datetime.datetime.utcnow(),
          # The time the token expires.
          'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60),
          # The audience field should always be set to the GCP project id.
          'aud': project_id
  }

  # Read the private key file.
  with open(private_key_file, 'r') as f:
    private_key = f.read()

  logger.info('Creating JWT using {} from private key file {}'.format(algorithm, private_key_file))

  return jwt.encode(token, private_key, algorithm=algorithm)
# [END iot_mqtt_jwt]

# [START iot_mqtt_config]
def error_str(rc):
  """Convert a Paho error to a human readable string."""
  return '{}: {}'.format(rc, mqtt.error_string(rc))


def on_connect(unused_client, unused_userdata, unused_flags, rc):
  """Callback for when a device connects."""
  logger = logging.getLogger(__name__)

  logger.info('MQTT on_connect {}'.format(mqtt.connack_string(rc)))

  # After a successful connect, reset backoff time and stop backing off.
  global should_backoff
  global minimum_backoff_time
  should_backoff = False
  minimum_backoff_time = 1


def on_disconnect(unused_client, unused_userdata, rc):
  """Paho callback for when a device disconnects."""
  logger = logging.getLogger(__name__)

  logger.info('MQTT on_disconnect {}'.format(error_str(rc)))
  # Since a disconnect occurred, the next loop iteration will wait with exponential backoff.
  global should_backoff
  should_backoff = True


def on_publish(unused_client, unused_userdata, unused_mid):
  """Paho callback when a message is sent to the broker."""
  logger = logging.getLogger(__name__)

  logger.info('MQTT on_publish')


def on_message(unused_client, unused_userdata, message):
  """Callback when the device receives a message on a subscription."""
  logger = logging.getLogger(__name__)

  payload = str(message.payload)
  logger.debug('Received message \'{}\' on topic \'{}\' with Qos {}'.format(
              payload, message.topic, str(message.qos)))

  __decode_message(payload)


def get_client(project_id, cloud_region, registry_id, device_id, private_key_file,
               algorithm, ca_certs, mqtt_bridge_hostname, mqtt_bridge_port):
  """Create our MQTT client. The client_id is a unique string that identifies
  this device. For Google Cloud IoT Core, it must be in the format below."""
  logger = logging.getLogger(__name__)

  client_id = 'projects/{}/locations/{}/registries/{}/devices/{}'.format(
              project_id, cloud_region, registry_id, device_id)
  logger.info('Device client_id is \'{}\''.format(client_id))

  client = mqtt.Client(client_id=client_id)

  # With Google Cloud IoT Core, the username field is ignored, and the
  # password field is used to transmit a JWT to authorize the device.
  client.username_pw_set(username='unused',
                         password=create_jwt(project_id, private_key_file, algorithm))

  # Enable SSL/TLS support.
  client.tls_set(ca_certs=ca_certs, tls_version=ssl.PROTOCOL_TLSv1_2)

  # Register message callbacks. https://eclipse.org/paho/clients/python/docs/
  # describes additional callbacks that Paho supports. In this example, the
  # callbacks just print to standard out.
  client.on_connect = on_connect
  client.on_publish = on_publish
  client.on_disconnect = on_disconnect
  client.on_message = on_message

  # Connect to the Google MQTT bridge.
  client.connect(mqtt_bridge_hostname, mqtt_bridge_port)

  # This is the topic that the device will receive configuration updates on.
  mqtt_config_topic = '/devices/{}/config'.format(device_id)

  # Subscribe to the config topic.
  client.subscribe(mqtt_config_topic, qos=1)

  # The topic that the device will receive commands on.
  mqtt_command_topic = '/devices/{}/commands/#'.format(device_id)

  # Subscribe to the commands topic, QoS 1 enables message acknowledgement.
  logger.info('Subscribing to {}'.format(mqtt_command_topic))
  client.subscribe(mqtt_command_topic, qos=0)

  return client
# [END iot_mqtt_config]


def detach_device(client, device_id):
  """Detach the device from the gateway."""
  # [START iot_detach_device]
  logger = logging.getLogger(__name__)

  detach_topic = '/devices/{}/detach'.format(device_id)
  logger.info('Detaching: {}'.format(detach_topic))
  client.publish(detach_topic, '{}', qos=1)
  # [END iot_detach_device]


def attach_device(client, device_id, auth):
  """Attach the device to the gateway."""
  # [START iot_attach_device]
  attach_topic = '/devices/{}/attach'.format(device_id)
  attach_payload = '{{"authorization" : "{}"}}'.format(auth)
  client.publish(attach_topic, attach_payload, qos=1)
  # [END iot_attach_device]


def listen_for_messages(
      service_account_json, project_id, cloud_region, registry_id, device_id,
      gateway_id, private_key_file, algorithm, ca_certs,
      mqtt_bridge_hostname, mqtt_bridge_port, jwt_expires_minutes, cb=None):
  """Listens for messages sent to the gateway and bound devices."""
  # [START iot_listen_for_messages]
  global minimum_backoff_time
  
  logger = logging.getLogger(__name__)

  jwt_iat = datetime.datetime.utcnow()
  jwt_exp_mins = jwt_expires_minutes
  # Use gateway to connect to server
  client = get_client(project_id, cloud_region, registry_id, gateway_id,
                      private_key_file, algorithm, ca_certs, mqtt_bridge_hostname,
                      mqtt_bridge_port)

  attach_device(client, device_id, '')
  logger.debug('Waiting for device to attach')
  time.sleep(5)

  # The topic devices receive configuration updates on.
  device_config_topic = '/devices/{}/config'.format(device_id)
  client.subscribe(device_config_topic, qos=1)

  # The topic gateways receive configuration updates on.
  gateway_config_topic = '/devices/{}/config'.format(gateway_id)
  client.subscribe(gateway_config_topic, qos=1)

  # The topic gateways receive error updates on. QoS must be 0.
  error_topic = '/devices/{}/errors'.format(gateway_id)
  client.subscribe(error_topic, qos=0)

  while True:
    try:
      client.loop()
      if cb is not None:
        cb(client)

      if should_backoff:
        # If backoff time is too large, give up.
        if minimum_backoff_time > MAXIMUM_BACKOFF_TIME:
          logger.info('Exceeded maximum backoff time. Giving up')
          break

        delay = minimum_backoff_time + random.randint(0, 1000) / 1000.0
        time.sleep(delay)
        minimum_backoff_time *= 2
        client.connect(mqtt_bridge_hostname, mqtt_bridge_port)

      seconds_since_issue = (datetime.datetime.utcnow() - jwt_iat).seconds
      if seconds_since_issue > 60 * jwt_exp_mins:
        logger.info('Refreshing token after {}s'.format(seconds_since_issue))
        jwt_iat = datetime.datetime.utcnow()
        client = get_client(project_id, cloud_region, registry_id, gateway_id,
                            private_key_file, algorithm, ca_certs, mqtt_bridge_hostname,
                            mqtt_bridge_port)

      time.sleep(1)

    except KeyboardInterrupt:
      detach_device(client, device_id)
      logger.info('Keyboard interrupt')
      raise
    except Exception as e:
      logger.error('Exception in listen loop {}'.format(e))

  logger.info('Exiting MQTT listener')
  # [END iot_listen_for_messages]

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

  global minimum_backoff_time
  global MAXIMUM_BACKOFF_TIME

  #If the module is executed as a script __name__ will be '__main__' and sys.argv[0] will be the full path of the module.
  if __name__ == '__main__':
    path_here = os.path.split(sys.argv[0])[0]
  #Else the module was imported and it has a __file__ attribute that will be the full path of the module.
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

  # MQTT
  try:
    cloud_region = 'europe-west1'
    registry_id = 'goggle-registry'
    device_id = 'orqa-goggles-prototype-0001'
    #mqtt_topic = '/devices/{}/{}'.format(device_id, 'events') #or 'state'
    private_key_file = '/config/ec2_private.pem'

    jwt_iat = datetime.datetime.utcnow()
    jwt_exp_mins = 20
    client = get_client(project_id, cloud_region, registry_id,
                        device_id, private_key_file, 'RS256', #or 'ES256'
                        'roots.pem', 'mqtt.googleapis.com', '8883') #or 443
    listen_for_messages(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"), project_id,
                        cloud_region, registry_id, device_id,
                        None, private_key_file,
                        'RS256', 'roots.pem', 'mqtt.googleapis.com',
                        '8883', jwt_exp_mins)    
  except Exception as e:
    logger.info('Failed setting up MQTT listener: {}'.format(e))
  logger.info('Exiting')
  #  [END main]

def __decode_message(message):
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
  
  # Message format:
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
    data = json.loads(message)
    if data['head'].get('type') != 'goggle_direction':
      logger.debug('Unknown message type')
      message.ack()
      return
  except:
    logger.error('Could not understand message: {}'.format(message))
    message.ack()
    return
  try:
    if data['head'].get('last_seen') < __decode_message.last_seen:
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
  __decode_message.last_seen = data['head']['last_seen']
  #logger.debug('Last seen {}'.format(__decode_message.last_seen))

  try:
    __set_angle(tilt_pin, data['body']['pitch'], tilt_ratio, tilt_servo_max_pw, tilt_servo_min_pw, tilt_max_angle, tilt_min_angle)
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
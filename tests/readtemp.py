#!/usr/bin/env python

#---------------------------------------------------------------------------# 
# DHT sensor configuration
#---------------------------------------------------------------------------#
import sys
import Adafruit_DHT

sensor = Adafruit_DHT.DHT11
#GPIO23, PIN 16
pin = 23

while True:

  humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
  # Note that sometimes you won't get a reading and
  # the results will be null (because Linux can't
  # guarantee the timing of calls to read the sensor).  
  # If this happens try again!
  if humidity is None or temperature is None:
    print 'Temp={0:0.1f}*  Humidity={1:0.1f}%'.format(temperature, humidity)

  if humidity is None or temperature is None:
    humidity, temperature = (0, 0)

  print 'Temp={0:0.1f}*  Humidity={1:0.1f}%'.format(temperature, humidity)




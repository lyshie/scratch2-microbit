#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import serial

if os.name == "nt":
    PORT = "COM7"
else:
    PORT = "/dev/ttyACM0"
#
BAUD = 115200
s = serial.Serial(PORT)
s.baudrate = BAUD
s.parity = serial.PARITY_NONE
s.databits = serial.EIGHTBITS
s.stopbits = serial.STOPBITS_ONE

while True:
    x = raw_input("String: ")
    try:
        s.write(x)
    except:
        pass

s.close()

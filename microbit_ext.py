# coding=utf-8
from __future__ import unicode_literals

import os
from blockext import *
import serial
import thread

acc_x = 0
acc_y = 0
acc_z = 0

class MicroBit:

    def __init__(self):
        pass

    def _on_reset(self):
        print("""
        Reset! The red stop button has been clicked,
        And now everything is how it was.
        """)

    @reporter("acc_x")
    def acc_x(self):
        return acc_x

    @reporter("acc_y")
    def acc_y(self):
        return acc_y

    @reporter("acc_z")
    def acc_z(self):
        return acc_z

def serial_proc():
    global acc_x
    global acc_y
    global acc_z

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
        data = s.readline().decode('UTF-8')
        data_list = data.rstrip().split(' ')
        try:
            x, y, z, a, b = data_list
            acc_x = x
            acc_y = y
            acc_z = z
            print(x, y, z)
        except:
            pass
    s.close()

def run_server():
    extension.run_forever(debug=True)

def get_decorated_blocks_from_class(cls, selectors=None):
    if selectors:
        cls_vars = vars(cls)
        values = map(cls_vars.get, selectors)
    else:
        values = vars(cls).values()

    functions = []
    for value in values:
        if callable(value) and hasattr(value, '_block'):
            functions.append(value)
    functions.sort(key=lambda func: func._block_id)
    return [f._block for f in functions]

descriptor = Descriptor(
        name="Simple Micro:bit Extension",
        port=12345,
        blocks=get_decorated_blocks_from_class(MicroBit),
        menus=dict(
            )
        )

extension = Extension(MicroBit, descriptor)


if __name__ == "__main__":
    try:
        thread.start_new_thread(serial_proc,())
        thread.start_new_thread(run_server,())
    except:
        pass

    while 1:
        pass

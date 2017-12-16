# coding=utf-8
'''
$ sudo python ./microbit_ext_ble.py D6:AF:43:58:57:9F
'''
from __future__ import unicode_literals

import os
import sys
from blockext import *
import thread

'''
URL:
    https://github.com/peplin/pygatt
'''
import pygatt
import time
from pygatt.util import *
import binascii

acc_x = 0
acc_y = 0
acc_z = 0
button_a = 0
button_b = 0


class MicroBit:

    def __init__(self):
        pass

    def _on_reset(self):
        print("""
        Reset! The red stop button has been clicked,
        And now everything is how it was.
        """)

    @reporter("button_a")
    def button_a(self):
        return button_a

    @reporter("button_b")
    def button_b(self):
        return button_b

    @reporter("acc_x")
    def acc_x(self):
        return acc_x

    @reporter("acc_y")
    def acc_y(self):
        return acc_y

    @reporter("acc_z")
    def acc_z(self):
        return acc_z

'''
URL:
    https://lancaster-university.github.io/microbit-docs/resources/bluetooth/bluetooth_profile.html
    https://lancaster-university.github.io/microbit-docs/ble/profile/#gatt-services
'''
BLE_CHAR = {
    # 0 = not pressed, 1 = pressed, 2 = long
    'BUTTON_A': 'E95DDA90-251D-470A-A062FA1922DFA9A8',
    'BUTTON_B': 'E95DDA91-251D-470A-A062FA1922DFA9A8',
    # Signed integer 8 bit value in degrees celsius
    'TEMPERATURE':    'E95D9250-251D-470A-A062FA1922DFA9A8',
    # X, Y, Z => 3 signed 16 bit values
    'ACCELEROMETER':  'E95DCA4B-251D-470A-A062FA1922DFA9A8',
    # 1, 2, 5, 10, 20, 80, 160 and 640
    'ACCELEROMETER_PERIOD':  'E95DFB24-251D-470A-A062FA1922DFA9A8',
}


def hex2int(byte_array):
    v = binascii.hexlify(byte_array)
    return v


def hex2sint(byte_array):
    v = int(binascii.hexlify(byte_array), 16)
    if v & 0x8000 == 0x8000:
        v = -((v ^ 0xffff) + 1)
    return v


def handle_button_a(handle, value):
    global button_a
    button_a = hex2int(value)


def handle_button_b(handle, value):
    global button_b
    button_b = hex2int(value)


def handle_accelerometer(handle, value):
    '''
    URL:
        http://microbit-challenges.readthedocs.io/en/latest/tutorials/accelerometer.html
        https://os.mbed.com/users/fbeaufort/code/microbit-ble-open/file/04376b21995b/source/drivers/MicroBitAccelerometer.cpp/
    '''
    global acc_x
    global acc_y
    global acc_z

    acc_x = hex2sint(bytearray([value[1], value[0]]))
    acc_y = hex2sint(bytearray([value[3], value[2]]))
    acc_z = hex2sint(bytearray([value[5], value[4]]))


def ble_proc():
    # adapter = pygatt.BGAPIBackend()
    adapter = pygatt.GATTToolBackend()

    try:
        adapter.start()
        device = adapter.connect(
            sys.argv[1], address_type=pygatt.BLEAddressType.random)
        device.subscribe(BLE_CHAR['BUTTON_A'],
                         callback=handle_button_a)
        device.subscribe(BLE_CHAR['BUTTON_B'],
                         callback=handle_button_b)
        device.subscribe(BLE_CHAR['ACCELEROMETER'],
                         callback=handle_accelerometer)
        while True:
            time.sleep(0.01)
    finally:
        adapter.stop()


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
    name="Simple Micro:bit Extension (BLE)",
    port=12345,
    blocks=get_decorated_blocks_from_class(MicroBit),
    menus=dict(
    )
)

extension = Extension(MicroBit, descriptor)


if __name__ == "__main__":
    try:
        thread.start_new_thread(ble_proc, ())
        thread.start_new_thread(run_server, ())
    except:
        pass

    while True:
        time.sleep(0.01)

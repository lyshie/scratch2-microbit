# coding=utf-8
'''
$ sudo python ./microbit_ext_ble.py D6:AF:43:58:57:9F
'''
from __future__ import unicode_literals

import os
import sys
import re
import time
import _thread

# Scratch 2.0 extension
from blockext import *

# Python wrapper for gatttool
# https://github.com/peplin/pygatt
import pygatt
from pygatt.util import *
import binascii

# Thread-safe list-like container
from collections import deque


class MicroBit(object):
    '''
    References:
        1. Bluetooth Developer Studio Level 3 Profile Report
           https://lancaster-university.github.io/microbit-docs/resources/bluetooth/bluetooth_profile.html
        2. BBC micro:bit Bluetooth Profile - GATT Services
        https://lancaster-university.github.io/microbit-docs/ble/profile/#gatt-services
    '''
    BLE_UUID = {
        # uint8 (0 = not pressed, 1 = pressed, 2 = long)
        'BUTTON_A_STATE': 'E95DDA90-251D-470A-A062FA1922DFA9A8',
        'BUTTON_B_STATE': 'E95DDA91-251D-470A-A062FA1922DFA9A8',
        # sint8 (degrees celsius)
        'TEMPERATURE':    'E95D9250-251D-470A-A062FA1922DFA9A8',
        # uint16 (milliseconds)
        'TEMPERATURE_PERIOD':    'E95D1B25-251D-470A-A062FA1922DFA9A8',
        # sint16, sint16, sint16 (X, Y, Z) should be divided by 1000
        'ACCELEROMETER':  'E95DCA4B-251D-470A-A062FA1922DFA9A8',
        # uint16 (1, 2, 5, 10, 20, 80, 160 and 640)
        'ACCELEROMETER_PERIOD':  'E95DFB24-251D-470A-A062FA1922DFA9A8',
        # utf8s (maximum length 20 octets)
        'LED_TEXT': 'E95D93EE-251D-470A-A062FA1922DFA9A8',
        # uint8[]
        # arrow left
        # 000_0_0100 => 0x40
        # 000_0_1000 => 0x80
        # 000_1_1111 => 0x1F
        # 000_0_1000 => 0x80
        # 000_0_0100 => 0x40
        'LED_MATRIX_STATE': 'E95D7B77-251D-470A-A062FA1922DFA9A8',
        # sint16, sint16, sint16 (X, Y, Z)
        'MAGNETOMETER': 'E95DFB11-251D-470A-A062FA1922DFA9A8',
        # uint16 (1, 2, 5, 10, 20, 80, 160 and 640)
        'MAGNETOMETER_PERIOD': 'E95D386C-251D-470A-A062FA1922DFA9A8',
        # uint16 (degrees from North)
        'MAGNETOMETER_BEARING': 'E95D9715-251D-470A-A062FA1922DFA9A8',
    }

    ACCELEROMETER_TILT_TOLERANCE = 200

    LED_STATE = [
        "0 (-----)",
        "1 (----*)",
        "2 (---*-)",
        "4 (--*--)",
        "8 (-*---)",
        "16 (*----)",
        "24 (*****)",
    ]

    LED_MATRIX_PATTERN = {
        'Arrow Left': bytearray([0x04, 0x08, 0x1F, 0x08, 0x04]),  # <-
        'Arrow Right': bytearray([0x04, 0x02, 0x1F, 0x02, 0x04]),  # ->
        'Arrow Up': bytearray([0x04, 0x0E, 0x15, 0x04, 0x04]),
        'Arrow Down': bytearray([0x04, 0x04, 0x15, 0x0E, 0x04]),
        'Yes': bytearray([0x00, 0x01, 0x02, 0x14, 0x08]),  # v
        'No': bytearray([0x11, 0x0A, 0x04, 0x0A, 0x11]),  # x
        'Square (Large)': bytearray([0x1F, 0x11, 0x11, 0x11, 0x1F]),
        'Square (Medium)': bytearray([0x00, 0x0E, 0x0A, 0x0E, 0x00]),
        'Square (Small)': bytearray([0x00, 0x00, 0x04, 0x00, 0x00]),
    }

    def __init__(self, mac_address):
        # bluetooth MAC address
        self.mac_address = mac_address

        # accelerometer
        self.acc_x = 0
        self.acc_y = 0
        self.acc_z = 0

        # magnetometer
        self.mag_x = 0
        self.mag_y = 0
        self.mag_z = 0
        self.mag_bearing = 0

        # button a and b
        self.button_a = 0
        self.button_b = 0

        # temperature
        self.temperature = 0

        # bluetooth device
        self.device = None

        # command output buffer to microbit
        self.command_queue = deque(list(), maxlen=100)

    def hex2uint(self, byte_array):
        '''Convert bytearray to unsigned integer (8 bits, 16 bits)'''
        v = int(binascii.hexlify(byte_array), 16)
        return v

    def hex2sint(self, byte_array):
        '''Convert bytearray to signed integer (16bits)'''
        v = int(binascii.hexlify(byte_array), 16)
        if v & 0x8000 == 0x8000:
            v = -((v ^ 0xffff) + 1)
        return v

    def handle_button_a(self, handle, value):
        '''callback for button_a state'''
        self.button_a = self.hex2uint(bytearray([value[0]]))

    def handle_button_b(self, handle, value):
        '''callback for button_b state'''
        self.button_b = self.hex2uint(bytearray([value[0]]))

    def handle_accelerometer(self, handle, value):
        '''callback for accelerometer'''
        '''
        References:
            1. MicroPython - Accelerometer
               http://microbit-challenges.readthedocs.io/en/latest/tutorials/accelerometer.html
            2. MBed OS - source/drivers/MicroBitAccelerometer.cpp
               https://os.mbed.com/users/fbeaufort/code/microbit-ble-open/file/04376b21995b/source/drivers/MicroBitAccelerometer.cpp/
        '''
        self.acc_x = self.hex2sint(bytearray([value[1], value[0]]))
        self.acc_y = self.hex2sint(bytearray([value[3], value[2]]))
        self.acc_z = self.hex2sint(bytearray([value[5], value[4]]))

    def handle_temperature(self, handle, value):
        '''callback for temperature'''
        self.temperature = self.hex2sint(bytearray([value[0]]))

    def handle_magnetometer(self, handle, value):
        '''callback for magnetometer'''
        '''
        References:
            1. Create a Digital Compass with the Raspberry Pi – Part 2 – “Tilt Compensation”
               http://ozzmaker.com/compass2/
        '''
        self.mag_x = self.hex2sint(bytearray([value[1], value[0]]))
        self.mag_y = self.hex2sint(bytearray([value[3], value[2]]))
        self.mag_z = self.hex2sint(bytearray([value[5], value[4]]))

    def handle_magnetometer_bearing(self, handle, value):
        '''callback for magnetometer bearing'''
        self.mag_bearing = self.hex2uint(bytearray([value[1], value[0]]))

# global instance of MicroBit
microbit = MicroBit(sys.argv[1])


class MicroBitExtension:

    def __init__(self):
        '''
            bind the global instance of MicroBit
        '''
        self.microbit = microbit

    def _on_reset(self):
        print("""
        Reset! The red stop button has been clicked,
        And now everything is how it was.
        """)

    @reporter("Button A")
    def button_a(self):
        return self.microbit.button_a

    @reporter("Button B")
    def button_b(self):
        return self.microbit.button_b

    @predicate("Tilted Left?")
    def tilt_left(self):
        return self.microbit.acc_x < (0 - MicroBit.ACCELEROMETER_TILT_TOLERANCE)

    @predicate("Tilted Right?")
    def tilt_right(self):
        return self.microbit.acc_x > MicroBit.ACCELEROMETER_TILT_TOLERANCE

    @predicate("Tilted Down?")
    def tilt_down(self):
        return self.microbit.acc_y < (0 - MicroBit.ACCELEROMETER_TILT_TOLERANCE)

    @predicate("Tilted Up?")
    def tilt_up(self):
        return self.microbit.acc_y > MicroBit.ACCELEROMETER_TILT_TOLERANCE

    @predicate("Face Up?")
    def face_up(self):
        return self.microbit.acc_z < (0 - MicroBit.ACCELEROMETER_TILT_TOLERANCE)

    @predicate("Face Down?")
    def face_down(self):
        return self.microbit.acc_z > MicroBit.ACCELEROMETER_TILT_TOLERANCE

    @reporter("X-Accelerometer")
    def acc_x(self):
        return self.microbit.acc_x

    @reporter("Y-Accelerometer")
    def acc_y(self):
        return self.microbit.acc_y

    @reporter("Z-Accelerometer")
    def acc_z(self):
        return self.microbit.acc_z

    @reporter("Temperature")
    def temperature_celsius(self):
        return self.microbit.temperature

    @command("Scroll %s")
    def scroll_text(self, text="HELLO"):
        self.microbit.command_queue.append("scroll_text\0{}".format(text))

    @command("Set LED Matrix %m.matrix_pattern")
    def led_matrix_pattern(self, matrix_pattern):
        self.microbit.command_queue.append(
            "led_matrix_pattern\0{}".format(matrix_pattern))

    @command("Set LED Matrix %d.led_row1 %d.led_row2 %d.led_row3 %d.led_row4 %d.led_row5")
    def led_matrix(self, led_row1=0, led_row2=0, led_row3=0, led_row4=0, led_row5=0):
        led_row1 = re.sub(r"\D", "", led_row1)
        led_row2 = re.sub(r"\D", "", led_row2)
        led_row3 = re.sub(r"\D", "", led_row3)
        led_row4 = re.sub(r"\D", "", led_row4)
        led_row5 = re.sub(r"\D", "", led_row5)
        self.microbit.command_queue.append("led_matrix\0{}\0{}\0{}\0{}\0{}".format(
            led_row1, led_row2, led_row3, led_row4, led_row5))

    @command("Clear Display %d.clear_type")
    def clear_display(self, clear_type=0):
        clear_type = re.sub(r"\D", "", clear_type)
        self.microbit.command_queue.append(
            "clear_display\0{}".format(clear_type))

    @reporter("X-Magnetometer")
    def mag_x(self):
        return self.microbit.mag_x

    @reporter("Y-Magnetometer")
    def mag_y(self):
        return self.microbit.mag_y

    @reporter("Z-Magnetometer")
    def mag_z(self):
        return self.microbit.mag_z

    @reporter("Bearing-Magnetometer")
    def mag_bearing(self):
        return self.microbit.mag_bearing


def ble_proc():
    # adapter = pygatt.BGAPIBackend()
    adapter = pygatt.GATTToolBackend()

    try:
        adapter.start()
        device = adapter.connect(
            microbit.mac_address, address_type=pygatt.BLEAddressType.random)
        device.subscribe(MicroBit.BLE_UUID['BUTTON_A_STATE'],
                         callback=microbit.handle_button_a)
        device.subscribe(MicroBit.BLE_UUID['BUTTON_B_STATE'],
                         callback=microbit.handle_button_b)
        device.subscribe(MicroBit.BLE_UUID['ACCELEROMETER'],
                         callback=microbit.handle_accelerometer)
        device.subscribe(MicroBit.BLE_UUID['TEMPERATURE'],
                         callback=microbit.handle_temperature)
        device.subscribe(MicroBit.BLE_UUID['MAGNETOMETER'],
                         callback=microbit.handle_magnetometer)
        device.subscribe(MicroBit.BLE_UUID['MAGNETOMETER_BEARING'],
                         callback=microbit.handle_magnetometer_bearing)

        microbit.device = device

        while True:
            try:
                cmd_line = microbit.command_queue.pop()
                process_command(cmd_line)
            except:
                pass
            time.sleep(0.01)
    finally:
        adapter.stop()


def process_command(cmd_line):
    if microbit.device is None:
        return

    items = cmd_line.split("\0")

    cmd = ""
    args = ""

    if len(items) > 1:
        cmd = items[0]
        args = items[1:]
    else:
        return

    if cmd == "scroll_text":
        microbit.device.char_write(MicroBit.BLE_UUID['LED_TEXT'], bytearray(
            b"{}".format(args[0])), wait_for_response=False)
    elif cmd == "clear_display":
        if args[0] == "0":
            microbit.device.char_write(MicroBit.BLE_UUID['LED_MATRIX_STATE'], bytearray(
                [0x00, 0x00, 0x00, 0x00, 0x00]), wait_for_response=False)
        else:
            microbit.device.char_write(MicroBit.BLE_UUID['LED_MATRIX_STATE'], bytearray(
                [0xFF, 0xFF, 0xFF, 0xFF, 0xFF]), wait_for_response=False)
    elif cmd == "led_matrix":
        microbit.device.char_write(MicroBit.BLE_UUID['LED_MATRIX_STATE'], bytearray(
            [int(args[0]), int(args[1]), int(args[2]), int(args[3]), int(args[4])]), wait_for_response=False)
    elif cmd == "led_matrix_pattern":
        microbit.device.char_write(MicroBit.BLE_UUID['LED_MATRIX_STATE'], MicroBit.LED_MATRIX_PATTERN[
            args[0]], wait_for_response=False)
        value = microbit.device.char_read(
            MicroBit.BLE_UUID['LED_MATRIX_STATE'])


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
    blocks=get_decorated_blocks_from_class(MicroBitExtension),
    menus=dict(
        matrix_pattern=['Arrow Left', 'Arrow Right',
                        'Arrow Up', 'Arrow Down', "Yes", "No", "Square (Large)", "Square (Medium)", "Square (Small)"],
        clear_type=["0 (off)", "1 (on)"],
        led_row1=MicroBit.LED_STATE,
        led_row2=MicroBit.LED_STATE,
        led_row3=MicroBit.LED_STATE,
        led_row4=MicroBit.LED_STATE,
        led_row5=MicroBit.LED_STATE,
    )
)

extension = Extension(MicroBitExtension, descriptor)


if __name__ == "__main__":
    try:
        _thread.start_new_thread(ble_proc, ())
        _thread.start_new_thread(run_server, ())
    except:
        pass

    while True:
        time.sleep(0.01)

# coding=utf-8
'''
$ sudo python ./microbit_ext_ble.py D6:AF:43:58:57:9F
'''
from __future__ import unicode_literals

import os
import sys
import re
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

'''
Thread-Safe
'''
from collections import deque

command_queue = deque(list(), maxlen=100)

acc_x = 0
acc_y = 0
acc_z = 0
button_a = 0
button_b = 0
temperature = 0
device = None

MICROBIT_ACCELEROMETER_TILT_TOLERANCE = 200
LED_STATE = [
    "0 (-----)",
    "1 (----*)",
    "2 (---*-)",
    "4 (--*--)",
    "8 (-*---)",
    "16 (*----)",
    "24 (*****)",
]


class MicroBit:

    def __init__(self):
        pass

    def _on_reset(self):
        print("""
        Reset! The red stop button has been clicked,
        And now everything is how it was.
        """)

    @reporter("Button A")
    def button_a(self):
        return button_a

    @reporter("Button B")
    def button_b(self):
        return button_b

    @predicate("Tilted Left?")
    def tilt_left(self):
        return acc_x < (0 - MICROBIT_ACCELEROMETER_TILT_TOLERANCE)

    @predicate("Tilted Right?")
    def tilt_right(self):
        return acc_x > MICROBIT_ACCELEROMETER_TILT_TOLERANCE

    @predicate("Tilted Down?")
    def tilt_down(self):
        return acc_y < (0 - MICROBIT_ACCELEROMETER_TILT_TOLERANCE)

    @predicate("Tilted Up?")
    def tilt_up(self):
        return acc_y > MICROBIT_ACCELEROMETER_TILT_TOLERANCE

    @predicate("Face Up?")
    def face_up(self):
        return acc_z < (0 - MICROBIT_ACCELEROMETER_TILT_TOLERANCE)

    @predicate("Face Down?")
    def face_down(self):
        return acc_z > MICROBIT_ACCELEROMETER_TILT_TOLERANCE

    @reporter("X-Accelerometer")
    def acc_x(self):
        return acc_x

    @reporter("Y-Accelerometer")
    def acc_y(self):
        return acc_y

    @reporter("Z-Accelerometer")
    def acc_z(self):
        return acc_z

    @reporter("Temperature")
    def temperature_celsius(self):
        return temperature

    @command("Scroll %s")
    def scroll_text(self, text="HELLO"):
        command_queue.append("scroll_text\0{}".format(text))

    @command("Set LED Matrix %m.matrix_pattern")
    def led_matrix_pattern(self, matrix_pattern):
        command_queue.append("led_matrix_pattern\0{}".format(matrix_pattern))

    @command("Set LED Matrix %d.led_row1 %d.led_row2 %d.led_row3 %d.led_row4 %d.led_row5")
    def led_matrix(self, led_row1=0, led_row2=0, led_row3=0, led_row4=0, led_row5=0):
        led_row1 = re.sub(r"\D", "", led_row1)
        led_row2 = re.sub(r"\D", "", led_row2)
        led_row3 = re.sub(r"\D", "", led_row3)
        led_row4 = re.sub(r"\D", "", led_row4)
        led_row5 = re.sub(r"\D", "", led_row5)
        command_queue.append("led_matrix\0{}\0{}\0{}\0{}\0{}".format(
            led_row1, led_row2, led_row3, led_row4, led_row5))

    @command("Clear Display %d.clear_type")
    def clear_display(self, clear_type=0):
        clear_type = re.sub(r"\D", "", clear_type)
        command_queue.append("clear_display\0{}".format(clear_type))

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
    # UTF-8, Maximum length 20 octets.
    'LED_TEXT': 'E95D93EE-251D-470A-A062FA1922DFA9A8',
    'LED_MATRIX': 'E95D7B77-251D-470A-A062FA1922DFA9A8',
}

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


def handle_temperature(handle, value):
    global temperature
    temperature = hex2sint(value)


def ble_proc():
    global device
    global command_queue
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
        device.subscribe(BLE_CHAR['TEMPERATURE'],
                         callback=handle_temperature)

        while True:
            try:
                cmd_line = command_queue.pop()
                process_command(cmd_line)
            except:
                pass
            time.sleep(0.01)
    finally:
        adapter.stop()


def process_command(cmd_line):
    global device
    global LED_MATRIX_PATTERN

    if device is None:
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
        device.char_write(BLE_CHAR['LED_TEXT'], bytearray(
            b"{}".format(args[0])), wait_for_response=False)
    elif cmd == "clear_display":
        if args[0] == "0":
            device.char_write(BLE_CHAR['LED_MATRIX'], bytearray(
                [0x00, 0x00, 0x00, 0x00, 0x00]), wait_for_response=False)
        else:
            device.char_write(BLE_CHAR['LED_MATRIX'], bytearray(
                [0xFF, 0xFF, 0xFF, 0xFF, 0xFF]), wait_for_response=False)
    elif cmd == "led_matrix":
        device.char_write(BLE_CHAR['LED_MATRIX'], bytearray(
            [int(args[0]), int(args[1]), int(args[2]), int(args[3]), int(args[4])]), wait_for_response=False)
    elif cmd == "led_matrix_pattern":
        device.char_write(BLE_CHAR['LED_MATRIX'], LED_MATRIX_PATTERN[
                          args[0]], wait_for_response=False)
        value = device.char_read(BLE_CHAR['LED_MATRIX'])
        print("OK{}".format(binascii.hexlify(value)))


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
        matrix_pattern=['Arrow Left', 'Arrow Right',
                        'Arrow Up', 'Arrow Down', "Yes", "No", "Square (Large)", "Square (Medium)", "Square (Small)"],
        clear_type=["0 (off)", "1 (on)"],
        led_row1=LED_STATE,
        led_row2=LED_STATE,
        led_row3=LED_STATE,
        led_row4=LED_STATE,
        led_row5=LED_STATE,
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

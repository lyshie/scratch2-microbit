from microbit import *

while True:
    x = ""
    if uart.any():
        x = uart.readline()
        if x:
            display.scroll(x)

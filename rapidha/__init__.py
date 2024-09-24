# -*- coding: utf-8 -*-

import sys
import argparse
from rapidha import RapidHADevice

def main(argv=None):
    parser = argparse.ArgumentParser( prog="rapidha", description='Console interface to RapidHA serial device communication', epilog='')
    parser.add_argument('input', metavar='/dev/ttyUSB0', help="Serial TTY device")

    args = vars(parser.parse_args(argv[1:]))

    if args.input:
        run(args.input)
    else:
        parser.print_help()

def _printall(name, packet):
    print("%s - %s" % (name, repr(packet)))

def run(device):
    ra = RapidHADevice(device)
    ra.dispatch.register("printall", _printall, lambda packet: True)
    ra.start_thread()

    # Do other stuff in the main thread
    while True:
        time.sleep(.1)
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
           line = sys.stdin.readline().strip('\n')
           if line == "exit":
               break
           else:
               try:
                   method = getattr(ra, line)
                   method()
               except AttributeError:
                   print "Unknown command: " + line
    ra.halt()

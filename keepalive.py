#!/usr/bin/env python3
# oracle stops "idle" always-free VMs: cpu, network AND memory under 20 % for 7 days.
# ytmp34 barely uses cpu or network, so this holds 1.5 GB of ram (~35 % in total) and touches it now and then
# so it stays really in use. costs nothing else.
import time

MB = 1536
block = bytearray(MB * 1024 * 1024)
while True:
    for i in range(0, len(block), 4096):
        block[i] = (block[i] + 1) & 0xFF
    time.sleep(600)

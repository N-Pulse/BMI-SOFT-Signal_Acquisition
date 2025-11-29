#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LSL bridge for Upside Down Labs UNO R4 EMG firmware (6 channels, 500 Hz).
"""

import os
os.environ["LSL_NO_NETWORK"] = "1"  # keep LSL local (no multicast)

import time
import serial
from pylsl import StreamInfo, StreamOutlet

# ---------- CONFIGURE THIS ----------
PORT = "COM12"           # <-- COM port of the Arduino on COMPUTER B
BAUD = 230400            # must match your Arduino sketch
NUM_CHANNELS = 6
SAMPLE_RATE = 500.0      # Hz, from SAMP_RATE in Arduino code

SYNC_BYTE_1 = 0xC7
SYNC_BYTE_2 = 0x7C
END_BYTE    = 0x01
PACKET_LEN  = NUM_CHANNELS * 2 + 3 + 1   # 6*2 + 3 header + 1 end = 16
# ------------------------------------


def read_exact(ser, n):
    """Read exactly n bytes from serial (blocking until all are read)."""
    data = bytearray()
    while len(data) < n:
        chunk = ser.read(n - len(data))
        if not chunk:
            continue
        data.extend(chunk)
    return bytes(data)


def find_sync(ser):
    """Align to the C7 7C sync sequence, return a full 16-byte packet."""
    while True:
        b = ser.read(1)
        if not b:
            continue
        if b[0] != SYNC_BYTE_1:
            continue
        b2 = ser.read(1)
        if not b2 or b2[0] != SYNC_BYTE_2:
            # restart search
            continue
        # We have sync bytes, read the remaining bytes
        rest = read_exact(ser, PACKET_LEN - 2)
        return bytes([SYNC_BYTE_1, SYNC_BYTE_2]) + rest


def main():
    print(f"Opening serial port {PORT} at {BAUD} baud...")
    ser = serial.Serial(PORT, BAUD, timeout=0.1)
    time.sleep(0.5)

    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # ---- Handshake: WHORU ----
    ser.write(b"WHORU\n")
    time.sleep(0.1)
    reply = ser.read(ser.in_waiting or 1)
    print("Board replied to WHORU:", reply.decode(errors="ignore").strip())

    # ---- Start streaming ----
    ser.write(b"START\n")
    ser.flush()
    print("Sent START command, waiting for packets...")

    # ---- Create LSL stream ----
    info = StreamInfo(
        'EMG_Stream',      # name
        'EMG',             # type
        NUM_CHANNELS,      # number of channels
        SAMPLE_RATE,       # nominal sampling rate
        'float32',         # channel format
        'uno-r4-udl'       # source id
    )
    outlet = StreamOutlet(info)
    print("✅ LSL stream 'EMG_Stream' (6 ch, 500 Hz) created.")

    # ---- Align to first packet ----
    packet = find_sync(ser)
    print("Sync found, starting main loop...")

    sample_count = 0
    last_report = time.time()

    while True:
        # After first packet, just read fixed-size chunks
        packet = read_exact(ser, PACKET_LEN)

        # Basic sanity checks
        if packet[0] != SYNC_BYTE_1 or packet[1] != SYNC_BYTE_2 or packet[-1] != END_BYTE:
            # Lost sync; realign
            packet = find_sync(ser)
            continue

        # Parse 6 channel values (uint16)
        values = []
        offset = 3  # skip sync and counter
        for _ in range(NUM_CHANNELS):
            high = packet[offset]
            low  = packet[offset + 1]
            raw  = (high << 8) | low        # 0..16383 with 14-bit ADC
            values.append(float(raw))
            offset += 2

        outlet.push_sample(values)
        sample_count += 1

        # Print small status every second
        now = time.time()
        if now - last_report >= 1.0:
            print(f"  pushed {sample_count} EMG samples...")
            last_report = now


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopping bridge.")

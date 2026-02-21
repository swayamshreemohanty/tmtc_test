"""
uart_reader.py
--------------
Reads raw bytes from the hardware UART (/dev/serial0) and displays every
common interpretation of the incoming data:

  - Raw hex dump
  - Unsigned integers  (8 / 16 / 32 / 64-bit, little-endian & big-endian)
  - Signed integers    (8 / 16 / 32 / 64-bit, little-endian & big-endian)
  - IEEE-754 floats    (32-bit & 64-bit, little-endian & big-endian)
  - Binary bit-pattern
  - ASCII / UTF-8 text (where printable)
"""

import serial
import struct
import time
import sys

# ── Configuration ────────────────────────────────────────────────────────────
UART_PORT  = '/dev/serial0'
BAUD_RATE  = 921600
TIMEOUT_S  = 1.0          # read() timeout in seconds
READ_CHUNK = 256           # max bytes to pull per iteration
# ─────────────────────────────────────────────────────────────────────────────


def hex_dump(data: bytes) -> str:
    """Return a formatted hex dump: '0A 1B 2C 3D ...'"""
    return ' '.join(f'{b:02X}' for b in data)


def bin_dump(data: bytes) -> str:
    """Return binary representation of every byte: '00001010 00011011 ...'"""
    return ' '.join(f'{b:08b}' for b in data)


def ascii_repr(data: bytes) -> str:
    """Return printable ASCII characters; replace non-printable with '.'"""
    return ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)


def decode_ints(data: bytes) -> dict:
    """
    Try to decode the byte buffer as every standard integer width,
    both signed and unsigned, both endiannesses.
    Only returns widths that fit exactly into the buffer length.
    """
    n   = len(data)
    out = {}

    widths = {1: 'B', 2: 'H', 4: 'I', 8: 'Q'}   # unsigned struct codes
    signed = {1: 'b', 2: 'h', 4: 'i', 8: 'q'}   # signed struct codes

    for size, code in widths.items():
        if n >= size:
            # Use only the first <size> bytes for fixed-width reads,
            # but also try to interpret the whole buffer when it matches.
            chunk_le = data[:size]
            chunk_be = data[:size]
            u_le = struct.unpack_from('<' + code, chunk_le)[0]
            u_be = struct.unpack_from('>' + code, chunk_be)[0]
            s_le = struct.unpack_from('<' + signed[size], chunk_le)[0]
            s_be = struct.unpack_from('>' + signed[size], chunk_be)[0]
            lbl  = size * 8
            out[f'uint{lbl}_LE'] = u_le
            out[f'uint{lbl}_BE'] = u_be
            out[f'int{lbl}_LE']  = s_le
            out[f'int{lbl}_BE']  = s_be

    return out


def decode_floats(data: bytes) -> dict:
    """Try to decode as 32-bit and 64-bit IEEE-754 floats."""
    out = {}
    n   = len(data)

    if n >= 4:
        out['float32_LE'] = struct.unpack_from('<f', data[:4])[0]
        out['float32_BE'] = struct.unpack_from('>f', data[:4])[0]
    if n >= 8:
        out['float64_LE'] = struct.unpack_from('<d', data[:8])[0]
        out['float64_BE'] = struct.unpack_from('>d', data[:8])[0]

    return out


def decode_utf8(data: bytes) -> str | None:
    """Attempt UTF-8 decode; return None on failure."""
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return None


def print_separator(char: str = '─', width: int = 70) -> None:
    print(char * width)


def display_all(data: bytes, packet_no: int) -> None:
    """Pretty-print every interpretation of the received bytes."""
    ts = time.strftime('%H:%M:%S')
    print_separator()
    print(f"  Packet #{packet_no:>6}  |  {ts}  |  {len(data)} byte(s)")
    print_separator('─')

    # ── Raw representations ──────────────────────────────────────────────────
    print(f"  HEX    : {hex_dump(data)}")
    print(f"  BINARY : {bin_dump(data)}")
    print(f"  ASCII  : {ascii_repr(data)}")

    # ── UTF-8 text ───────────────────────────────────────────────────────────
    utf8 = decode_utf8(data)
    if utf8 is not None:
        printable = utf8.strip()
        if printable:
            print(f"  UTF-8  : {printable!r}")

    # ── Integer interpretations ──────────────────────────────────────────────
    ints = decode_ints(data)
    if ints:
        print()
        print("  ── Integer interpretations ─────────────────────")
        for label, value in ints.items():
            print(f"    {label:<12}: {value}")

    # ── Float interpretations ────────────────────────────────────────────────
    floats = decode_floats(data)
    if floats:
        print()
        print("  ── Float interpretations ───────────────────────")
        for label, value in floats.items():
            print(f"    {label:<12}: {value:.6g}")

    print()


def main() -> None:
    print(f"Opening UART  : {UART_PORT}")
    print(f"Baud rate     : {BAUD_RATE}")
    print(f"Read chunk    : {READ_CHUNK} bytes")
    print(f"Timeout       : {TIMEOUT_S} s")
    print_separator('═')
    print("Listening for data... (Ctrl+C to stop)")
    print_separator('═')

    try:
        ser = serial.Serial(
            port=UART_PORT,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=TIMEOUT_S,
        )
    except serial.SerialException as exc:
        print(f"[ERROR] Cannot open {UART_PORT}: {exc}", file=sys.stderr)
        sys.exit(1)

    packet_no  = 0
    byte_total = 0

    try:
        while True:
            raw = ser.read(READ_CHUNK)   # blocks up to TIMEOUT_S
            if not raw:
                continue                 # timeout with no data → loop

            packet_no  += 1
            byte_total += len(raw)
            display_all(raw, packet_no)

    except KeyboardInterrupt:
        print_separator('═')
        print(f"Stopped.  Packets received: {packet_no}  |  Total bytes: {byte_total}")

    finally:
        if ser.is_open:
            ser.close()


if __name__ == '__main__':
    main()

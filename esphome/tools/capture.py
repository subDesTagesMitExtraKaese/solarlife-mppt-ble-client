#!/usr/bin/env python3
"""Record what the MPPT bridge sees, for offline analysis.

The script connects to the ESPHome API of a running bridge and writes one
NDJSON line per event:

    {"type": "meta", ...}      device name and version, once per run
    {"type": "frame", ...}     one reassembled and CRC-checked frame
    {"type": "decoded", ...}   the same frame parsed with the Python client
    {"type": "state", ...}     one changed MPPT entity state
    {"type": "log", ...}       warnings, errors and component logs

Only the MPPT sub-device is recorded; the bridge's own sensors and the BLE
notify chunks are skipped to keep capture files small.

The raw frames separate controller behaviour from client problems such as
framing errors and stale values.

Needs `aioesphomeapi`, which ships with ESPHome, so the virtualenv used to
compile the bridge can run it. Run it next to the bridge, for example:

    nohup .venv-local/bin/python esphome/tools/capture.py \
        --host <bridge-ip> --out-dir captures >> captures/capture.out 2>&1 &

Frames are only logged when the firmware is compiled with `logger: level:
DEBUG` or higher.
"""

import argparse
import json
import re
import struct
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from aioesphomeapi import APIClient, APIConnectionError
from aioesphomeapi.api_pb2 import LogLevel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.protocol import LumiaxClient, ProtocolError

ANSI = re.compile(r"\x1b\[[0-9;]*m")
LOG_LINE = re.compile(r"^\[([A-Z]+)\]\[([^\]]*)\]: (.*)$")
FRAME = re.compile(
    r"^Read frame: start=0x([0-9A-Fa-f]+) fc=0x([0-9A-Fa-f]+) "
    r"byte_count=(\d+) length=(\d+) raw=(.*)$"
)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class Capture:
    def __init__(self, out_dir: Path, max_bytes: int = 64 * 1024 * 1024):
        self.out_dir = out_dir
        self.max_bytes = max_bytes
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.handle = None
        self.path = None
        self.client = LumiaxClient()
        self.names = {}
        self.device_ids = set()
        self.last_states = {}
        self.register_addresses = None
        self.open()

    def open(self) -> None:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self.path = self.out_dir / f"mppt-{stamp}.ndjson"
        self.handle = self.path.open("a", buffering=1)
        print(f"capturing to {self.path}", file=sys.stderr, flush=True)

    def rotate_if_needed(self) -> None:
        if self.handle is not None and self.handle.tell() > self.max_bytes:
            self.handle.close()
            self.open()

    def write(self, event: dict) -> None:
        self.rotate_if_needed()
        self.handle.write(json.dumps(event, separators=(",", ":")) + "\n")

    def state_name(self, key: int) -> str:
        return self.names.get(key, f"key{key}")

    def on_state(self, state) -> None:
        if self.device_ids and getattr(state, "device_id", None) not in self.device_ids:
            return
        value = getattr(state, "state", None)
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8", "replace")
        if self.last_states.get(state.key) == value:
            return
        self.last_states[state.key] = value
        self.write({"type": "state", "ts": now(), "name": self.state_name(state.key), "value": value})

    def on_log(self, message) -> None:
        text = getattr(message, "message", b"")
        if isinstance(text, (bytes, bytearray)):
            text = text.decode("utf-8", "replace")
        text = ANSI.sub("", text)

        for line in text.splitlines():
            # Unprefixed lines are the API's own traffic.
            match = LOG_LINE.match(line)
            if match is None:
                continue
            level, tag, msg = match.groups()

            if msg.startswith("Notify chunk"):
                # The reassembled frame below has the same bytes.
                continue

            frame = FRAME.match(msg)
            if frame is not None:
                start, fc, byte_count, length, raw = frame.groups()
                self.write_frame(int(start, 16), int(fc, 16), int(byte_count), int(length), raw)
                continue

            # Keep component logs plus warnings and errors; other lines are noise.
            if tag.startswith("solarlife_mppt") or level in ("W", "E"):
                self.write({"type": "log", "ts": now(), "level": level, "tag": tag, "msg": msg})

    def write_frame(self, start: int, fc: int, byte_count: int, length: int, raw: str) -> None:
        hexes = raw.split()
        frame = bytes(int(value, 16) for value in hexes)
        event = {
            "type": "frame",
            "ts": now(),
            "start": start,
            "fc": fc,
            "byte_count": byte_count,
            "length": length,
            "raw": "".join(hexes),
        }
        self.write(event)

        # Decode with the Python client parser so the capture also records what
        # that client would have published for this frame.
        try:
            results = self.client.parse(start, frame)
        except (ProtocolError, ValueError, IndexError, struct.error) as error:
            self.write({"type": "decode_error", "ts": now(), "raw": event["raw"], "error": str(error)})
            return

        event = {"type": "decoded", "ts": now(), "start": start}
        if self.register_addresses is None:
            # Names repeat in the register map; record once where this frame
            # takes each value from.
            self.register_addresses = {result.name: f"{result.address:#06x}" for result in results}
            event["registers"] = self.register_addresses
        event["values"] = {
            result.name: round(result.value, 4) if isinstance(result.value, float) else result.value
            for result in results
        }
        self.write(event)


async def run(host: str, port: int, capture: Capture, encryption_key: str | None) -> None:
    import asyncio

    stopped = asyncio.Event()

    async def on_stop(expected_disconnect: bool) -> None:
        # The bridge reboots on every OTA update; reconnect instead of
        # sleeping forever on a dead connection.
        stopped.set()

    client = APIClient(host, port, noise_psk=encryption_key)
    await client.connect(on_stop=on_stop, login=True)
    info = await client.device_info()
    capture.write(
        {
            "type": "meta",
            "ts": now(),
            "host": host,
            "name": info.name,
            "esphome_version": info.esphome_version,
        }
    )

    entities, _ = await client.list_entities_services()
    capture.names = {entity.key: getattr(entity, "name", str(entity.key)) for entity in entities}
    capture.device_ids = {device.device_id for device in info.devices if "solarlife" in device.name.lower()}
    if not capture.device_ids:
        capture.write({"type": "log", "ts": now(), "level": "W", "tag": "capture", "msg": "no Solarlife sub-device found, recording all states"})

    client.subscribe_states(capture.on_state)
    client.subscribe_logs(capture.on_log, log_level=LogLevel.LOG_LEVEL_VERY_VERBOSE)

    print("capturing, press Ctrl+C to stop", file=sys.stderr, flush=True)
    await stopped.wait()


def main() -> None:
    import asyncio

    parser = argparse.ArgumentParser(description="Record MPPT bridge frames and states as NDJSON")
    parser.add_argument("--host", required=True, help="ESPHome bridge address")
    parser.add_argument("--port", type=int, default=6053, help="ESPHome API port")
    parser.add_argument("--out-dir", default="captures", help="directory for the NDJSON files")
    parser.add_argument("--encryption-key", default=None, help="API encryption key, if the bridge has one")
    args = parser.parse_args()

    capture = Capture(Path(args.out_dir))
    while True:
        try:
            asyncio.run(run(args.host, args.port, capture, args.encryption_key))
        except KeyboardInterrupt:
            break
        except (APIConnectionError, OSError, TimeoutError) as error:
            capture.write({"type": "disconnect", "ts": now(), "error": str(error)})
            print(f"capture disconnected ({error}), retrying in 15s", file=sys.stderr, flush=True)
            time.sleep(15)


if __name__ == "__main__":
    main()

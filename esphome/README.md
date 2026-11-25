# ESPHome MPPT bridge

ESPHome implementation of the Lumiax Modbus-over-BLE bridge. It is a secondary
target to the Python client and needs no Python at runtime.

The component is board-independent. The included
[`shelly-plus-plug-s.yaml`](shelly-plus-plug-s.yaml) is one example wiring; adapt
it to your own board.

## Configuration

Add a `ble_client`, include [`packages/solarlife_mppt.yaml`](packages/solarlife_mppt.yaml)
and enable the local component:

```yaml
external_components:
  - source:
      type: local
      path: components
    components: [solarlife_mppt]

solarlife_mppt:
  id: mppt
  ble_client_id: mppt_ble
  update_interval: 20s
```

Optional settings are `service_uuid`, `notify_uuid`, `write_uuid`, `retries`,
`timeout` and `parameters_interval`.

## Entities

Entities are generated from the shared `../registers.toml` into
`packages/solarlife_mppt.yaml`:

- flags become binary sensors;
- read-only numbers become sensors;
- writable numbers become numbers;
- enums become text sensors;
- writable two-state enums become switches;
- writable multi-value enums become selects;
- write-only actions become buttons.

The detail block is read every `update_interval` (20 s by default). The
parameter block is read every `parameters_interval` (300 s by default).

The same name exists in several controller blocks (`load_current` is both a
status register at `0x304B` and a real-time register at `0x3126`). A name-only
lookup would pick one of them and silently starve the entity, so every generated
entity also passes the `address` it belongs to. Hand-written entities may omit
`address`; they then fall back to the first name match.

## Protocol

The controller speaks Modbus-RTU-style frames over BLE:

- notify on `0000ff01-…`, write on `0000ff02-…`
- read: `FE 04 30 30 00 29 <crc16>` for the 41 detail registers at `0x3030`
- read: `FE 03 90 21 00 0C <crc16>` for the 12 parameter registers at `0x9021`
- write: `FE 05/06 <addr> <value> <crc16>`; 32-bit values use `FE 10`
- CRC16/Modbus, little-endian; responses are reassembled from notifications and
  retried on timeout.
- A response is only accepted when device id, function code and byte count match
  the request. Anything else is dropped byte by byte, so a late byte from a
  previous response cannot shift the next one.

## Register map

`../registers.toml` is the source of truth for both targets. Edit it, then
regenerate from the repository root:

```bash
python esphome/tools/gen_registers.py
```

## Limitations

- The generated C++ table and the entity package only cover the detail,
  parameter and switch/button ranges. Other registers stay in
  `../registers.toml` but are not compiled into the firmware.
- Device settings outside the parameter block (clock, backlight, device ID,
  timing periods) are not exposed as entities.
- Wi-Fi and BLE share one radio on some ESP32 variants. Expect slower connects
  and occasional retries.

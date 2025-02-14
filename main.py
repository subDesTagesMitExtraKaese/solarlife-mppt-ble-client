#!/usr/bin/env python3

import argparse
import asyncio
import signal
import json

import aiomqtt
from bleak import BleakScanner
from bleak.exc import BleakError, BleakDeviceNotFoundError

from src.bleclient import BleClient

send_config = True
reconnect_interval = 5  # In seconds

async def mqtt_publish(details: dict[str, any], client: aiomqtt.Client):
    global send_config
    # Define the base topic for MQTT Discovery
    base_topic = "homeassistant"

    # Define the device information
    device_info = {
        "identifiers": ["solarlife_mppt_ble"],
        "name": "Solarlife MPPT",
        "manufacturer": "Solarlife",
    }

    # Publish each item in the details dictionary to its own MQTT topic
    for key, value in details.items():
        state_topic = f"{base_topic}/sensor/solarlife/{key}/state"
        topic = f"{base_topic}/sensor/solarlife/{key}/config"

        # Create the MQTT Discovery payload
        payload = {
            "name": f"Solarlife {key.replace('_', ' ').title()}",
            "device": device_info,
            "unique_id": f"solarlife_{key}",
            "state_topic": state_topic,
            "unit_of_measurement": BleClient.get_unit_of_measurement(key)
        }
        if "daily_energy" in key:
            payload['device_class'] = "energy"
            payload['state_class'] = "total_increasing"
        elif "total_energy" in key:
            payload['device_class'] = "energy"
            payload['state_class'] = "total"
        elif "voltage" in key:
            payload['device_class'] = "voltage"
            payload['state_class'] = "measurement"
        elif "current" in key:
            payload['device_class'] = "current"
            payload['state_class'] = "measurement"
        elif "power" in key:
            payload['device_class'] = "power"
            payload['state_class'] = "measurement"
        elif "temperature" in key:
            payload['device_class'] = "temperature"
            payload['state_class'] = "measurement"
        elif key == "battery_percentage":
            payload['device_class'] = "battery"
            payload['state_class'] = "measurement"

        # Publish the MQTT Discovery payload
        if send_config:
            print(f"Publishing MQTT Discovery payload for {key}")
            await client.publish(topic, payload=json.dumps(payload), retain=True)

        # Publish the entity state
        await client.publish(state_topic, payload=str(value))
    send_config = False
    
async def main(address, host, port, username, password):
    async def run_mppt():
        while True:
            try:
                async with aiomqtt.Client(hostname=host, port=port, username=username, password=password) as client:
                    print(f"Connecting to MQTT broker at {host}:{port}")
                    while True:
                        try:
                            async with BleClient(address) as mppt:
                                while True:
                                    details = await mppt.request_details()
                                    if details:
                                        print(f"Battery: {details['battery_percentage']}% ({details['battery_voltage']}V)")
                                        await mqtt_publish(details, client)
                                    else:
                                        print("No values recieved")
                                    await asyncio.sleep(20.0)

                        except BleakDeviceNotFoundError:
                            print(f"BLE device with address {address} was not found")
                            await asyncio.sleep(5)
                        except BleakError as e:
                            print(f"BLE error occurred: {e}")
                            await asyncio.sleep(5)
            except aiomqtt.MqttError as error:
                print(f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
                await asyncio.sleep(reconnect_interval)
            except asyncio.CancelledError:
                raise  # Re-raise the CancelledError to stop the task
            except Exception as e:
                print(f"An error occurred during BLE communication: {e}")
                await asyncio.sleep(5)  # Wait for 5 seconds before retrying

    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(run_mppt())

        # Setup signal handler to cancel the task on termination
        for signame in {'SIGINT', 'SIGTERM'}:
            loop.add_signal_handler(getattr(signal, signame),
                                    task.cancel)

        await task  # Wait for the task to complete

    except asyncio.CancelledError:
        pass  # Task was cancelled, no need for an error message

async def list_services(address):
    async with BleClient(address) as mppt:
        mppt.list_services()

async def scan_for_devices():
    devices = await BleakScanner.discover()
    if not devices:
        print("No BLE devices found.")
    else:
        print("Available BLE devices:")
        for device in devices:
            print(f"{device.address} - {device.name}")
    return devices

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Solarlife MPPT BLE Client')
    parser.add_argument('address', help='BLE device address')
    parser.add_argument('--host', help='MQTT broker host', default='localhost')
    parser.add_argument('--port', help='MQTT broker port', default=1883, type=int)
    parser.add_argument('--username', help='MQTT username')
    parser.add_argument('--password', help='MQTT password')
    parser.add_argument('--list-services', help='List GATT services', action='store_true')
    parser.add_argument('--scan', help='Scan for bluetooth devices', action='store_true')

    args = parser.parse_args()

    if args.scan:
        asyncio.run(scan_for_devices())
    elif args.list_services:
        asyncio.run(list_services(args.address))
    else:
        asyncio.run(main(args.address, args.host, args.port, args.username, args.password))

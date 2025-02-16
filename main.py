#!/usr/bin/env python3

import argparse
import asyncio
import signal

import aiomqtt
from bleak import BleakScanner
from bleak.exc import BleakError, BleakDeviceNotFoundError

from src.homeassistant import MqttSensor
from src.bleclient import BleClient, Result
from src.variables import variables

send_config = True
request_interval = 20   # In seconds
reconnect_interval = 5  # In seconds

async def request_and_publish_details(sensor: MqttSensor, mppt: BleClient) -> None:
    global send_config
    details = await mppt.request_details()
    if details:
        print(f"Battery: {details['battery_percentage'].value}% ({details['battery_voltage'].value}V)")
        if send_config:
            print(f"configuring {len(details)}/{len(variables)} entities")
            await sensor.store_config(details)
            send_config = False
        
        await sensor.publish(details)
    else:
        print("No values recieved")

async def run_mppt(sensor: MqttSensor, address: str):
    try:
        async with BleClient(address) as mppt:
            while True:
                await request_and_publish_details()
                await asyncio.sleep(request_interval)

    except BleakDeviceNotFoundError:
        print(f"BLE device with address {address} was not found")
        await asyncio.sleep(reconnect_interval)
    except BleakError as e:
        print(f"BLE error occurred: {e}")
        await asyncio.sleep(reconnect_interval)

async def run_mqtt(address, host, port, username, password):
    while True:
        try:
            async with MqttSensor(hostname=host, port=port, username=username, password=password) as sensor:
                print(f"Connected to MQTT broker at {host}:{port}")
                while True:
                    await run_mppt(sensor, address)
        except aiomqtt.MqttError as error:
            print(f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
            await asyncio.sleep(reconnect_interval)
        except asyncio.CancelledError:
            raise  # Re-raise the CancelledError to stop the task
        except Exception as e:
            print(f"An error occurred during BLE communication: {e}")
            await asyncio.sleep(reconnect_interval)

async def main(*args):
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(run_mqtt(*args))

        # Setup signal handler to cancel the task on termination
        for signame in {'SIGINT', 'SIGTERM'}:
            loop.add_signal_handler(getattr(signal, signame),
                                    task.cancel)

        await task  # Wait for the task to complete

    except asyncio.CancelledError:
        pass  # Task was cancelled, no need for an error message

async def list_services(address):
    async with BleClient(address) as mppt:
        await mppt.list_services()

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

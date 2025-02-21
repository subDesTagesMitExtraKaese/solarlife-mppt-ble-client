#!/usr/bin/env python3

import argparse
import asyncio
import signal
import traceback

import aiomqtt
from bleak import BleakScanner
from bleak.exc import BleakError, BleakDeviceNotFoundError

from src.homeassistant import MqttSensor
from src.bleclient import BleClient, Result
from src.variables import variables, VariableContainer, battery_and_load_parameters, switches

request_interval = 20   # In seconds
reconnect_interval = 5  # In seconds

ble_lock = asyncio.Lock()

async def request_and_publish_details(sensor: MqttSensor, address: str) -> None:
    async with ble_lock:
        try:
            async with BleClient(address) as mppt:
                details = await mppt.request_details()
                if details:
                    print(f"Battery: {details['battery_percentage'].value}% ({details['battery_voltage'].value}V)")
                    await sensor.publish(details)
                else:
                    print("No values recieved")
        except (BleakError, asyncio.TimeoutError) as e:
            print(f"Got {type(e).__name__} while fetching details: {e}")

async def request_and_publish_parameters(sensor: MqttSensor, address: str) -> None:
    async with ble_lock:
        async with BleClient(address) as mppt:
            parameters = await mppt.request_parameters()
            if parameters:
                await sensor.publish(parameters)

async def subscribe_and_watch(sensor: MqttSensor, address: str):
    parameters = battery_and_load_parameters[:12] + switches
    await sensor.subscribe(parameters)
    await sensor.store_config(switches)

    while True:
        command = await sensor.get_command()
        print(f"Received command to set {command.name} to '{command.value}'")
        async with ble_lock:
            try:
                async with BleClient(address) as mppt:
                    results = await mppt.write([command])
                    await sensor.publish(results)
            except (BleakError, asyncio.TimeoutError) as e:
                print(f"Get {type(e).__name__} while writing command: {e}")


async def run_mppt(sensor: MqttSensor, address: str):
    loop = asyncio.get_event_loop()
    task = loop.create_task(subscribe_and_watch(sensor, address))

    try:
        await request_and_publish_parameters(sensor, address)
        while True:
            await request_and_publish_details(sensor, address)
            await asyncio.sleep(request_interval)
            if task.done() and task.exception():
                break
    except (asyncio.TimeoutError, BleakDeviceNotFoundError, BleakError) as e:
        print(f"{type(e).__name__} occurred: {e}")
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    print("BLE session ended.")


async def run_mqtt(address, host, port, username, password):
    while True:
        try:
            async with MqttSensor(hostname=host, port=port, username=username, password=password) as sensor:
                print(f"Connected to MQTT broker at {host}:{port}")
                while True:
                    await run_mppt(sensor, address)
                    await asyncio.sleep(reconnect_interval)
        except aiomqtt.MqttError as error:
            print(f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
        except asyncio.CancelledError:
            raise  # Re-raise the CancelledError to stop the task
        except Exception as e:
            print(traceback.format_exc())
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

#!/usr/bin/env python3

import argparse
import asyncio
import signal
import json

import paho.mqtt.client as mqtt
from bleak.exc import BleakError, BleakDeviceNotFoundError

from bleclient import BleClient

client = mqtt.Client()
send_config = True

def details_handler(details):
    if details:
        print(f"Battery: {details['battery_percentage']}% ({details['battery_voltage']}V)")
        mqtt_publish(details, client)
    else:
        print("No values recieved")


def mqtt_publish(details, client):
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
            client.publish(topic, payload=json.dumps(payload), retain=True)

        # Publish the entity state
        client.publish(state_topic, payload=str(value))
    send_config = False
    
async def main(address, host, port, username, password):
    client.username_pw_set(username, password)  # Set MQTT username and password

    async def run_mppt():
        while True:
            try:
                client.connect(host, port)  # Connect to the MQTT broker
                break  # Connection successful, exit the loop

            except asyncio.CancelledError:
                raise  # Re-raise the CancelledError to stop the task
            except Exception as e:
                print(f"An error occurred while connecting to MQTT broker: {e}")
                await asyncio.sleep(5)  # Wait for 5 seconds before retrying

        while True:
            try:
                async with BleClient(address) as mppt:
                    mppt.on_details_received = details_handler
                    await mppt.request_details()

                    while True:
                        await asyncio.sleep(20.0)
                        try:
                            await mppt.request_details()
                        except BleakError as e:
                            print(f"BLE error occurred: {e}")
                            # Handle the BLE error accordingly, e.g., reconnect or terminate the task
                            break

            except asyncio.CancelledError:
                raise  # Re-raise the CancelledError to stop the task
            except BleakDeviceNotFoundError:
                print(f"BLE device with address {address} was not found")
                await asyncio.sleep(5)  # Wait for 5 seconds before retrying
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Solarlife MPPT BLE Client')
    parser.add_argument('address', help='BLE device address')
    parser.add_argument('--host', help='MQTT broker host', default='localhost')
    parser.add_argument('--port', help='MQTT broker port', default=1883, type=int)
    parser.add_argument('--username', help='MQTT username')
    parser.add_argument('--password', help='MQTT password')

    args = parser.parse_args()

    asyncio.run(main(args.address, args.host, args.port, args.username, args.password))

import json
import re
from typing import ClassVar

from aiomqtt import Client

from src.protocol import Result, ResultContainer
from src.registers import Register, RegisterContainer, ValueKind, registers


class MqttSensor(Client):
    # Define the base topic for MQTT Discovery
    base_topic = "homeassistant"

    # Define the sensor name
    sensor_name = "solarlife"

    # Define the device information
    device_info: ClassVar[dict] = {
        "identifiers": ["solarlife_mppt_ble"],
        "name": "Solarlife",
        "manufacturer": "Solarlife",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.known_names = set()
        self.subscribed_names = set()

    # https://www.home-assistant.io/integrations/#search/mqtt
    def get_platform(self, register: Register) -> str:
        kind = register.format.kind
        if kind is ValueKind.FLAG:
            return "binary_sensor"
        if kind is ValueKind.ENUM:
            if register.is_writable:
                return "switch" if register.payload_off else "button"
            return "sensor"
        if register.is_writable:
            return "number"
        return "sensor"

    def get_config_topic(self, register: Register) -> str:
        platform = self.get_platform(register)
        return f"{self.base_topic}/{platform}/{self.sensor_name}/{register.name}/config"

    def get_state_topic(self, register: Register) -> str:
        platform = self.get_platform(register)
        return f"{self.base_topic}/{platform}/{self.sensor_name}/{register.name}/state"

    def get_command_topic(self, register: Register) -> str:
        platform = self.get_platform(register)
        return (
            f"{self.base_topic}/{platform}/{self.sensor_name}/{register.name}/command"
        )

    async def store_config(self, registers: RegisterContainer) -> None:
        # Publish each item in the results to its own MQTT topic
        for key, register in registers.items():
            if key in self.known_names:
                continue
            self.known_names.add(key)

            platform = self.get_platform(register)
            config_topic = self.get_config_topic(register)
            state_topic = self.get_state_topic(register)
            command_topic = self.get_command_topic(register)

            print(f"Publishing homeassistant config for {platform} {key}")

            # Create the MQTT Discovery payload
            payload = {
                "name": register.friendly_name,
                "device": self.device_info,
                "object_id": f"{self.sensor_name}_{key}",
                "unique_id": f"{self.sensor_name}_{key}",
                "state_topic": state_topic,
            }

            if register.format.kind is ValueKind.NUMBER and register.format.divisor:
                payload["unit_of_measurement"] = register.unit
                payload["mode"] = "box"
                payload["min"] = 0

            if "daily" in key and "Wh" in register.unit:
                payload["device_class"] = "energy"
                payload["state_class"] = "total_increasing"
            elif "total" in key and "Wh" in register.unit:
                payload["device_class"] = "energy"
                payload["state_class"] = "total"
            elif "Wh" in register.unit:
                payload["device_class"] = "energy"
                payload["state_class"] = "measurement"
            elif "V" in register.unit:
                payload["device_class"] = "voltage"
                payload["state_class"] = "measurement"
            elif "A" in register.unit:
                payload["device_class"] = "current"
                payload["state_class"] = "measurement"
            elif "W" in register.unit:
                payload["device_class"] = "power"
                payload["state_class"] = "measurement"
            elif "°C" in register.unit:
                payload["device_class"] = "temperature"
                payload["state_class"] = "measurement"
            elif key == "battery_percentage":
                payload["device_class"] = "battery"
                payload["state_class"] = "measurement"
            elif "timing_period" in key or "delay" in key or "total_light_time" in key:
                payload["device_class"] = "duration"

            if platform == "button":
                payload["payload_press"] = register.payload_on
            elif platform in ("switch", "binary_sensor"):
                payload["payload_on"] = register.payload_on
                payload["payload_off"] = register.payload_off

            if register.is_writable:
                payload["command_topic"] = command_topic

            # Publish the MQTT Discovery payload
            await super().publish(
                config_topic, payload=json.dumps(payload), retain=True
            )

    async def publish(self, results: ResultContainer):
        await self.store_config(results)
        # Publish each item in the details dictionary to its own MQTT topic
        for result in results:
            state_topic = self.get_state_topic(result)
            # Publish the entity state
            await super().publish(
                state_topic, payload=str(result.value), retain=result.is_writable
            )

    async def subscribe(self, registers: RegisterContainer):
        for key, register in registers.items():
            if register.is_writable:
                if key in self.subscribed_names:
                    continue
                self.subscribed_names.add(key)
                platform = self.get_platform(register)
                command_topic = self.get_command_topic(register)
                print(
                    f"Subscribing to homeassistant commands for {platform} {register.name}"
                )
                await super().subscribe(topic=command_topic, qos=2)

    async def get_command(self) -> Result:
        message = await anext(self.messages)
        match = re.match(
            rf"^{self.base_topic}/\w+/{self.sensor_name}/(\w+)/", message.topic.value
        )
        register_name = match.group(1)
        register = registers[register_name]
        value = str(message.payload, encoding="utf8")
        return Result(**vars(register), value=value)

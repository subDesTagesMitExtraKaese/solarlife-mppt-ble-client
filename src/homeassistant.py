import json
import re

from aiomqtt import Client

from src.protocol import ResultContainer, Result, FunctionCodes
from src.variables import VariableContainer, Variable, variables

class MqttSensor(Client):
    # Define the base topic for MQTT Discovery
    base_topic = "homeassistant"

    # Define the sensor name
    sensor_name = "solarlife"

    # Define the device information
    device_info = {
        "identifiers": ["solarlife_mppt_ble"],
        "name": "Solarlife",
        "manufacturer": "Solarlife",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.known_names = set()
        self.subscribed_names = set()

    # https://www.home-assistant.io/integrations/#search/mqtt
    def get_platform(self, variable: Variable) -> str:
        is_writable = FunctionCodes.WRITE_MEMORY_SINGLE.value in variable.function_codes or \
                      FunctionCodes.WRITE_STATUS_REGISTER.value in variable.function_codes
        is_numeric = variable.multiplier != 0
        if variable.binary_payload:
            on, off = variable.binary_payload
            if is_writable and off:
                return "switch"
            elif is_writable:
                return "button"
            else:
                return "binary_sensor"
        elif is_writable and is_numeric:
            return "number"
        elif is_writable:
            # to-do: select or text 
            pass
        return "sensor"

    def get_config_topic(self, variable: Variable) -> str:
        platform = self.get_platform(variable)
        return f"{self.base_topic}/{platform}/{self.sensor_name}/{variable.name}/config"
    
    def get_state_topic(self, variable: Variable) -> str:
        platform = self.get_platform(variable)
        return f"{self.base_topic}/{platform}/{self.sensor_name}/{variable.name}/state"

    def get_command_topic(self, variable: Variable) -> str:
        platform = self.get_platform(variable)
        return f"{self.base_topic}/{platform}/{self.sensor_name}/{variable.name}/command"

    async def store_config(self, variables: VariableContainer) -> None:
        # Publish each item in the results to its own MQTT topic
        for key, variable in variables.items():
            if key in self.known_names:
                continue
            self.known_names.add(key)

            platform = self.get_platform(variable)
            config_topic = self.get_config_topic(variable)
            state_topic = self.get_state_topic(variable)
            command_topic = self.get_command_topic(variable)

            print(f"Publishing homeassistant config for {platform} {key}")

            # Create the MQTT Discovery payload
            payload = {
                "name": variable.friendly_name,
                "device": self.device_info,
                "object_id": f"{self.sensor_name}_{key}",
                "unique_id": f"{self.sensor_name}_{key}",
                "state_topic": state_topic,
            }

            if variable.multiplier != 0:
                payload["unit_of_measurement"] = variable.unit
                payload["mode"] = "box"
                payload["min"] = 0
                
            if "daily" in key and "Wh" in variable.unit:
                payload['device_class'] = "energy"
                payload['state_class'] = "total_increasing"
            elif "total" in key and "Wh" in variable.unit:
                payload['device_class'] = "energy"
                payload['state_class'] = "total"
            elif "Wh" in variable.unit:
                payload['device_class'] = "energy"
                payload['state_class'] = "measurement"
            elif "V" in variable.unit:
                payload['device_class'] = "voltage"
                payload['state_class'] = "measurement"
            elif "A" in variable.unit:
                payload['device_class'] = "current"
                payload['state_class'] = "measurement"
            elif "W" in variable.unit:
                payload['device_class'] = "power"
                payload['state_class'] = "measurement"
            elif "°C" in variable.unit:
                payload['device_class'] = "temperature"
                payload['state_class'] = "measurement"
            elif key == "battery_percentage":
                payload['device_class'] = "battery"
                payload['state_class'] = "measurement"
            elif "timing_period" in key or "delay" in key or "total_light_time" in key:
                payload['device_class'] = "duration"

            if platform == "button":
                on, off = variable.binary_payload
                payload["payload_press"] = on
            elif variable.binary_payload:
                on, off = variable.binary_payload
                payload["payload_on"] = on
                payload["payload_off"] = off

            # Handle writable entities
            if FunctionCodes.WRITE_MEMORY_SINGLE.value in variable.function_codes or \
               FunctionCodes.WRITE_STATUS_REGISTER.value in variable.function_codes:
                payload["command_topic"] = command_topic

            # Publish the MQTT Discovery payload
            await super().publish(config_topic, payload=json.dumps(payload), retain=True)

    async def publish(self, results: ResultContainer):
        await self.store_config(results)
        # Publish each item in the details dictionary to its own MQTT topic
        for key, result in results.items():
            state_topic = self.get_state_topic(result)
            is_writable = FunctionCodes.WRITE_MEMORY_SINGLE.value in result.function_codes or \
                          FunctionCodes.WRITE_STATUS_REGISTER.value in result.function_codes

            # Publish the entity state
            await super().publish(state_topic, payload=str(result.value), retain=is_writable)

    async def subscribe(self, variables: VariableContainer):
        for key, variable in variables.items():
            if FunctionCodes.WRITE_MEMORY_SINGLE.value in variable.function_codes or \
               FunctionCodes.WRITE_STATUS_REGISTER.value in variable.function_codes:
                if key in self.subscribed_names:
                    continue
                self.subscribed_names.add(key)
                platform = self.get_platform(variable)
                command_topic = self.get_command_topic(variable)
                print(f"Subscribing to homeassistant commands for {platform} {variable.name}")
                await super().subscribe(topic=command_topic, qos=2)
    
    async def get_command(self) -> Result:
        message = await anext(self.messages)
        match = re.match(rf"^{self.base_topic}/\w+/{self.sensor_name}/(\w+)/", message.topic.value)
        variable_name = match.group(1)
        variable = variables[variable_name]
        value = str(message.payload, encoding="utf8")
        return Result(**vars(variable), value=value)
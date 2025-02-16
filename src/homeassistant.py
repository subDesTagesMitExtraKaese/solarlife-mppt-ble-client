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
        "name": "Solarlife MPPT",
        "manufacturer": "Solarlife",
    }

    def __init__(self, *args, **kwargs):
        super(MqttSensor, self).__init__(*args, **kwargs)
        self.known_names = set()

    # https://www.home-assistant.io/integrations/#search/mqtt
    def get_platform(self, variable: Variable) -> str:
        is_writable = FunctionCodes.WRITE_MEMORY_SINGLE in value.function_codes or \
                      FunctionCodes.WRITE_STATUS_REGISTER in value.function_codes
        is_numeric = value.multiplier != 0
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
            print(f"publishing homeassistant config for {key}")
            config_topic = self.get_config_topic(variable)
            state_topic = self.get_state_topic(variable)
            command_topic = self.get_command_topic(variable)

            # Create the MQTT Discovery payload
            payload = {
                "name": variable.friendly_name,
                "device": self.device_info,
                "unique_id": f"solarlife_{key}",
                "state_topic": state_topic,
            }

            if variable.multiplier != 0:
                payload["unit_of_measurement"] = variable.unit
                
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
            elif "timing_period" in key or "delay" in key:
                payload['device_class'] = "duration"

            if variable.binary_payload:
                on, off = variable.binary_payload
                payload["payload_on"] = on
                payload["payload_off"] = off

            # Handle writable entities
            if FunctionCodes.WRITE_MEMORY_SINGLE in variable.function_codes or \
               FunctionCodes.WRITE_STATUS_REGISTER in variable.function_codes:
                payload["command_topic"] = command_topic

            # Publish the MQTT Discovery payload
            await self.publish(config_topic, payload=json.dumps(payload), retain=True)

    async def publish(self, details: ResultContainer):
        # Publish each item in the details dictionary to its own MQTT topic
        for key, value in details.items():
            state_topic = self.get_state_topic(value)

            # Publish the entity state
            await super(MqttSensor, self).publish(state_topic, payload=str(value.value))

    async def subscribe(self, variables: VariableContainer):
        for key, variable in variables.items():
            if FunctionCodes.WRITE_MEMORY_SINGLE in value.function_codes or \
               FunctionCodes.WRITE_STATUS_REGISTER in value.function_codes:
                command_topic = self.get_command_topic(value)
                await super(MqttSensor, self).subscribe(topic=command_topic, qos=2)
    
    async def get_commands(self) -> ResultContainer:
        for message in await self.messages:
            match = re.match(rf"^{self.base_topic}/\w+/{self.sensor_name}/(\w+)/", message.topic)
            variable_name = match.group(1)
            variable = variables[variable_name]
            yield Result(**vars(variable), value=message.payload)
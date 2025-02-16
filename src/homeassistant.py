import json

from aiomqtt import Client

from src.protocol import ResultContainer, VariableContainer, Variable, FunctionCodes


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

    async def store_config(self, results: ResultContainer) -> None:
        # Publish each item in the results to its own MQTT topic
        for key, value in results.items():
            config_topic = self.get_config_topic(value)
            state_topic = self.get_state_topic(value)
            command_topic = self.get_command_topic(value)

            # Create the MQTT Discovery payload
            payload = {
                "name": value.friendly_name,
                "device": self.device_info,
                "unique_id": f"solarlife_{key}",
                "state_topic": state_topic,
            }

            if value.multiplier != 0:
                payload["unit_of_measurement"] = value.unit
                
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

            if value.binary_payload:
                on, off = value.binary_payload
                payload["payload_on"] = on
                payload["payload_off"] = off

            # Handle writable entities
            if FunctionCodes.WRITE_MEMORY_SINGLE in value.function_codes or \
               FunctionCodes.WRITE_STATUS_REGISTER in value.function_codes:
                payload["command_topic"] = command_topic

            # Publish the MQTT Discovery payload
            await self.publish(config_topic, payload=json.dumps(payload), retain=True)

    async def publish(self, details: ResultContainer):
        # Publish each item in the details dictionary to its own MQTT topic
        for key, value in details.items():
            state_topic = self.get_state_topic(value)

            # Publish the entity state
            await super(MqttSensor, self).publish(state_topic, payload=str(value.value))
import json

from aiomqtt import Client

from src.protocol import Result, Variable


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

    def get_config_topic(self, variable: Variable) -> str:
        return f"{self.base_topic}/sensor/{self.sensor_name}/{variable.name}/config"
    
    def get_state_topic(self, variable: Variable) -> str:
        return f"{self.base_topic}/sensor/{self.sensor_name}/{variable.name}/state"
    
    async def store_config(self, details: dict[str, Result]) -> None:
        # Publish each item in the details dictionary to its own MQTT topic
        for key, value in details.items():
            state_topic = self.get_state_topic(value)
            config_topic = self.get_config_topic(value)

            # Create the MQTT Discovery payload
            payload = {
                "name": f"Solarlife {value.friendly_name}",
                "device": self.device_info,
                "unique_id": f"solarlife_{key}",
                "state_topic": state_topic,
                "unit_of_measurement": value.unit,
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
            await self.publish(config_topic, payload=json.dumps(payload), retain=True)

    async def publish(self, details: dict[str, Result]):
        # Publish each item in the details dictionary to its own MQTT topic
        for key, value in details.items():
            state_topic = self.get_state_topic(value)

            # Publish the entity state
            await super(MqttSensor, self).publish(state_topic, payload=str(value.value))
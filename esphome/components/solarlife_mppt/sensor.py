import esphome.codegen as cg
from esphome.const import CONF_ID
from esphome.types import ConfigType

from esphome.components import sensor

from . import (
    CONF_ADDRESS,
    CONF_REGISTER,
    CONF_SOLARLIFE_MPPT_ID,
    SOLARLIFE_MPPT_COMPONENT_SCHEMA,
    solarlife_mppt_ns,
)

DEPENDENCIES = ["solarlife_mppt"]

SolarlifeMpptSensor = solarlife_mppt_ns.class_(
    "SolarlifeMpptSensor", sensor.Sensor, cg.Component
)

CONFIG_SCHEMA = SOLARLIFE_MPPT_COMPONENT_SCHEMA.extend(
    sensor.sensor_schema(SolarlifeMpptSensor)
)


async def to_code(config: ConfigType) -> None:
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await sensor.register_sensor(var, config)
    await cg.register_parented(var, config[CONF_SOLARLIFE_MPPT_ID])
    cg.add(var.set_register(config[CONF_REGISTER]))
    if CONF_ADDRESS in config:
        cg.add(var.set_address(config[CONF_ADDRESS]))

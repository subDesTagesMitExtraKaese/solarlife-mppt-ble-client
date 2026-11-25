import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_MAX_VALUE, CONF_MIN_VALUE, CONF_STEP
from esphome.types import ConfigType

from esphome.components import number

from . import (
    CONF_ADDRESS,
    CONF_REGISTER,
    CONF_SOLARLIFE_MPPT_ID,
    SOLARLIFE_MPPT_COMPONENT_SCHEMA,
    solarlife_mppt_ns,
)

DEPENDENCIES = ["solarlife_mppt"]

SolarlifeMpptNumber = solarlife_mppt_ns.class_(
    "SolarlifeMpptNumber", number.Number, cg.Component
)

CONFIG_SCHEMA = SOLARLIFE_MPPT_COMPONENT_SCHEMA.extend(
    number.number_schema(SolarlifeMpptNumber).extend(
        {
            cv.Optional(CONF_MIN_VALUE, default=0.0): cv.float_,
            cv.Optional(CONF_MAX_VALUE, default=65535.0): cv.float_,
            cv.Optional(CONF_STEP, default=0.01): cv.positive_float,
        }
    )
)


async def to_code(config: ConfigType) -> None:
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await number.register_number(
        var,
        config,
        min_value=config[CONF_MIN_VALUE],
        max_value=config[CONF_MAX_VALUE],
        step=config[CONF_STEP],
    )
    await cg.register_parented(var, config[CONF_SOLARLIFE_MPPT_ID])
    cg.add(var.set_register(config[CONF_REGISTER]))
    if CONF_ADDRESS in config:
        cg.add(var.set_address(config[CONF_ADDRESS]))

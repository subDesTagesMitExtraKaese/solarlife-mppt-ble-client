import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_OPTIONS
from esphome.types import ConfigType

from esphome.components import select

from . import (
    CONF_ADDRESS,
    CONF_REGISTER,
    CONF_SOLARLIFE_MPPT_ID,
    SOLARLIFE_MPPT_COMPONENT_SCHEMA,
    solarlife_mppt_ns,
)

DEPENDENCIES = ["solarlife_mppt"]

SolarlifeMpptSelect = solarlife_mppt_ns.class_(
    "SolarlifeMpptSelect", select.Select, cg.Component
)

CONFIG_SCHEMA = SOLARLIFE_MPPT_COMPONENT_SCHEMA.extend(
    select.select_schema(SolarlifeMpptSelect).extend(
        {cv.Required(CONF_OPTIONS): cv.All(cv.ensure_list(cv.string_strict), cv.Length(min=1))}
    )
)


async def to_code(config: ConfigType) -> None:
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await select.register_select(var, config, options=config[CONF_OPTIONS])
    await cg.register_parented(var, config[CONF_SOLARLIFE_MPPT_ID])
    cg.add(var.set_register(config[CONF_REGISTER]))
    if CONF_ADDRESS in config:
        cg.add(var.set_address(config[CONF_ADDRESS]))

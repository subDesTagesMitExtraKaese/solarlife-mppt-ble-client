import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.types import ConfigType

from esphome.components import ble_client

CODEOWNERS = ["@subDesTagesMitExtraKaese"]
DEPENDENCIES = ["ble_client", "esp32_ble_tracker"]
AUTO_LOAD = [
    "sensor",
    "number",
    "binary_sensor",
    "text_sensor",
    "select",
    "switch",
    "button",
]
MULTI_CONF = True

DOMAIN = "solarlife_mppt"

CONF_SOLARLIFE_MPPT_ID = "solarlife_mppt_id"
CONF_SERVICE_UUID = "service_uuid"
CONF_NOTIFY_UUID = "notify_uuid"
CONF_WRITE_UUID = "write_uuid"
CONF_RETRIES = "retries"
CONF_TIMEOUT = "timeout"
CONF_PARAMETERS_INTERVAL = "parameters_interval"
CONF_REGISTER = "register"
CONF_ADDRESS = "address"

solarlife_mppt_ns = cg.esphome_ns.namespace(DOMAIN)
SolarlifeMppt = solarlife_mppt_ns.class_(
    "SolarlifeMppt", cg.PollingComponent, ble_client.BLEClientNode
)
SolarlifeMpptEntity = solarlife_mppt_ns.class_("SolarlifeMpptEntity")

CONFIG_SCHEMA = (
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(SolarlifeMppt),
            cv.Optional(CONF_SERVICE_UUID, default=0xFF00): cv.uint16_t,
            cv.Optional(CONF_NOTIFY_UUID, default=0xFF01): cv.uint16_t,
            cv.Optional(CONF_WRITE_UUID, default=0xFF02): cv.uint16_t,
            cv.Optional(CONF_RETRIES, default=10): cv.int_range(min=0, max=10),
            cv.Optional(
                CONF_TIMEOUT, default="2s"
            ): cv.positive_time_period_milliseconds,
            cv.Optional(
                CONF_PARAMETERS_INTERVAL, default="300s"
            ): cv.positive_time_period_milliseconds,
        }
    )
    .extend(ble_client.BLE_CLIENT_SCHEMA)
    .extend(cv.polling_component_schema("20s"))
)

SOLARLIFE_MPPT_COMPONENT_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_SOLARLIFE_MPPT_ID): cv.use_id(SolarlifeMppt),
        cv.Required(CONF_REGISTER): cv.string,
        # Names repeat across controller blocks, so the generated package passes the
        # address the entity belongs to.
        cv.Optional(CONF_ADDRESS): cv.uint16_t,
    }
)


async def to_code(config: ConfigType) -> None:
    var = await ble_client.new_ble_node_component(config)
    cg.add(var.set_service_uuid(config[CONF_SERVICE_UUID]))
    cg.add(var.set_notify_uuid(config[CONF_NOTIFY_UUID]))
    cg.add(var.set_write_uuid(config[CONF_WRITE_UUID]))
    cg.add(var.set_retries(config[CONF_RETRIES]))
    cg.add(var.set_command_timeout(config[CONF_TIMEOUT]))
    cg.add(var.set_parameters_interval(config[CONF_PARAMETERS_INTERVAL]))

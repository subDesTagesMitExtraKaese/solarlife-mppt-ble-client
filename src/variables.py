from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Tuple, Union, Optional


class FunctionCodes(Enum):
    # Read
    READ_STATUS_REGISTER  = 0x02 # Read the switch input status
    READ_PARAMETER        = 0x03 # Read multiple hold registers
    READ_MEMORY           = 0x04 # Read input register
    # Write
    WRITE_STATUS_REGISTER = 0x05 # Write single register
    WRITE_MEMORY_SINGLE   = 0x06 # Write single hold register
    WRITE_MEMORY_RANGE    = 0x10 # Write multiple hold registers

@dataclass
class Variable():
    address: int
    is_32_bit: bool
    is_signed: bool
    function_codes: list[int]
    unit: str
    multiplier: int
    name: str
    friendly_name: str
    func: Union[Callable[int, str], None]
    binary_payload: Union[Tuple[str, str], None]

class VariableContainer:
    def __init__(self, variables: List[Variable]):
        self._variables = variables
        self._variable_map = {var.name: var for var in variables}

    def __getitem__(self, key: Union[int, str, slice]) -> Variable:
        if isinstance(key, int):
            return self._variables[key]
        elif isinstance(key, str):
            return self._variable_map[key]
        elif isinstance(key, slice):
            return VariableContainer(self._variables[key])
        else:
            raise TypeError("Key must be an integer index, a variable name string, or a slice.")

    def __len__(self):
        return len(self._variables)

    def __iter__(self):
        return iter(self._variables)
    
    def __add__(self, other):
        return VariableContainer(self._variables + other._variables)

    def __bool__(self):
        return len(self._variables) > 0

    def items(self):
        return self._variable_map.items()
    
    def get(self, key: str) -> Optional[Variable]:
        if isinstance(key, str):
            return self._variable_map.get(key)
        else:
            raise TypeError("Key must be a variable name string.")

def _get_functional_status_registers(function_codes: list[int], offset: int):
    return [
        # Controller functional status 1
        Variable(offset, False, False, function_codes, "", 0, "maximum_system_voltage_level", "Maximum system voltage level",
            lambda x: ["", "12V", "24V", "36V", "48V"][(x >> 12) & 0xF], None),
        Variable(offset, False, False, function_codes, "", 0, "minimum_system_voltage_level", "Minimum system voltage level",
            lambda x: ["", "12V", "24V", "36V", "48V"][(x >>  8) & 0xF], None),
        Variable(offset, False, False, function_codes, "", 0, "controller_series", "Controller Series",
            lambda x: ["MT series", "DC series", "SMR series"][(x >>  4) & 0xF], None),
        Variable(offset, False, False, function_codes, "", 0, "battery_type", "Battery type",
            lambda x: ["Lithium battery", "Non Lithium battery"][(x >>  0) & 0xF], None),

        # Controller functional status 2
        Variable(offset + 1, False, False, function_codes, "", 0, "infrared_function_available", "Is infrared function available",
            lambda x: (x >> 15) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "automatic_power_reduction_available", "Is automatic power reduction setting available(only in 365 mode)",
            lambda x: (x >> 14) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "charging_at_zero_celsius_available", "Is 0°C prohibit charging setting available",
            lambda x: (x >> 13) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "grade_of_rated_voltage_available", "Is grade of rated voltage setting available",
            lambda x: (x >> 12) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "overcharge_recovery_voltage_available", "Is overcharge recovery voltage setting available (only lithium battery)",
            lambda x: (x >> 11) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "overcharge_protection_available", "Is overcharge protection setting available (only lithium battery)",
            lambda x: (x >> 10) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "floating_charge_voltage_available", "Is floating charge voltage setting available",
            lambda x: (x >>  9) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "equilibrium_charge_voltage_available", "Is equilibrium charge voltage setting available",
            lambda x: (x >>  8) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "strong_charging_voltage_available", "Is strong charging voltage setting available",
            lambda x: (x >>  7) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "low_voltage_recovery_voltage_available", "Is low voltage recovery setting available",
            lambda x: (x >>  6) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "low_voltage_protection_voltage_available", "Is low voltage protection setting available",
            lambda x: (x >>  5) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "battery_type_available", "Is Battery Type setting available",
            lambda x: (x >>  4) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "backlight_time_available", "Is Backlight Time setting available",
            lambda x: (x >>  3) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "device_time_available", "Is Device Time setting available",
            lambda x: (x >>  2) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "device_id_available", "Is Device ID setting available",
            lambda x: (x >>  1) & 1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, function_codes, "", 0, "device_password_available", "Is Device password setting available",
            lambda x: (x >>  0) & 1 == 1, ("True", "False")),

        # Controller functional status 3
        Variable(offset + 2, False, False, function_codes, "", 0, "six_time_frame_mode_available", "Is Six Time Frame Mode available",
            lambda x: (x >> 7) & 1 == 1, ("True", "False")),
        Variable(offset + 2, False, False, function_codes, "", 0, "five_time_frame_mode_available", "Is Five Time Frame Mode available",
            lambda x: (x >> 6) & 1 == 1, ("True", "False")),
        Variable(offset + 2, False, False, function_codes, "", 0, "timing_control_mode_available", "Is Timing Control available",
            lambda x: (x >> 5) & 1 == 1, ("True", "False")),
        Variable(offset + 2, False, False, function_codes, "", 0, "t0t_mode_available", "Is T0T Mode available",
            lambda x: (x >> 4) & 1 == 1, ("True", "False")),
        Variable(offset + 2, False, False, function_codes, "", 0, "fixed_duration_mode_available", "Is Fixed Light Up Duration Mode available",
            lambda x: (x >> 3) & 1 == 1, ("True", "False")),
        Variable(offset + 2, False, False, function_codes, "", 0, "d2d_mode_available", "Is D2D Mode available",
            lambda x: (x >> 2) & 1 == 1, ("True", "False")),
        Variable(offset + 2, False, False, function_codes, "", 0, "24h_mode_available", "Is 24H Mode available",
            lambda x: (x >> 1) & 1 == 1, ("True", "False")),
        Variable(offset + 2, False, False, function_codes, "", 0, "manual_operation_mode_available", "Is Manual Operation Mode available",
            lambda x: (x >> 0) & 1 == 1, ("True", "False")),

        # Controller functional status 4 (reserved)
        # Variable(offset + 3, False, False, function_codes, "", 0, "controller_functional_status_4", "Controller functional status 4", None, None),
    ]

def _get_device_status_registers(offset: int):
    return [
        # Battery status
        Variable(offset, False, False, [0x04], "", 0, "battery_temperature_protection_status", "Battery temperature protection status",
            lambda x: ["Normal", "High temperature protection"][(x >> 4) & 0x1], None),
        Variable(offset, False, False, [0x04], "", 0, "battery_voltage_protection_status", "Battery voltage protection status",
            lambda x: ["Normal", "Over voltage protection", "Voltage is low", "Low voltage protection"][(x >> 0) & 0xF], None),

        # Charge status
        Variable(offset + 1, False, False, [0x04], "", 0, "solar_panel_charge_disabled", "Is charging manually disabled", 
            lambda x: (x >> 6) & 0x1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, [0x04], "", 0, "solar_panel_is_night", "Is solar panel night", 
            lambda x: (x >> 5) & 0x1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, [0x04], "", 0, "solar_panel_charge_over_temperature", "Is charge over temperature", 
            lambda x: (x >> 4) & 0x1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, [0x04], "", 0, "solar_panel_charge_state", "Solar panel charge status", 
            lambda x: ["Not charging", "Float charge", "Boost charge", "Equal charge"][(x >> 2) & 0x3], None),
        Variable(offset + 1, False, False, [0x04], "", 0, "solar_panel_charge_state", "Is charge fault", 
            lambda x: (x >> 1) & 0x1 == 1, ("True", "False")),
        Variable(offset + 1, False, False, [0x04], "", 0, "solar_panel_is_charging", "Solar panel is charging", 
            lambda x: (x >> 0) & 0x1 == 1, ("True", "False")),

        # Discharge status
        Variable(offset + 2, False, False, [0x04], "", 0, "load_state", "Load status",
            lambda x: ["Light load", "Moderate load", "Rated load", "Overload"][(x >> 12) & 0x3], None),
        Variable(offset + 2, False, False, [0x04], "", 0, "output_short_circuit", "Is output short circuit", 
            lambda x: (x >> 11) & 0x1 == 1, ("True", "False")),
        Variable(offset + 2, False, False, [0x04], "", 0, "output_hardware_protection", "Is output hardware protection", 
            lambda x: (x >>  4) & 0x1 == 1, ("True", "False")),
        Variable(offset + 2, False, False, [0x04], "", 0, "output_open_circuit_protection", "Is output open circuit protection", 
            lambda x: (x >>  3) & 0x1 == 1, ("True", "False")),
        Variable(offset + 2, False, False, [0x04], "", 0, "output_over_temperature", "Is output over temperature", 
            lambda x: (x >>  2) & 0x1 == 1, ("True", "False")),
        Variable(offset + 2, False, False, [0x04], "", 0, "output_fault", "Is output fault", 
            lambda x: (x >> 1) & 0x1 == 1, ("True", "False")),
        Variable(offset + 2, False, False, [0x04], "", 0, "load_is_enabled", "Is load enabled", 
            lambda x: (x >> 0) & 0x1 == 1, ("True", "False")),
    ]

real_time_status = VariableContainer([
    Variable(0x2000, False, False, [0x02], "", 0, "equipment_internal_over_temperature", "Equipment internal over temperature",
        lambda x: ["Normal", "Over temperature"][x], None),
    Variable(0x200C, False, False, [0x02], "", 0, "day_or_night", "Day or night",
        lambda x: ["Day", "Night"][x], None),
])

status_registers = VariableContainer(
    _get_functional_status_registers([0x04], 0x3011) + [

    Variable(0x3015, False, False, [0x04], "V", 100, "lvd_min_setting_value", "Low voltage detect min setting value", None, None),
    Variable(0x3016, False, False, [0x04], "V", 100, "lvd_max_setting_value", "Low voltage detect max setting value", None, None),
    Variable(0x3017, False, False, [0x04], "V", 100, "lvd_default_setting_value", "Low voltage detect default setting value", None, None),
    Variable(0x3018, False, False, [0x04], "V", 100, "lvr_min_setting_value", "Low voltage recovery min setting value", None, None),
    Variable(0x3019, False, False, [0x04], "V", 100, "lvr_max_setting_value", "Low voltage recovery max setting value", None, None),
    Variable(0x301A, False, False, [0x04], "V", 100, "lvr_default_setting_value", "Low voltage recovery default setting value", None, None),
    Variable(0x301B, False, False, [0x04], "V", 100, "cvt_min_setting_value", "Charge target voltage min setting value for Li Series controller", None, None),
    Variable(0x301C, False, False, [0x04], "V", 100, "cvt_max_setting_value", "Charge target voltage max setting value for Li Series controller", None, None),
    Variable(0x301D, False, False, [0x04], "V", 100, "cvt_default_setting_value", "Charge target voltage default setting value Li Series controller", None, None),
    Variable(0x301E, False, False, [0x04], "V", 100, "cvr_min_setting_value", "Charge recovery voltage min setting value Li Series controller", None, None),
    Variable(0x301F, False, False, [0x04], "V", 100, "cvr_max_setting_value", "Charge recovery voltage max setting value Li Series controller", None, None),
    Variable(0x3020, False, False, [0x04], "V", 100, "cvr_default_setting_value", "Charge recovery voltage default setting value Li Series controller", None, None),
    Variable(0x3021, False, False, [0x04], "V", 100, "day_night_threshold_voltage_min", "Day/Night threshold voltage min setting value", None, None),
    Variable(0x3022, False, False, [0x04], "V", 100, "day_night_threshold_voltage_max", "Day/Night threshold voltage max setting value", None, None),
    Variable(0x3023, False, False, [0x04], "V", 100, "day_night_threshold_voltage_default", "Day/Night threshold voltage default setting value", None, None),
    Variable(0x3024, False, False, [0x04], "V", 100, "dimming_voltage_min", "Dimming voltage min setting value", None, None),
    Variable(0x3025, False, False, [0x04], "V", 100, "dimming_voltage_max", "Dimming voltage max setting value", None, None),
    Variable(0x3026, False, False, [0x04], "V", 100, "dimming_voltage_default", "Dimming voltage default setting value", None, None),
    Variable(0x3027, False, False, [0x04], "A", 100, "load_current_min", "Load current min setting value", None, None),
    Variable(0x3028, False, False, [0x04], "A", 100, "load_current_max", "Load current max setting value", None, None),
    Variable(0x3029, False, False, [0x04], "V", 100, "cvt_cvr_max_dropout_voltage", "Charge target and recovery voltage max allow dropout voltage for Li-series controller", None, None),
    Variable(0x302A, False, False, [0x04], "V", 100, "cvt_cvr_min_dropout_voltage", "Charge target and recovery voltage min allow dropout voltage for Li-series controller", None, None),
    Variable(0x302B, False, False, [0x04], "V", 100, "lvd_lvr_min_dropout_voltage", "Low voltage detect and recovery min allow dropout voltage", None, None),
    Variable(0x302C, False, False, [0x04], "V", 100, "min_allow_dropout_voltage", "CVR and LVD & CVT and LVR Min allow dropout voltage", None, None),
    Variable(0x3030, False, False, [0x04], "", 1, "equipment_id", "Equipment ID", None, None),
    Variable(0x3031, False, False, [0x04], "", 1, "run_days", "Number of running days", None, None),
    Variable(0x3032, False, False, [0x04], "V", 100, "battery_voltage_level", "Current battery voltage level", None, None),

    ] + _get_device_status_registers(0x3033) + [

    Variable(0x3036, False, False, [0x04], "℃", 100, "environment_temperature", "Environment temperature", None, None),
    Variable(0x3037, False, False, [0x04], "℃", 100, "device_built_in_temperature", "Device built-intemperature", None, None),
    Variable(0x3038, False, False, [0x04], "", 1, "battery_empty_times", "Battery empty times", None, None),
    Variable(0x3039, False, False, [0x04], "", 1, "battery_full_times", "Battery full times", None, None),
    Variable(0x303A, False, False, [0x04], "", 1, "over_voltage_protection_times", "Over-voltage protection times", None, None),
    Variable(0x303B, False, False, [0x04], "", 1, "over_current_protection_times", "Over-current protection times", None, None),
    Variable(0x303C, False, False, [0x04], "", 1, "short_circuit_protection_times", "short-circuit protection times", None, None),
    Variable(0x303D, False, False, [0x04], "", 1, "open_circuit_protection_times", "Open-circuit protection times", None, None),
    Variable(0x303E, False, False, [0x04], "", 1, "hardware_protection_times", "Hardware protection times", None, None),
    Variable(0x303F, False, False, [0x04], "", 1, "charge_over_temperature_protection_times", "Charge over-temperature protection times", None, None),
    Variable(0x3040, False, False, [0x04], "", 1, "discharge_over_temperature_protection_times", "Discharge over-temperature protection time", None, None),
    Variable(0x3045, False, False, [0x04], "%", 1, "battery_percentage", "Battery remaining capacity", None, None),
    Variable(0x3046, False, False, [0x04], "V", 100, "battery_voltage", "Battery voltage", None, None),
    Variable(0x3047, False, True,  [0x04], "A", 100, "battery_current", "Battery current", None, None),
    Variable(0x3048, True,  True,  [0x04], "W", 100, "battery_power", "Battery power", None, None),
    Variable(0x304A, False, False, [0x04], "V", 100, "load_voltage", "Load voltage", None, None),
    Variable(0x304B, False, False, [0x04], "A", 100, "load_current", "Load current", None, None),
    Variable(0x304C, True,  False, [0x04], "W", 100, "load_power", "Load power", None, None),
    Variable(0x304E, False, False, [0x04], "V", 100, "solar_panel_voltage", "Solar panel voltage", None, None),
    Variable(0x304F, False, False, [0x04], "A", 100, "solar_panel_current", "Solar panel current", None, None),
    Variable(0x3050, True,  False, [0x04], "W", 100, "solar_panel_power", "Solar panel power", None, None),
    Variable(0x3052, False, False, [0x04], "kWh", 100, "solar_panel_daily_energy", "Daily solar panel energy", None, None),
    Variable(0x3053, True,  False, [0x04], "kWh", 100, "solar_panel_total_energy", "Total solar panel energy", None, None),
    Variable(0x3055, False, False, [0x04], "kWh", 100, "load_daily_energy", "Daily load energy", None, None),
    Variable(0x3056, True,  False, [0x04], "kWh", 100, "load_total_energy", "Total load energy", None, None),
    Variable(0x3058, False, False, [0x04], "min", 1, "total_light_time_during_the_day", "Total light time during the day", None, None),
    Variable(0x309D, False, False, [0x04], "", 1, "run_days", "Number of running days", None, None),
    Variable(0x30A0, False, False, [0x04], "V", 100, "battery_voltage", "Battery voltage", None, None),
    Variable(0x30A1, False, True,  [0x04], "A", 100, "battery_current", "Battery current", None, None),
    Variable(0x30A2, False, False, [0x04], "℃", 100, "environment_temperature", "Environment temperature", None, None),

    ] + _get_device_status_registers(0x30A3) + [

    Variable(0x30A6, False, False, [0x04], "", 1, "battery_empty_times", "Battery empty times", None, None),
    Variable(0x30A7, False, False, [0x04], "", 1, "battery_full_times", "Battery full times", None, None),
    Variable(0x30A8, False, False, [0x04], "V", 100, "battery_daily_voltage_maximum", "Highest battery voltage today", None, None),
    Variable(0x30A9, False, False, [0x04], "V", 100, "battery_daily_voltage_minimum", "Lowest battery voltage today", None, None),
    Variable(0x3125, False, False, [0x04], "V", 100, "load_voltage", "Load voltage", None, None),
    Variable(0x3126, False, False, [0x04], "A", 100, "load_current", "Load current", None, None),
    Variable(0x3127, True,  False, [0x04], "W", 100, "load_power", "Load power", None, None),
    Variable(0x3129, False, False, [0x04], "kWh", 100, "load_daily_energy", "Daily load energy", None, None),
    Variable(0x312E, True,  False, [0x04], "kWh", 100, "load_total_energy", "Total load energy", None, None),
    Variable(0x316C, False, False, [0x04], "", 1, "run_days", "The number of running days", None, None),
])

rated_parameters = VariableContainer([
    Variable(0x3000, False, False, [0x04], "V", 100, "solar_panel_rated_voltage", "Solar panel rated voltage", None, None),
    Variable(0x3001, False, False, [0x04], "A", 100, "solar_panel_rated_current", "Solar panel rated current", None, None),
    Variable(0x3002, True,  False, [0x04], "W", 100, "solar_panel_rated_power", "Solar panel rated power", None, None),
    Variable(0x3004, False, False, [0x04], "V", 100, "battery_rated_voltage", "Battery rated voltage", None, None),
    Variable(0x3005, False, False, [0x04], "A", 100, "battery_rated_current", "Battery rated current", None, None),
    Variable(0x3006, True,  False, [0x04], "W", 100, "battery_rated_power", "Battery rated power", None, None),
    Variable(0x3008, False, False, [0x04], "V", 100, "load_rated_voltage", "Load rated voltage", None, None),
    Variable(0x3009, False, False, [0x04], "A", 100, "load_rated_current", "Load rated current", None, None),
    Variable(0x300A, True,  False, [0x04], "W", 100, "load_rated_power", "Load rated power", None, None),
])

read_only_registers = VariableContainer(
    _get_functional_status_registers([0x03], 0x8FF0) + [

    Variable(0x8FF4, False, False, [0x03], "V", 100, "lvd_min_setting_value", "Low voltage detect min setting value", None, None),
    Variable(0x8FF5, False, False, [0x03], "V", 100, "lvd_max_setting_value", "Low voltage detect max setting value", None, None),
    Variable(0x8FF6, False, False, [0x03], "V", 100, "lvd_default_setting_value", "Low voltage detect default setting value", None, None),
    Variable(0x8FF7, False, False, [0x03], "V", 100, "lvr_min_setting_value", "Low voltage recovery min setting value", None, None),
    Variable(0x8FF8, False, False, [0x03], "V", 100, "lvr_max_setting_value", "Low voltage recovery max setting value", None, None),
    Variable(0x8FF9, False, False, [0x03], "V", 100, "lvr_default_setting_value", "Low voltage recovery default setting value", None, None),
    Variable(0x8FFA, False, False, [0x03], "V", 100, "cvt_min_setting_value", "Charge target voltage min setting value for Li Series controller", None, None),
    Variable(0x8FFB, False, False, [0x03], "V", 100, "cvt_max_setting_value", "Charge target voltage max setting value Li Series controller", None, None),
    Variable(0x8FFC, False, False, [0x03], "V", 100, "cvt_default_setting_value", "Charge target voltage default setting value Li Series controller", None, None),
    Variable(0x8FFD, False, False, [0x03], "V", 100, "cvr_min_setting_value", "Charge recovery voltage min setting value Li Series controller", None, None),
    Variable(0x8FFE, False, False, [0x03], "V", 100, "cvr_max_setting_value", "Charge recovery voltage max setting value Li Series controller", None, None),
    Variable(0x8FFF, False, False, [0x03], "V", 100, "cvr_default_setting_value", "Charge recovery voltage default setting value Li Series controller", None, None),
    Variable(0x9000, False, False, [0x03], "V", 100, "day_night_threshold_voltage_min", "Day/Night threshold voltage min setting value", None, None),
    Variable(0x9001, False, False, [0x03], "V", 100, "day_night_threshold_voltage_max", "Day/Night threshold voltage max setting value", None, None),
    Variable(0x9002, False, False, [0x03], "V", 100, "day_night_threshold_voltage_default", "Day/Night threshold voltage default setting value", None, None),
    Variable(0x9003, False, False, [0x03], "V", 100, "dimming_voltage_min", "Dimming voltage min setting value", None, None),
    Variable(0x9004, False, False, [0x03], "V", 100, "dimming_voltage_max", "Dimming voltage max setting value", None, None),
    Variable(0x9005, False, False, [0x03], "V", 100, "dimming_voltage_default", "Dimming voltage default setting value", None, None),
    Variable(0x9006, False, False, [0x03], "A", 100, "load_current_min", "Load current min setting value", None, None),
    Variable(0x9007, False, False, [0x03], "A", 100, "load_current_max", "Load current max setting value", None, None),

    Variable(0x9008, False, False, [0x03], "V", 100, "battery_voltage_level", "Current battery voltage level", None, None),
    Variable(0x9009, False, False, [0x03], "V", 100, "cvt_cvr_max_dropout_voltage", "Charge target and recovery voltage max allow dropout voltage for Li-series controller", None, None),
    Variable(0x900A, False, False, [0x03], "V", 100, "cvt_cvr_min_dropout_voltage", "Charge target and recovery voltage min allow dropout voltage for Li-series controller", None, None),
    Variable(0x900B, False, False, [0x03], "V", 100, "lvd_lvr_min_dropout_voltage", "Low voltage detect and recovery min allow dropout voltage", None, None),
    Variable(0x900C, False, False, [0x03], "V", 100, "min_allow_dropout_voltage", "CVR and LVD & CVT and LVR Min allow dropout voltage", None, None),
])

device_parameters = VariableContainer([
    Variable(0x9017, False, False, [0x03, 0x06, 0x10], "ss", 1, "real_time_clock_second", "Real-time clock second", None, None),
    Variable(0x9018, False, False, [0x03, 0x06, 0x10], "mm", 1, "real_time_clock_minute", "Real-time clock minute", None, None),
    Variable(0x9019, False, False, [0x03, 0x06, 0x10], "hh", 1, "real_time_clock_hour", "Real-time clock hour", None, None),
    Variable(0x901A, False, False, [0x03, 0x06, 0x10], "dd", 1, "real_time_clock_day", "Real-time clock day", None, None),
    Variable(0x901B, False, False, [0x03, 0x06, 0x10], "MM", 1, "real_time_clock_month", "Real-time clock month", None, None),
    Variable(0x901C, False, False, [0x03, 0x06, 0x10], "yy", 1, "real_time_clock_year", "Real-time clock year (00-99)", None, None),
    Variable(0x901D, False, False, [0x03, 0x06, 0x10], "baud", 0, "baud_rate", "Baud rate",
        lambda x: ["4800", "9600", "19200", "57600", "115200"][x & 0xF], None),
    Variable(0x901E, False, False, [0x03, 0x06, 0x10], "s", 1, "backlight_time", "Backlight time", None, None),
    Variable(0x901F, False, False, [0x03, 0x06, 0x10], "", 0, "device_password", "Device password",
        lambda x: str(max((x>>12) & 0xF, 9)) + 
                    str(max((x>> 8) & 0xF, 9)) + 
                    str(max((x>> 4) & 0xF, 9)) + 
                    str(max((x>> 0) & 0xF, 9)), None),
    Variable(0x9020, False, False, [0x03, 0x06, 0x10], "", 1, "slave_id", "Slave ID", None, None),
])

battery_and_load_parameters = VariableContainer([
    Variable(0x9021, False, False, [0x03, 0x06, 0x10], "", 0, "battery_type", "Battery type",
        lambda x: ["Lithium", "Liquid", "GEL", "AGM"][(x >>  0) & 0xF], None),
    Variable(0x9022, False, False, [0x03, 0x06, 0x10], "V", 100, "low_voltage_protection_voltage", "Low voltage protection",  None, None),
    Variable(0x9023, False, False, [0x03, 0x06, 0x10], "V", 100, "low_voltage_recovery_voltage", "Low voltage recovery", None, None),
    Variable(0x9024, False, False, [0x03, 0x06, 0x10], "V", 100, "boost_voltage", "Boost voltage", None, None),
    Variable(0x9025, False, False, [0x03, 0x06, 0x10], "V", 100, "equalizing_voltage", "Equalizing voltage", None, None),
    Variable(0x9026, False, False, [0x03, 0x06, 0x10], "V", 100, "float_voltage", "Float voltage", None, None),
    Variable(0x9027, False, False, [0x03, 0x06, 0x10], "", 0, "system_rated_voltage_level", "System rated voltage level",
        lambda x: ["Auto", "12V", "24V", "36V", "48V", "60V", "110V", "120V", "220V", "240V"][x], None),
    Variable(0x9028, False, False, [0x03, 0x06, 0x10], "V", 100, "charge_target_voltage_for_lithium", "Charge target voltage for lithium", None, None),
    Variable(0x9029, False, False, [0x03, 0x06, 0x10], "V", 100, "charge_recovery_voltage_for_lithium", "Charge recovery voltage for lithium", None, None),
    Variable(0x902A, False, False, [0x03, 0x06, 0x10], "", 0, "charging_at_zero_celsius", "0°C charging",
        lambda x: ["Normal charging", "No charging", "Slow charging"][x & 0xF], None),
    Variable(0x902B, False, False, [0x03, 0x06, 0x10], "", 0, "mt_series_load_mode", "Load mode for MT series controller",
        lambda x: (["Always on", "Dusk to dawn"] + 
                    [f"Night light on time {n} hours" for n in range(2, 10)] + 
                    ["Manual", "T0T", "Timing switch"])[x], None),
    Variable(0x902C, False, False, [0x03, 0x06, 0x10], "", 0, "mt_series_manual_control_default", "MT Series manual control mode default setting",
        lambda x: ["On", "Off"][x], ("On", "Off")),
    Variable(0x902D, False, False, [0x03, 0x06, 0x10], "min", 1, "mt_series_timing_period_1", "MT Series timing opening period 1",
        lambda x: ((x >> 8) & 0xFF) * 60 + max(x & 0xFF, 59), None),
    Variable(0x902E, False, False, [0x03, 0x06, 0x10], "min", 1, "mt_series_timing_period_2", "MT Series timing opening period 2",
        lambda x: ((x >> 8) & 0xFF) * 60 + max(x & 0xFF, 59), None),
    Variable(0x902F, False, False, [0x03, 0x06, 0x10], "sec", 1, "timed_start_time_1_seconds", "Timed start time 1-seconds", None, None),
    Variable(0x9030, False, False, [0x03, 0x06, 0x10], "min", 1, "timed_start_time_1_minutes", "Timed start time 1-minute", None, None),
    Variable(0x9031, False, False, [0x03, 0x06, 0x10], "hour", 1, "timed_start_time_1_hours", "Timed start time 1-hour", None, None),
    Variable(0x9032, False, False, [0x03, 0x06, 0x10], "sec", 1, "timed_off_time_1_seconds", "Timed off time 1-seconds", None, None),
    Variable(0x9033, False, False, [0x03, 0x06, 0x10], "min", 1, "timed_off_time_1_minutes", "Timed off time 1-minute", None, None),
    Variable(0x9034, False, False, [0x03, 0x06, 0x10], "hour", 1, "timed_off_time_1_hours", "Timed off time 1-hour", None, None),
    Variable(0x9035, False, False, [0x03, 0x06, 0x10], "sec", 1, "timed_start_time_2_seconds", "Timed start time 2-seconds", None, None),
    Variable(0x9036, False, False, [0x03, 0x06, 0x10], "min", 1, "timed_start_time_2_minutes", "Timed start time 2-minute", None, None),
    Variable(0x9037, False, False, [0x03, 0x06, 0x10], "hour", 1, "timed_start_time_2_hours", "Timed start time 2-hour", None, None),
    Variable(0x9038, False, False, [0x03, 0x06, 0x10], "sec", 1, "timed_off_time_2_seconds", "Timed off time 2-seconds", None, None),
    Variable(0x9039, False, False, [0x03, 0x06, 0x10], "min", 1, "timed_off_time_2_minutes", "Timed off time 2-minute", None, None),
    Variable(0x903A, False, False, [0x03, 0x06, 0x10], "hour", 1, "timed_off_time_2_hours", "Timed off time 2-hour", None, None),
    Variable(0x903B, False, False, [0x03, 0x06, 0x10], "", 0, "time_control_period_selection", "Time control period selection",
        lambda x: ["1 period", "2 periods"][x], None),
    Variable(0x903C, False, False, [0x03, 0x06, 0x10], "V", 100, "light_controlled_dark_voltage", "Light controlled dark voltage", None, None),
    Variable(0x903D, False, False, [0x03, 0x06, 0x10], "min", 1, "day_night_delay_time", "Day/Night delay time", None, None),
    Variable(0x903E, False, False, [0x03, 0x06, 0x10], "%", 0.1, "dc_series_timing_control_time_1_dimming", "DC series timing control time 1 dimming", None, None),
    Variable(0x903F, False, False, [0x03, 0x06, 0x10], "%", 0.1, "dc_series_timing_control_time_2_dimming", "DC series timing control time 2 dimming", None, None),
    Variable(0x9040, False, False, [0x03, 0x06, 0x10], "min", 1.0/30, "dc_series_time_1", "DC Series time 1", None, None),
    Variable(0x9041, False, False, [0x03, 0x06, 0x10], "%", 0.1, "dc_series_time_1_dimming", "DC Series the time 1 dimming", None, None),
    Variable(0x9042, False, False, [0x03, 0x06, 0x10], "min", 1.0/30, "dc_series_time_2", "DC Series time 2", None, None),
    Variable(0x9043, False, False, [0x03, 0x06, 0x10], "%", 0.1, "dc_series_time_2_dimming", "DC Series the time 2 dimming", None, None),
    Variable(0x9044, False, False, [0x03, 0x06, 0x10], "sec", 1.0/30, "dc_series_time_3", "DC Series time 3", None, None),
    Variable(0x9045, False, False, [0x03, 0x06, 0x10], "%", 0.1, "dc_series_time_3_dimming", "DC Series the time 3 dimming", None, None),
    Variable(0x9046, False, False, [0x03, 0x06, 0x10], "sec", 1.0/30, "dc_series_time_4", "DC Series time 4", None, None),
    Variable(0x9047, False, False, [0x03, 0x06, 0x10], "%", 0.1, "dc_series_time_4_dimming", "DC Series the time 4 dimming", None, None),
    Variable(0x9048, False, False, [0x03, 0x06, 0x10], "sec", 1.0/30, "dc_series_time_5", "DC Series time 5", None, None),
    Variable(0x9049, False, False, [0x03, 0x06, 0x10], "%", 0.1, "dc_series_time_5_dimming", "DC Series the time 5 dimming", None, None),
    Variable(0x904A, False, False, [0x03, 0x06, 0x10], "A", 100, "dc_series_load_current_limit", "DC Series load current limit", None, None),
    Variable(0x904B, False, False, [0x03, 0x06, 0x10], "", 0, "dc_series_auto_dimming", "DC Series auto dimming",
        lambda x: ["Auto dimming", "365 mode", "No dimming", "No dimming"][x & 0xF], None),
    Variable(0x904C, False, False, [0x03, 0x06, 0x10], "V", 100, "dc_series_dimming_voltage", "DC Series dimming voltage", None, None),
    Variable(0x904D, False, False, [0x03, 0x06, 0x10], "%", 1, "dc_series_dimming_percentage", "DC Series dimming percentage", None, None),
    Variable(0x904E, False, False, [0x03, 0x06, 0x10], "sec", 0.1, "sensing_delay_off_time", "Sensing delay off time", None, None),
    Variable(0x904F, False, False, [0x03, 0x06, 0x10], "%", 0.1, "infrared_dimming_when_no_people", "Dimming of Infrared Series controller when no people", None, None),
    Variable(0x9052, False, False, [0x03, 0x06, 0x10], "", 0, "light_controlled_switch", "Light controlled switch", None, ("On", "Off")),
    Variable(0x9053, False, False, [0x03, 0x06, 0x10], "V", 100, "light_controlled_daybreak_voltage", "Light-control led daybreak voltage", None, None),
    Variable(0x9054, False, False, [0x03, 0x06, 0x10], "%", 1, "dimming_percentage", "Dimming percentage for load test", None, None),
    Variable(0x9069, False, False, [0x03, 0x06, 0x10], "A", 100, "maximum_charging_current_setting", "Maximum charging current setting", None, None),
    Variable(0x906A, False, False, [0x03, 0x06, 0x10], "℃", 100, "over_temperature_protection", "Over temperature protection", None, None),
])

switches = VariableContainer([
    Variable(0x0000, False, False, [0x05], "", 0, "manual_control_switch", "Manual control switch", None, ("On", "Off")),
    Variable(0x0001, False, False, [0x05], "", 0, "test_key_trigger", "Test key on/off", None, ("On", "Off")),
    Variable(0x0002, False, False, [0x05], "", 0, "dc_series_timing_control_mode_switch", "DC Series timing control mode switch", None, ("On", "Off")),
    Variable(0x0003, False, False, [0x05], "", 0, "manual_control_charging_switch", "Manual control charging switch", None, ("On", "Off")),

    Variable(0x0008, False, False, [0x05], "", 0, "restore_system_default_values", "Restore system default values", None, ("Restore", "")),
    Variable(0x0009, False, False, [0x05], "", 0, "clear_device_statistics", "Clear running days, Power generation or consumption WH and historical minimum/maximum voltage", None, ("Clear", "")),
    Variable(0x000A, False, False, [0x05], "", 0, "clear_counters", "Clear all protection and fully charged times", None, ("Clear", "")),
    Variable(0x000B, False, False, [0x05], "", 0, "clear_charge_discharge_ah", "Clear charge/discharge AH", None, ("Clear", "")),
    Variable(0x000C, False, False, [0x05], "", 0, "clear_all", "Clear all of the above historical data", None, ("Clear", "")),
])

variables = (
    real_time_status +
    status_registers +
    rated_parameters +
    read_only_registers +
    device_parameters +
    battery_and_load_parameters +
    switches
)

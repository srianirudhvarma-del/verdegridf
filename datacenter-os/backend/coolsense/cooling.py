"""
coolsense/cooling.py -- SHOULD HAVE #16: cross-wiring with ThermOS
for a combined cooling-performance estimate.

coolingPerformance(rack, t) = flow(rack, t) * specificHeatConstant *
                               (T_return(rack, t) - T_supply(rack, t))

Pulls T_return/T_supply from ThermOS's existing per-rack temperature
feed (thermos/sensors.py's ThermalTelemetry) rather than adding new
sensors.
"""

# Specific heat of water, kJ/(L*K) -- standard constant, not calibrated per site.
DEFAULT_SPECIFIC_HEAT_CONSTANT = 4.186


def cooling_performance(
    flow_l_per_s: float,
    t_return_c: float,
    t_supply_c: float,
    *,
    specific_heat_constant: float = DEFAULT_SPECIFIC_HEAT_CONSTANT,
) -> float:
    """Returns cooling performance in kW."""
    return flow_l_per_s * specific_heat_constant * (t_return_c - t_supply_c)

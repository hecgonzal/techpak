from .cpu import get_cpu_info
from .device    import get_device_info
from .memory import get_memory_info
from .storage import get_storage_info
from .battery import get_battery_info
from .thermal import get_thermal_info
from .power import get_power_info
from .runtime import get_runtime_info
from .capabilities import get_capabilities_info
from .services import get_services_info

def get_sysinfo():
    return {
        "schema_version": "1.0",
        "timestamp": "",
        "sequence": 0,
        "device": get_device_info(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "storage": get_storage_info(),
        "battery": get_battery_info(),
        "thermal": get_thermal_info(),
        "power": get_power_info(),
        "runtime": get_runtime_info(),
        "capabilities": get_capabilities_info(),
        "services": get_services_info(),
    }
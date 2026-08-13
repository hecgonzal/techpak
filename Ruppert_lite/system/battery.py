import psutil

def battery():

    battery = psutil.sensors_battery()
    
    return {
        "percent": battery.percent if battery else None,
        "plugged": battery.power_plugged if battery else None,
        "secsleft": battery.secsleft if battery else None
    }
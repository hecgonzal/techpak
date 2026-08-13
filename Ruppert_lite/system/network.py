
import psutil
def network():

    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()

    interfaces = {}
    for iface, stat in stats.items():
        interfaces[iface] = {
            "is_up": stat.isup,
            "speed": stat.speed,  # Mbps
            "mtu": stat.mtu,
            "addresses": [
                addr.address for addr in addrs.get(iface, [])
                if addr.family == 2  # AF_INET (IPv4)
            ]
        }

    return {
        "interfaces": interfaces,
        "is_up": any(stat.isup for stat in stats.values()),
        "active_interfaces": [iface for iface, stat in stats.items() if stat.isup]
    }
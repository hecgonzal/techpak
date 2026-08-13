from .battery import battery
from .network import network

class SystemTools:
    def __init__(self):
        self.battery_info = battery()
        self.network_info = network()

    def battery(self, field=None):
        if field:
            return self.battery_info.get(field, None)
        return self.battery_info

    def network(self, field=None):
        if field:
            return self.network_info.get(field, None)
        return self.network_info
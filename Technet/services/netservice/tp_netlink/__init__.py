from .hop_count import get_hop_count
from .mesh_route import get_mesh_route
from .link_quality import get_link_quality
from ...packservice.tp_ruppertlog import service_logged


@service_logged("tp-netlink")
def get_netlink_packet():
    """Build the current tp-netlink packet from lightweight field collectors."""
    return {
        "hop_count": get_hop_count(),
        "mesh_route": get_mesh_route(),
        "link_quality": get_link_quality(),
    }

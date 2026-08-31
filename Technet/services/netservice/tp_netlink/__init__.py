from .hop_count import get_hop_count
from .mesh_route import get_mesh_route
from .link_quality import get_link_quality
from .session_token import get_session_token
from .encryption import get_encryption


def get_netlink_packet():
    """Build the current tp-netlink packet from lightweight field collectors."""
    return {
        "hop_count": get_hop_count(),
        "mesh_route": get_mesh_route(),
        "link_quality": get_link_quality(),
        "session_token": get_session_token(),
        "encryption": get_encryption(),
    }

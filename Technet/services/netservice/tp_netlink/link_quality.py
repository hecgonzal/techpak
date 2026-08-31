"""Link-quality field for tp-netlink.

This is intentionally lightweight and conservative: Linux networking tools can
report signal or quality values, but that depends on radio hardware and drivers.
We return a neutral placeholder unless a concrete source is available.
"""


def get_link_quality():
    """Return a link-quality string for the current network path."""
    return "unknown"

"""Hop-count field for tp-netlink.

TODO: this value is expected to be updated by tp-msgbus mesh routing logic once
network topology awareness is implemented. For now we keep the default local
network hop count at 1.
"""


def get_hop_count():
    """Return the current mesh hop count for the local packet."""
    return 1

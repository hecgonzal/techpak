"""Deprecated compatibility stub; encryption is not a Netlink route field.

Transport encryption is negotiated by the secure transport. This helper is not
used by the Netlink packet builder and must not imply that a link is protected.
"""


def get_encryption():
    """Return the legacy unknown placeholder; inspect transport state instead."""
    return "unknown"

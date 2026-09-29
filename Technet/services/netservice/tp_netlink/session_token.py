"""Deprecated compatibility stub; session tokens belong to tp-authlite.

This value is not included in the Netlink route packet. Do not use this helper
for authentication or authorization.
"""


def get_session_token():
    """Return an empty legacy placeholder; no Netlink token is defined."""
    return ""

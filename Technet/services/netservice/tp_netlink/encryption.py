"""Encryption field for tp-netlink.

TODO: actual encryption negotiation and keying should be handled by tp-authlite or
other security layers. Until then we keep this explicitly unset.
"""


def get_encryption():
    """Return the encryption mode for the active network transport."""
    return "unknown"

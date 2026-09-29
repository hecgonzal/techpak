# tp-authlite MVP

This is an **in-process Linux/Python prototype**, not a network-ready security service. It provides typed packet construction and verification, Ed25519 device enrollment proof, BrainBoard-signed short-lived capability tokens, local SQLite policy/replay state, and a receiver-side dispatcher. It does not provide TLS/mTLS, sockets, a production CA, a GPIO provider, secure-element keys, distributed policy/registry, or synchronized logs.

## Packet and trust boundary

`packet_schema.json` is the machine-readable contract. The request's canonical signature covers packet version and kind, request ID, source/destination device IDs, the complete authorization values (including the signed token, audience, capability, nonce and sequence), and the typed payload. Human-readable aliases, priority and the separate `netlink` route object are transport hints and are not signed. Receivers must use IDs and signed authorization data—not aliases or route hints—for trust decisions.

Ed25519 signatures use RFC 8785 JSON Canonicalization Scheme bytes. The packet stays a JSON object; route metadata may be changed without changing the signed request. `tp-msgbus` remains transport-only and must never treat a parseable envelope as authenticated.

## Minimal in-process example

```python
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from Technet.services.netservice.tp_authlite import (
    Authlite, SQLiteAuthStore, build_request_packet,
)

brainboard_key = Ed25519PrivateKey.generate()  # Development example only.
store = SQLiteAuthStore(Path("/var/lib/techpack/authlite/registry.sqlite3"))
authlite = Authlite(
    authority_device_id="brainboard-01",
    authority_signing_key=brainboard_key,
    store=store,
)

# On a receiver device, construct a verifier with only the pinned public key:
# receiver_authlite = Authlite(
#     authority_device_id="brainboard-01",
#     authority_public_key=brainboard_key.public_key(),
#     store=receiver_store,
# )

# A real enrolled device key, token and allowlisted capability are required
# before constructing a request. This snippet only shows the packet API shape.
packet = build_request_packet(
    device_private_key,
    authority_id="brainboard-01",
    authority_public_key=brainboard_key.public_key(),
    token=device_token,
    source_device_id="watch-01",
    destination_device_id="brainboard-01",
    audience="tp-sysinfo",
    capability="telemetry.read",
    operation="sysinfo.get",
    arguments={"fields": ["battery"]},
    sequence=authlite.next_sequence("watch-01", "brainboard-01"),
)
```

Never use a generated demonstration authority key for a persistent BrainBoard installation. Load long-lived keys through `FileKeyStore` under a dedicated service account. The current file provider uses mode-restricted raw key files; it is not encrypted or hardware-backed.

## Security constraints

- Enrollment approval APIs and token issuance are local trusted-service APIs. Do not expose them through MsgBus until a transport authenticates the peer and administration is separately authorized.
- `DevelopmentCLIConfirmation` and `DevelopmentCallbackConfirmation` are not production physical-presence proof. Replace them with a local GPIO/button or documented trusted host-assisted provider.
- The dispatcher commits the sequence/nonce/request-ID replay record and accepted audit event before it calls a service handler. Failed verification, policy, or argument checks never call the handler.
- Replay state is per receiving registry. A request retry needs a new request ID, nonce and higher sequence.
- The SQLite database contains public device keys, policy, replay state and metadata-only security audit events. Protect and back it up as security-sensitive local state.
- A valid signature proves possession of a registered key; it does not by itself grant a capability. Audience, token, current registry policy and the operation's registered capability are checked independently.

The `requirements.txt` beside this file pins the package versions tested for this prototype. Review dependency versions, threat model, backup/recovery and operational permissions before deployment.

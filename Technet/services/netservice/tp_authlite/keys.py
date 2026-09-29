"""Ed25519 key helpers with a permission-locked file provider for Linux MVP."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .errors import StorageError


class FileKeyStore:
    """Store raw Ed25519 private keys in a dedicated, permission-locked directory.

    This is an MVP storage provider, not hardware-backed or encrypted key storage.
    Linux deployments should run under a dedicated service account.
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def load_or_create(self, name: str) -> Ed25519PrivateKey:
        if not name or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in name):
            raise ValueError("Key name may contain only letters, numbers, hyphen, and underscore")
        try:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            if os.name == "posix":
                if stat.S_IMODE(self.directory.stat().st_mode) & 0o077:
                    raise StorageError(f"Key directory permissions are too broad: {self.directory}")
            key_path = self.directory / f"{name}.ed25519"
            if key_path.is_symlink():
                raise StorageError(f"Private key path must not be a symbolic link: {key_path}")
            try:
                key_bytes = key_path.read_bytes()
                if os.name == "posix" and stat.S_IMODE(key_path.stat().st_mode) & 0o077:
                    raise StorageError(f"Private key permissions are too broad: {key_path}")
                if len(key_bytes) != 32:
                    raise StorageError(f"Private key file has an invalid size: {key_path}")
                return Ed25519PrivateKey.from_private_bytes(key_bytes)
            except FileNotFoundError:
                key = Ed25519PrivateKey.generate()
                raw = key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption(),
                )
                if self._write_new_key(key_path, raw):
                    return key
                stored_key = key_path.read_bytes()
                if os.name == "posix" and stat.S_IMODE(key_path.stat().st_mode) & 0o077:
                    raise StorageError(f"Private key permissions are too broad: {key_path}")
                return Ed25519PrivateKey.from_private_bytes(stored_key)
        except StorageError:
            raise
        except OSError as error:
            raise StorageError("Unable to access protected key storage") from error

    @staticmethod
    def _write_new_key(path: Path, key_bytes: bytes) -> bool:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary_path = Path(temporary_name)
        try:
            if os.name == "posix":
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as key_file:
                key_file.write(key_bytes)
                key_file.flush()
                os.fsync(key_file.fileno())
            try:
                os.link(temporary_path, path)
            except FileExistsError:
                # Another process won the create race; never overwrite its key.
                return False
            return True
        finally:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass

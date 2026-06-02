"""SSH connection manager — key-based authentication only, no password."""

from __future__ import annotations

import os
import stat
import threading
from pathlib import Path
from typing import Optional

import paramiko


class SSHConnectionError(Exception):
    """Raised when SSH connection or authentication fails."""


class SSHManager:
    """
    Thread-safe SSH connection manager.
    Supports private key file or in-memory private key string.
    Passwords are explicitly NOT supported.
    """

    _lock = threading.Lock()

    def __init__(
        self,
        host: str,
        user: str,
        port: int = 22,
        private_key_path: Optional[str] = None,
        private_key_content: Optional[str] = None,
        key_passphrase: Optional[str] = None,
        connect_timeout: int = 15,
    ):
        if not private_key_path and not private_key_content:
            raise SSHConnectionError(
                "Either --private-key-path or --private-key-content must be provided. "
                "Password authentication is not supported."
            )

        self.host = host
        self.user = user
        self.port = port
        self.connect_timeout = connect_timeout
        self._passphrase = key_passphrase
        self._client: Optional[paramiko.SSHClient] = None

        self._pkey = self._load_key(private_key_path, private_key_content)

    # ------------------------------------------------------------------
    # Key loading
    # ------------------------------------------------------------------

    def _load_key(
        self,
        path: Optional[str],
        content: Optional[str],
    ) -> paramiko.PKey:
        """Load a private key from file path or raw PEM string."""
        import io

        key_loaders = [
            paramiko.RSAKey,
            paramiko.Ed25519Key,
            paramiko.ECDSAKey,
            paramiko.DSSKey,
        ]

        if path:
            key_path = Path(path).expanduser()
            if not key_path.exists():
                raise SSHConnectionError(f"Private key file not found: {key_path}")

            # Warn if permissions are too open (Unix only)
            if os.name != "nt":
                mode = key_path.stat().st_mode
                if mode & (stat.S_IRWXG | stat.S_IRWXO):
                    raise SSHConnectionError(
                        f"Private key file {key_path} has insecure permissions "
                        f"({oct(mode)}). Run: chmod 600 {key_path}"
                    )

            source = str(key_path)
            for loader in key_loaders:
                try:
                    return loader.from_private_key_file(source, password=self._passphrase)
                except (paramiko.SSHException, ValueError):
                    continue
            raise SSHConnectionError(
                f"Cannot load private key from {path}. "
                "Supported types: RSA, Ed25519, ECDSA, DSS."
            )

        # content (PEM string)
        buf = io.StringIO(content)
        for loader in key_loaders:
            try:
                buf.seek(0)
                return loader.from_private_key(buf, password=self._passphrase)
            except (paramiko.SSHException, ValueError):
                continue
        raise SSHConnectionError(
            "Cannot load private key from provided content. "
            "Supported types: RSA, Ed25519, ECDSA, DSS."
        )

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        with self._lock:
            if self._client and self._client.get_transport() and self._client.get_transport().is_active():
                return  # already connected

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507

            try:
                client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.user,
                    pkey=self._pkey,
                    password=None,        # explicitly disable password auth
                    allow_agent=False,    # no SSH agent fallback
                    look_for_keys=False,  # no ~/.ssh/id_rsa fallback
                    timeout=self.connect_timeout,
                )
            except paramiko.AuthenticationException as exc:
                raise SSHConnectionError(
                    f"SSH key authentication failed for {self.user}@{self.host}:{self.port}. "
                    f"Details: {exc}"
                ) from exc
            except paramiko.SSHException as exc:
                raise SSHConnectionError(f"SSH error: {exc}") from exc
            except OSError as exc:
                raise SSHConnectionError(
                    f"Cannot reach {self.host}:{self.port} — {exc}"
                ) from exc

            self._client = client

    def disconnect(self) -> None:
        with self._lock:
            if self._client:
                self._client.close()
                self._client = None

    @property
    def client(self) -> paramiko.SSHClient:
        self.connect()
        return self._client  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Exec helpers
    # ------------------------------------------------------------------

    def exec(self, command: str, timeout: int = 60) -> tuple[int, str, str]:
        """
        Execute a shell command on the remote host.
        Returns (exit_code, stdout, stderr).
        """
        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return exit_code, out, err

    # ------------------------------------------------------------------
    # SFTP helpers
    # ------------------------------------------------------------------

    def _sftp(self) -> paramiko.SFTPClient:
        return self.client.open_sftp()

    def read_file(self, remote_path: str) -> bytes:
        with self._sftp() as sftp:
            with sftp.open(remote_path, "rb") as f:
                return f.read()

    def write_file(self, remote_path: str, content: bytes) -> None:
        with self._sftp() as sftp:
            # Ensure parent directory exists
            parent = str(Path(remote_path).parent)
            try:
                self.exec(f"mkdir -p {parent}")
            except Exception:
                pass
            with sftp.open(remote_path, "wb") as f:
                f.write(content)

    def delete_file(self, remote_path: str) -> None:
        with self._sftp() as sftp:
            sftp.remove(remote_path)

    def list_dir(self, remote_path: str) -> list[dict]:
        with self._sftp() as sftp:
            items = []
            for attr in sftp.listdir_attr(remote_path):
                items.append({
                    "name": attr.filename,
                    "size": attr.st_size,
                    "modified": attr.st_mtime,
                    "is_dir": stat.S_ISDIR(attr.st_mode) if attr.st_mode else False,
                    "permissions": oct(attr.st_mode)[-4:] if attr.st_mode else "????",
                })
            return items

    def stat_file(self, remote_path: str) -> dict:
        with self._sftp() as sftp:
            attr = sftp.stat(remote_path)
            return {
                "path": remote_path,
                "size": attr.st_size,
                "modified": attr.st_mtime,
                "is_dir": stat.S_ISDIR(attr.st_mode) if attr.st_mode else False,
                "permissions": oct(attr.st_mode)[-4:] if attr.st_mode else "????",
            }

    def mkdir(self, remote_path: str, parents: bool = True) -> None:
        cmd = f"mkdir -p {remote_path}" if parents else f"mkdir {remote_path}"
        code, _, err = self.exec(cmd)
        if code != 0:
            raise OSError(f"mkdir failed: {err}")

    def delete_dir(self, remote_path: str, recursive: bool = False) -> None:
        cmd = f"rm -rf {remote_path}" if recursive else f"rmdir {remote_path}"
        code, _, err = self.exec(cmd)
        if code != 0:
            raise OSError(f"delete_dir failed: {err}")

    def rename(self, old_path: str, new_path: str) -> None:
        with self._sftp() as sftp:
            sftp.rename(old_path, new_path)

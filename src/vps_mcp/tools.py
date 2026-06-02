"""MCP tool definitions for VPS remote operations."""

from __future__ import annotations

import json
import textwrap
from typing import Any

from .ssh import SSHManager, SSHConnectionError


def _ok(data: Any) -> list[dict]:
    if isinstance(data, str):
        return [{"type": "text", "text": data}]
    return [{"type": "text", "text": json.dumps(data, indent=2, default=str)}]


def _err(msg: str) -> list[dict]:
    return [{"type": "text", "text": f"ERROR: {msg}"}]


# ---------------------------------------------------------------------------
# Tool registry builder
# ---------------------------------------------------------------------------

def register_tools(mcp, ssh: SSHManager) -> None:  # noqa: C901
    """Register all VPS tools onto the MCP server instance."""

    # -----------------------------------------------------------------------
    # 1. Execute shell command
    # -----------------------------------------------------------------------
    @mcp.tool(
        name="vps_exec",
        description=textwrap.dedent("""\
            Execute a shell command on the remote VPS.
            Returns exit_code, stdout, and stderr.
            Use for: running scripts, checking status, package management, etc.
        """),
    )
    def vps_exec(command: str, timeout: int = 60) -> list[dict]:
        """
        Args:
            command: Shell command to run on VPS (e.g. "ls -la /var/log")
            timeout: Max seconds to wait for command (default 60)
        """
        try:
            code, out, err = ssh.exec(command, timeout=timeout)
            result = {
                "exit_code": code,
                "stdout": out,
                "stderr": err,
                "success": code == 0,
            }
            return _ok(result)
        except SSHConnectionError as exc:
            return _err(f"SSH connection failed: {exc}")
        except Exception as exc:
            return _err(str(exc))

    # -----------------------------------------------------------------------
    # 2. Read file
    # -----------------------------------------------------------------------
    @mcp.tool(
        name="vps_read_file",
        description="Read the contents of a file on the remote VPS.",
    )
    def vps_read_file(path: str, encoding: str = "utf-8") -> list[dict]:
        """
        Args:
            path: Absolute path to the file on VPS (e.g. "/etc/nginx/nginx.conf")
            encoding: Text encoding (default utf-8). Use 'binary' to get hex dump.
        """
        try:
            raw = ssh.read_file(path)
            if encoding == "binary":
                return _ok(f"[binary, {len(raw)} bytes]\n{raw.hex()}")
            text = raw.decode(encoding, errors="replace")
            return _ok(text)
        except FileNotFoundError:
            return _err(f"File not found: {path}")
        except SSHConnectionError as exc:
            return _err(f"SSH error: {exc}")
        except Exception as exc:
            return _err(str(exc))

    # -----------------------------------------------------------------------
    # 3. Write / create file
    # -----------------------------------------------------------------------
    @mcp.tool(
        name="vps_write_file",
        description=textwrap.dedent("""\
            Write (create or overwrite) a file on the remote VPS.
            Parent directories are created automatically.
        """),
    )
    def vps_write_file(path: str, content: str, encoding: str = "utf-8") -> list[dict]:
        """
        Args:
            path: Absolute path to the file on VPS
            content: Text content to write
            encoding: Text encoding (default utf-8)
        """
        try:
            ssh.write_file(path, content.encode(encoding))
            return _ok(f"File written successfully: {path} ({len(content)} chars)")
        except SSHConnectionError as exc:
            return _err(f"SSH error: {exc}")
        except Exception as exc:
            return _err(str(exc))

    # -----------------------------------------------------------------------
    # 4. Append to file
    # -----------------------------------------------------------------------
    @mcp.tool(
        name="vps_append_file",
        description="Append text to an existing file on the remote VPS.",
    )
    def vps_append_file(path: str, content: str) -> list[dict]:
        """
        Args:
            path: Absolute path to the file on VPS
            content: Text to append
        """
        try:
            # Read existing + append
            try:
                existing = ssh.read_file(path).decode("utf-8", errors="replace")
            except Exception:
                existing = ""
            ssh.write_file(path, (existing + content).encode("utf-8"))
            return _ok(f"Appended {len(content)} chars to {path}")
        except SSHConnectionError as exc:
            return _err(f"SSH error: {exc}")
        except Exception as exc:
            return _err(str(exc))

    # -----------------------------------------------------------------------
    # 5. Delete file
    # -----------------------------------------------------------------------
    @mcp.tool(
        name="vps_delete_file",
        description="Delete a file on the remote VPS.",
    )
    def vps_delete_file(path: str) -> list[dict]:
        """
        Args:
            path: Absolute path to the file to delete
        """
        try:
            ssh.delete_file(path)
            return _ok(f"Deleted: {path}")
        except FileNotFoundError:
            return _err(f"File not found: {path}")
        except SSHConnectionError as exc:
            return _err(f"SSH error: {exc}")
        except Exception as exc:
            return _err(str(exc))

    # -----------------------------------------------------------------------
    # 6. List directory
    # -----------------------------------------------------------------------
    @mcp.tool(
        name="vps_list_dir",
        description="List files and directories at a path on the remote VPS.",
    )
    def vps_list_dir(path: str) -> list[dict]:
        """
        Args:
            path: Absolute directory path to list (e.g. "/var/log")
        """
        try:
            items = ssh.list_dir(path)
            return _ok({"path": path, "count": len(items), "items": items})
        except FileNotFoundError:
            return _err(f"Path not found: {path}")
        except SSHConnectionError as exc:
            return _err(f"SSH error: {exc}")
        except Exception as exc:
            return _err(str(exc))

    # -----------------------------------------------------------------------
    # 7. Stat file/dir
    # -----------------------------------------------------------------------
    @mcp.tool(
        name="vps_stat",
        description="Get metadata (size, permissions, modified time) for a file or directory on the VPS.",
    )
    def vps_stat(path: str) -> list[dict]:
        """
        Args:
            path: Absolute path to check
        """
        try:
            info = ssh.stat_file(path)
            return _ok(info)
        except FileNotFoundError:
            return _err(f"Path not found: {path}")
        except SSHConnectionError as exc:
            return _err(f"SSH error: {exc}")
        except Exception as exc:
            return _err(str(exc))

    # -----------------------------------------------------------------------
    # 8. Create directory
    # -----------------------------------------------------------------------
    @mcp.tool(
        name="vps_mkdir",
        description="Create a directory (and parents) on the remote VPS.",
    )
    def vps_mkdir(path: str) -> list[dict]:
        """
        Args:
            path: Absolute directory path to create
        """
        try:
            ssh.mkdir(path, parents=True)
            return _ok(f"Directory created: {path}")
        except SSHConnectionError as exc:
            return _err(f"SSH error: {exc}")
        except Exception as exc:
            return _err(str(exc))

    # -----------------------------------------------------------------------
    # 9. Delete directory
    # -----------------------------------------------------------------------
    @mcp.tool(
        name="vps_delete_dir",
        description="Delete a directory on the remote VPS. Set recursive=true to delete non-empty directories.",
    )
    def vps_delete_dir(path: str, recursive: bool = False) -> list[dict]:
        """
        Args:
            path: Absolute directory path to delete
            recursive: If true, delete directory and all contents (rm -rf)
        """
        try:
            ssh.delete_dir(path, recursive=recursive)
            return _ok(f"Directory deleted: {path}")
        except SSHConnectionError as exc:
            return _err(f"SSH error: {exc}")
        except Exception as exc:
            return _err(str(exc))

    # -----------------------------------------------------------------------
    # 10. Rename / move
    # -----------------------------------------------------------------------
    @mcp.tool(
        name="vps_rename",
        description="Rename or move a file/directory on the remote VPS.",
    )
    def vps_rename(old_path: str, new_path: str) -> list[dict]:
        """
        Args:
            old_path: Current absolute path
            new_path: New absolute path (can be in a different directory = move)
        """
        try:
            ssh.rename(old_path, new_path)
            return _ok(f"Renamed: {old_path} → {new_path}")
        except SSHConnectionError as exc:
            return _err(f"SSH error: {exc}")
        except Exception as exc:
            return _err(str(exc))

    # -----------------------------------------------------------------------
    # 11. Check connection
    # -----------------------------------------------------------------------
    @mcp.tool(
        name="vps_ping",
        description="Test connectivity to the VPS and return basic server info.",
    )
    def vps_ping() -> list[dict]:
        try:
            code, out, err = ssh.exec("echo OK && uname -a && uptime && whoami")
            if code == 0:
                return _ok({"status": "connected", "info": out.strip()})
            return _err(f"Command failed: {err}")
        except SSHConnectionError as exc:
            return _err(f"SSH error: {exc}")
        except Exception as exc:
            return _err(str(exc))

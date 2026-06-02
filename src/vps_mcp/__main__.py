"""CLI entrypoint for vps-mcp — runs as a stdio MCP server for Claude Code."""

from __future__ import annotations

import argparse
import sys

from mcp.server import FastMCP

from .ssh import SSHManager, SSHConnectionError
from .tools import register_tools


BANNER = """
╔══════════════════════════════════════════════╗
║        SSH VPS MCP — Lema Core Tech          ║
║   Remote VPS management via SSH key auth     ║
╚══════════════════════════════════════════════╝
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ssh-vps-mcp",
        description="MCP server for remote VPS management via SSH key authentication.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using key file path
  ssh-vps-mcp --host 217.15.166.73 --user root --private-key-path ~/.ssh/id_rsa

  # Using passphrase-protected key
  ssh-vps-mcp --host 217.15.166.73 --user root \\
          --private-key-path ~/.ssh/id_rsa \\
          --key-passphrase "my passphrase"

  # Using raw key content (e.g. from env var)
  ssh-vps-mcp --host myserver.com --user deploy \\
          --private-key-content "$SSH_PRIVATE_KEY"

Claude Code usage (~/.claude.json or .claude/settings.json):
  {
    "mcpServers": {
      "vps": {
        "command": "ssh-vps-mcp",
        "args": [
          "--host", "YOUR_VPS_IP",
          "--user", "root",
          "--private-key-path", "~/.ssh/id_rsa"
        ]
      }
    }
  }
        """,
    )

    # Connection args
    conn = p.add_argument_group("SSH Connection")
    conn.add_argument("--host", required=True, help="VPS hostname or IP address")
    conn.add_argument("--user", required=True, help="SSH username (e.g. root, ubuntu, deploy)")
    conn.add_argument("--port", type=int, default=22, help="SSH port (default: 22)")

    # Auth args — one of these is required
    auth = p.add_argument_group("SSH Authentication (one required)")
    auth.add_argument(
        "--private-key-path",
        metavar="PATH",
        help="Path to SSH private key file (e.g. ~/.ssh/id_rsa). "
             "File must have 600 permissions.",
    )
    auth.add_argument(
        "--private-key-content",
        metavar="PEM",
        help="Raw PEM content of the private key (e.g. from environment variable). "
             "Useful in CI/CD or secrets managers.",
    )
    auth.add_argument(
        "--key-passphrase",
        metavar="PHRASE",
        help="Passphrase for the private key (if encrypted).",
    )

    # Transport
    p.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="SSH connection timeout in seconds (default: 15)",
    )
    p.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Validate auth — at least one key source required
    if not args.private_key_path and not args.private_key_content:
        parser.error(
            "You must provide --private-key-path or --private-key-content.\n"
            "Password authentication is not supported."
        )

    print(BANNER, file=sys.stderr)
    print(
        f"  Connecting to {args.user}@{args.host}:{args.port} ...",
        file=sys.stderr,
        flush=True,
    )

    try:
        ssh = SSHManager(
            host=args.host,
            user=args.user,
            port=args.port,
            private_key_path=args.private_key_path,
            private_key_content=args.private_key_content,
            key_passphrase=args.key_passphrase,
            connect_timeout=args.timeout,
        )
        # Eagerly verify connection on startup
        ssh.connect()
        print("  ✓ SSH key authentication successful.\n", file=sys.stderr, flush=True)

    except SSHConnectionError as exc:
        print(f"\n  ✗ Connection failed: {exc}\n", file=sys.stderr)
        sys.exit(1)

    # Build MCP server
    mcp = FastMCP(
        name="ssh-vps-mcp",
        instructions=f"Remote VPS management for {args.user}@{args.host}:{args.port}. "
                     "Use vps_ping to verify connectivity, then use file and exec tools to manage the server.",
    )

    register_tools(mcp, ssh)

    # Run stdio transport (required by Claude Code)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

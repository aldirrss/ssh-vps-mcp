# ssh-vps-mcp

**MCP server for remote VPS management via SSH key authentication — built for Claude Code.**

Manage files and run commands on your remote VPS directly from Claude Code using the Model Context Protocol (MCP). Only SSH key authentication is supported — passwords are explicitly rejected.

---

## Features

- **SSH key-only auth** — RSA, Ed25519, ECDSA, DSS. No passwords.
- **File operations** — read, write, append, delete, rename, stat
- **Directory operations** — list, create, delete (recursive)
- **Shell execution** — run any command with stdout/stderr/exit code capture
- **Connection check** — `vps_ping` tool with server info
- **Secure** — checks key file permissions (must be `600`), no SSH agent fallback, no `~/.ssh` key scanning

---

## Installation

```bash
pip install ssh-vps-mcp
```

Or install from source:

```bash
git clone https://github.com/aldirrss/ssh-vps-mcp
cd ssh-vps-mcp
pip install .
```

Verify installation:
```bash
ssh-vps-mcp --version
```

---

## Usage with Claude Code

### 1. Configure in Claude Code

Add to your Claude Code MCP config. The config file is at:
- **Global**: `~/.claude.json`
- **Project-level**: `.claude/settings.json` (in your project root)

```json
{
  "mcpServers": {
    "vps": {
      "command": "ssh-vps-mcp",
      "args": [
        "--host", "YOUR_VPS_IP_OR_HOSTNAME",
        "--user", "root",
        "--private-key-path", "~/.ssh/id_rsa"
      ]
    }
  }
}
```

### 2. Or add via Claude Code CLI

```bash
claude mcp add vps -- ssh-vps-mcp \
  --host YOUR_VPS_IP \
  --user root \
  --private-key-path ~/.ssh/id_rsa
```

### 3. Start Claude Code

```bash
claude
```

You'll see the VPS MCP connect on startup. Then ask Claude to manage your server:

```
> Can you check what's in /var/log/nginx/ on the VPS?
> Deploy this nginx config to /etc/nginx/sites-available/myapp
> Run: systemctl restart nginx
```

---

## Authentication Options

### Option A: Private key file (recommended)

```json
{
  "mcpServers": {
    "vps": {
      "command": "ssh-vps-mcp",
      "args": [
        "--host", "217.15.166.73",
        "--user", "root",
        "--private-key-path", "~/.ssh/id_rsa"
      ]
    }
  }
}
```

> Key file must have `chmod 600` permissions or the server will refuse to start.

### Option B: Passphrase-protected key

```json
{
  "args": [
    "--host", "myserver.com",
    "--user", "deploy",
    "--private-key-path", "~/.ssh/id_ed25519",
    "--key-passphrase", "your-passphrase"
  ]
}
```

### Option C: Key content from environment variable

Useful for CI/CD or when storing keys in a secrets manager:

```json
{
  "mcpServers": {
    "vps": {
      "command": "ssh-vps-mcp",
      "args": [
        "--host", "myserver.com",
        "--user", "deploy",
        "--private-key-content", "${SSH_PRIVATE_KEY}"
      ]
    }
  }
}
```

> Set `SSH_PRIVATE_KEY` environment variable to your full PEM content.

### Option D: Custom SSH port

```json
{
  "args": [
    "--host", "myserver.com",
    "--user", "root",
    "--port", "2222",
    "--private-key-path", "~/.ssh/id_rsa"
  ]
}
```

---

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `vps_ping` | Test connection, get server info (uname, uptime, whoami) |
| `vps_exec` | Run a shell command, returns exit_code + stdout + stderr |
| `vps_read_file` | Read a file's contents |
| `vps_write_file` | Write (create/overwrite) a file |
| `vps_append_file` | Append text to an existing file |
| `vps_delete_file` | Delete a file |
| `vps_list_dir` | List files in a directory |
| `vps_stat` | Get file/directory metadata |
| `vps_mkdir` | Create directory (with parents) |
| `vps_delete_dir` | Delete directory (`recursive=true` for non-empty) |
| `vps_rename` | Rename or move file/directory |

---

## Multiple VPS Servers

You can configure multiple VPS servers in one config:

```json
{
  "mcpServers": {
    "vps-production": {
      "command": "ssh-vps-mcp",
      "args": ["--host", "prod.example.com", "--user", "root", "--private-key-path", "~/.ssh/prod_rsa"]
    },
    "vps-staging": {
      "command": "ssh-vps-mcp",
      "args": ["--host", "staging.example.com", "--user", "deploy", "--private-key-path", "~/.ssh/staging_rsa"]
    }
  }
}
```

---

## CLI Reference

```
ssh-vps-mcp --help

Arguments:
  --host HOST                     VPS hostname or IP (required)
  --user USER                     SSH username (required)
  --port PORT                     SSH port (default: 22)
  --private-key-path PATH         Path to private key file (chmod 600)
  --private-key-content PEM       Raw PEM content of private key
  --key-passphrase PHRASE         Passphrase for encrypted key
  --timeout SECONDS               Connection timeout (default: 15)
  --version                       Show version
```

---

## Security Notes

- **No password auth** — the server will error if no key is provided.
- **Key file permission check** — files with group/world read permissions (`not 600`) are rejected.
- **No SSH agent** — won't silently use your `ssh-agent` keys.
- **No `~/.ssh` scanning** — only uses the key you explicitly provide.
- **AutoAddPolicy** — host keys are auto-accepted (suitable for known VPS IPs; you can restrict this for production).

---

## Requirements

- Python 3.10+
- SSH key pair with public key already added to `~/.ssh/authorized_keys` on your VPS

---

## License

MIT — Lema Core Technologies

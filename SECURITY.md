# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 4.x     | Yes                |
| < 4.0   | No                 |

## Reporting a Vulnerability

If you discover a security vulnerability in MemoryMesh, **please do not open a public issue.**

Instead, report it privately by emailing **hello@sparkvibe.io** with the subject line **[SECURITY] MemoryMesh vulnerability report**.

Please include:

- A description of the vulnerability
- Steps to reproduce (if applicable)
- The affected version(s)
- Any potential impact assessment

We will acknowledge receipt within **48 hours** and aim to provide an initial assessment within **5 business days**. Critical vulnerabilities will be prioritized for a patch release.

## Disclosure Policy

- We follow **coordinated disclosure**: we will work with you on a fix before any public announcement.
- Once a fix is released, we will credit the reporter (unless anonymity is requested).
- We will publish a security advisory via GitHub Security Advisories.

## Scope

The following are in scope:

- SQL injection or data exfiltration via the MemoryMesh API
- Unauthorized access to memory databases (project or global stores)
- Path traversal or file system access beyond intended directories
- Vulnerabilities in the MCP server (stdin/stdout JSON-RPC interface)
- Encryption weaknesses in `EncryptedMemoryStore`
- Secret leakage through logging or error messages

The following are **out of scope**:

- Denial-of-service against the local SQLite database
- Vulnerabilities in optional third-party dependencies (sentence-transformers, openai, httpx) -- report those to the respective maintainers
- Issues requiring physical access to the machine where MemoryMesh runs

## Security Best Practices

When using MemoryMesh:

- Keep your MemoryMesh installation updated to the latest version.
- Use `redact_secrets=True` when storing memories that may contain API keys or tokens.
- The `.memorymesh/` directory contains your memory database -- treat it as sensitive data.
- Do not commit `.memorymesh/` to version control (it is in `.gitignore` by default).

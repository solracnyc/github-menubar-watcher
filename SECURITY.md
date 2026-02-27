# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it through
[GitHub Security Advisories](https://github.com/solracnyc/github-menubar-watcher/security/advisories/new).

Do **not** open a public issue for security vulnerabilities.

## Scope

This project interacts with:
- The GitHub API (read-only)
- The macOS Keychain (to retrieve stored tokens)
- The local filesystem (config and state files)

## Token Handling

GitHub tokens are resolved from the macOS Keychain or environment variables. Tokens are never written to disk by this application.

# Security Policy

## Reporting a Vulnerability

Please do not open a public issue for security-sensitive reports.

Send a private report to the maintainers through the project owner channels, or
contact Memect via the official organization contact method. Include:

- affected version or commit
- reproduction steps
- impact assessment
- any relevant logs or proof of concept

We will acknowledge valid reports as soon as practical and coordinate a fix or
mitigation before public disclosure.

## Secrets

Phoenix workflows may use API keys for OpenAI-compatible model providers. Never
commit keys to the repository. Use environment variables, `xdev-config`, or your
secret manager.

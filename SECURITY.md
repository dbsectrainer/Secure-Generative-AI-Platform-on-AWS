# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| main    | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

### How to Report

1. Email the maintainers with a description of the vulnerability
2. Include steps to reproduce the issue
3. Provide any relevant logs or screenshots (redact sensitive data)

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected component(s) (e.g., RAG pipeline, IAM configuration, Lambda handler)
- Potential impact assessment
- Suggested fix (if any)

### Response Timeline

- **Acknowledgement**: Within 48 hours
- **Initial assessment**: Within 5 business days
- **Resolution target**: Within 30 days for critical issues

## Security Best Practices for Contributors

### Credentials and Secrets

- Never commit AWS access keys, secret keys, or session tokens
- Never commit `.env` files or `terraform.tfvars` with real values
- Use AWS IAM roles and instance profiles instead of long-lived credentials
- Rotate credentials regularly

### Infrastructure as Code

- All Terraform changes must be reviewed before apply
- Enable encryption at rest and in transit for all resources
- Use private VPC endpoints where available
- Follow least-privilege IAM principles

### Application Security

- Validate and sanitise all inputs, especially to LLM prompts
- Do not log sensitive data (PII, tokens, credentials)
- Use parameterised queries for any database interactions
- Keep dependencies up to date and audit regularly

## Scope

This security policy covers:

- All code in this repository
- Terraform modules and configurations
- Lambda functions and API definitions
- RAG pipeline components
- Security simulation scripts

## Acknowledgements

We appreciate responsible disclosure and will acknowledge contributors who report valid security issues (with their permission).

# Contributing

Thank you for your interest in contributing to the Secure Generative AI Platform on AWS.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a feature branch from `main`
4. Make your changes
5. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.9+
- Terraform >= 1.x
- AWS CLI configured with appropriate credentials
- Git

### Local Setup

```bash
# Clone the repository
git clone https://github.com/<your-username>/Secure-Generative-AI-Platform-on-AWS.git
cd Secure-Generative-AI-Platform-on-AWS

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Branch Naming

Use descriptive branch names with a prefix:

- `feat/` -- new features
- `fix/` -- bug fixes
- `docs/` -- documentation changes
- `refactor/` -- code refactoring
- `test/` -- adding or updating tests
- `chore/` -- maintenance tasks

Example: `feat/add-guardrails-config`

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:

```
feat(rag): add retrieval filtering for document types
fix(security): patch prompt injection bypass in input validator
docs(architecture): update network diagram with VPC endpoints
```

## Pull Request Process

1. Ensure your branch is up to date with `main`
2. Run all tests and linting before submitting
3. Fill out the pull request template completely
4. Link any related issues
5. Request review from at least one maintainer

### PR Checklist

- [ ] Code follows the project style guidelines
- [ ] Tests added/updated for new functionality
- [ ] Documentation updated if needed
- [ ] No secrets or credentials committed
- [ ] Terraform changes include `plan` output
- [ ] Security implications considered

## Code Style

- **Python**: Follow PEP 8. Use type hints where practical.
- **Terraform**: Use consistent naming (`snake_case`), add descriptions to variables and outputs.
- **General**: Prefer clarity over cleverness. Keep functions focused.

## Security

- Never commit secrets, API keys, or credentials
- Do not commit `.env` files
- Sanitise all user inputs
- Report security vulnerabilities privately (see [SECURITY.md](SECURITY.md))

## Reporting Issues

Use the GitHub issue templates for:

- **Bug reports** -- include steps to reproduce, expected vs actual behaviour
- **Feature requests** -- describe the use case and proposed solution

## Questions?

Open a [discussion](../../discussions) or reach out via issues.

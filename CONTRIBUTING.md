# Contributing to Diago

Thanks for your interest in contributing.

## Getting Started

1. Fork the repository
2. Create a feature branch
3. Install dependencies
   - Backend: `pip install -r requirements.txt`
   - Frontend: `cd frontend && npm install`
4. Run the app locally and validate your changes

## Development Workflow

- Keep PRs focused and small where possible
- Prefer clear, descriptive commit messages
- Add or update tests for behavior changes
- Update docs when functionality or setup changes

## Code Quality

Before opening a PR, run:

```bash
pytest -q
```

For frontend changes, also run:

```bash
cd frontend
npm run lint
```

## Pull Requests

A good pull request includes:

- Problem statement
- Scope of changes
- Testing evidence
- Notes on tradeoffs or follow-up work

## Reporting Issues

Please include:

- Steps to reproduce
- Expected vs actual behavior
- Relevant logs/error messages
- Environment details (OS, Python/Node versions)

## Community

By contributing, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

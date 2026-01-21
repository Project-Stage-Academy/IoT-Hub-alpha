# Contributing Guide

Thank you for contributing to this project!  
To ensure a smooth and comfortable development process for everyone, please follow the guidelines below.

## 1. Getting Started
1. Create a new branch from `main`.
2. Branch names must follow this format:  
   `task-number-short-description`

   **Examples:**
   - `task-14-repo-hygiene`

## 2. Code Standards
We use automated tools to maintain consistent code quality:

- **Black** — for automatic code formatting.
- **Flake8** — for syntax and style checks (linting).

Before committing, make sure to run:
```bash
black .
flake8 .
```

## 3. Pull Request (PR) Process

Every Pull Request must go through a Code Review before being merged.

PR checklist:
- [ ] Code is formatted using Black
- [ ] Flake8 reports no errors
- [ ] All tests pass (pytest)
- [ ] Documentation is updated (if applicable)
- [ ] PR includes a link to the related User Story or Issue

## 4. Docker Workflow

All changes must be tested inside Docker containers.

To build and start the project:

```bash
docker compose up -d --build
```

## 5. Code Review Expectations

When participating in code reviews:

* Be respectful and constructive.
* Explain the reasoning behind suggestions.
* Treat reviews as a collaborative improvement process.

When submitting a PR:
* Keep changes focused and reasonably sized.
* Avoid mixing unrelated changes in a single Pull Request.

## 6. Code Style & Clean Code

* Prefer readable and explicit code over clever solutions.
* Follow Python best practices (PEP 8).
* Remove unused code, imports, and comments.

## 7. Code of Conduct

This project follows a Code of Conduct.

By participating, you are expected to uphold this standard.

See: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

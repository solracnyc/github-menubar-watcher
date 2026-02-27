# Contributing

Thanks for your interest in contributing to GitHub Menubar Watcher!

## Dev Setup

```bash
git clone https://github.com/solracnyc/github-menubar-watcher.git
cd github-menubar-watcher
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Running Tests

```bash
.venv/bin/python -m pytest tests/ -v
```

## Making Changes

1. Fork the repo and create a feature branch
2. Make your changes
3. Run the test suite and confirm all tests pass
4. Open a pull request with a clear description

## Style

- Keep it simple — this is a small, focused tool
- Follow existing code patterns
- Add tests for new functionality

## Reporting Bugs

Open an issue using the bug report template. Include your macOS version, Python version, and steps to reproduce.

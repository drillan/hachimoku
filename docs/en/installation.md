# Installation

```{contents}
:depth: 2
:local:
```

## Requirements

- Python 3.13 or later
- Git (required for diff mode and PR mode)

## Global Installation (uv tool install)

Using `uv tool install`, you can use the `8moku` / `hachimoku` commands globally without explicitly activating a virtual environment.

### Install from Git URL

Install directly from the repository:

```bash
uv tool install git+https://github.com/drillan/hachimoku.git
```

### Install from Local Clone

Clone the repository and then install:

```bash
git clone https://github.com/drillan/hachimoku.git
cd hachimoku
uv tool install .
```

### Choosing between uv tool install and uv sync

| Method | Target | Use Case |
|--------|--------|----------|
| `uv tool install` | Users | Install commands globally for use as a review tool |
| `uv sync` | Developers | Develop, test, and debug within the project directory |

- **Users**: After installing with `uv tool install`, you can run the `8moku` command from any directory
- **Developers**: Use `uv sync` to synchronize dependencies to the project's virtual environment, and run commands via `uv run`

## Upgrading

### If installed from Git URL

```bash
uv tool install --reinstall git+https://github.com/drillan/hachimoku.git
```

### If installed from local clone

```bash
cd hachimoku
git pull
uv tool install --reinstall .
```

```{note}
`uv tool install` does nothing if the package is already installed.
The `--reinstall` flag forces reinstallation of all packages.
This flag implies `--refresh` (cache invalidation),
ensuring the latest code is fetched from the remote repository.
```

## Install from Source (for development)

Clone the repository and synchronize dependencies:

```bash
git clone https://github.com/drillan/hachimoku.git
cd hachimoku
uv sync
```

To include development tools (tests, linter, type checker):

```bash
uv sync --group dev
```

## Setup

After installation, initialize in your project directory:

```bash
cd your-project
8moku init
```

The following files are created in the `.hachimoku/` directory:

- `config.toml` - Configuration file (template with all options commented out)
- `agents/*.toml` - Copies of built-in agent definitions

See [Configuration](configuration.md) for configuration details.

## Verification

```bash
# Display help
8moku --help

# Check agent list
8moku agents
```

The `hachimoku` command provides the same functionality:

```bash
hachimoku --help
```

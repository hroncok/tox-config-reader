# tox-config-reader

A tool to read tox configuration.

## Installation

```bash
pip install tox-config-reader
```

## Usage

```python
from tox_config_reader import read_config

# Auto-discover and read configuration
config = read_config()

# Or from a specific directory
config = read_config(Path("/path/to/project"))

# Or use a specific reader directly
from tox_config_reader.raw import ToxINIConfigReader
reader = ToxINIConfigReader(Path("tox.ini"))
config = reader.read()
```

## License

MIT


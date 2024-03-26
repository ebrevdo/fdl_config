# Fiddle


Fiddle is a Python-first configuration library particularly well suited to ML
applications. Fiddle enables deep configurability of parameters in a program,
while allowing configuration to be expressed in readable and maintainable Python
code.

Additional details can be found in the [documentation].

[documentation]: https://fiddle.readthedocs.io


### Setup


Install Fiddle with pip:

```shell
pip install fiddle
```

Install Fiddle from source:

```shell
git clone https://github.com/google/fiddle
cd fiddle
python -m setup install
```

Import Fiddle:

```python
import fiddle as fdl
```

### Eugene's modifications

Build the `fdl_config` wheel:

```shell
WHEEL_PATH=$(./build_renamed.sh | tail -1)
# Install with the [flags] extension, which adds etils and absl-py.
pip install "${WHEEL_PATH}"'[flags]'
```

Import Fiddle:

```python
import fdl_config as fdl
```

Update repo from upstream:

```shell
update_from_google.sh
git push
```


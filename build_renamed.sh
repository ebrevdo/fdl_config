#!/usr/bin/env bash

# Build in a tempdir and rename `fiddle` to `fdl_config` everywhere.
# Final output line is the path to the wheel file.

set -e

# On MacOS, first make sure gsed is avaialble; and if so, use that.
if [[ $(uname) == "Darwin" ]]; then
    if ! command -v gsed &> /dev/null; then
        echo "gsed not found; please install with 'brew install gnu-sed'"
        exit 1
    fi
    _SED=gsed
else
    _SED=sed
fi

BUILD_DIR=$(mktemp -d)
# Copy over everything except for hidden files
rsync -a --exclude=".*" . "${BUILD_DIR}"
pushd "${BUILD_DIR}"
mv fiddle fdl_config
find . -type f -print0 | xargs -0 -L1 "${_SED}" -i -e 's/fiddle/fdl_config/g'
python -m build --wheel . >/dev/null
ls "${BUILD_DIR}"/dist/*.whl | sort -r | head -n 1


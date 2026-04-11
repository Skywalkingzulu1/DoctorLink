"""
A minimal stub for the ``pytest_xprocess`` package.

The original test suite expects ``pytest_xprocess.getrootdir`` to be
importable. In environments where the real package is not installed we
provide a lightweight fallback that returns the current working directory.
"""

import os
from pathlib import Path
from typing import Union


def getrootdir() -> Union[str, Path]:
    """
    Return the root directory for pytest execution.

    This stub simply returns the current working directory, which is
    sufficient for the test plugin that only needs a path object.
    """
    return Path(os.getcwd())
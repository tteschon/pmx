"""pmx -- process discovery from event logs, built on pm4py.

Copyright (C) 2026 tteschon

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version. See the LICENSE file at the root of this repository, or
<https://www.gnu.org/licenses/>.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    # The *distribution* is `pmx-cli`, not `pmx` -- that name belongs to an
    # unrelated project on PyPI. Asking for "pmx" here would report 0.0.0.dev0
    # on a normal install, or that other project's version on a machine which
    # happens to have it.
    __version__ = version("pmx-cli")
except PackageNotFoundError:  # a source tree that was never installed
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]

# Copyright (c) 2021-2025, Thomas Aglassinger
# All rights reserved. Distributed under the BSD 3-Clause License.
import logging
from importlib.metadata import version

__version__ = version(__name__)

log = logging.getLogger("nubops")

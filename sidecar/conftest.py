"""Configure sys.path so sidecar modules resolve as top-level imports."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

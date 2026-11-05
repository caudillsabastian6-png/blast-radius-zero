#!/usr/bin/env python3
"""Run the Blast Radius Zero test suite (stdlib unittest, offline).

    python3 tests/run_tests.py

No network, no API key, no Docker required. Docker-specific containment
assertions run only when a Docker daemon and the worker image are present,
and skip otherwise.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "agent"))
sys.path.insert(0, HERE)


def main() -> int:
    suite = unittest.TestLoader().discover(start_dir=HERE, pattern="test_*.py",
                                           top_level_dir=HERE)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

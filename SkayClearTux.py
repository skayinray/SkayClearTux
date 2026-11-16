#!/usr/bin/env python3
"""Запуск SkayClearTux (используется и для сборки)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skaycleartux.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

# SPDX-License-Identifier: Apache-2.0
"""Webots entry point; no pip installation is required to open the world."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from home_bot.simulation import run

if __name__ == "__main__":
    run(ROOT, smoke="--smoke" in sys.argv)

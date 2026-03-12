#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    print(
        "[WARN] Deprecated: scripts/harvest_knowledge_base.py -> scripts/ops.sh harvest-knowledge",
        file=sys.stderr,
    )
    return subprocess.call(["bash", str(script_dir / "ops.sh"), "harvest-knowledge", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())

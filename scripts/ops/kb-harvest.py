#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.services.knowledge_harvester import KnowledgeHarvester  # noqa: E402


def main() -> int:
    harvester = KnowledgeHarvester(settings=settings)
    result = harvester.harvest()
    print(
        "[PASS] knowledge base refreshed: "
        f"{result['succeeded']}/{result['attempted']} succeeded "
        f"(failed={result['failed']}, success_rate={result['success_rate']}%)"
    )
    print(f"[INFO] generated_at: {result['generated_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

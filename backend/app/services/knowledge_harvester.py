from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx

from app.core.config import REPO_ROOT, Settings


@dataclass
class HarvestResult:
    attempted: int
    succeeded: int
    failed: int
    success_rate: float
    generated_at: str

    def as_dict(self) -> dict:
        return {
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "success_rate": self.success_rate,
            "generated_at": self.generated_at,
        }


class KnowledgeHarvester:
    def __init__(self, *, settings: Settings, knowledge_file: Path | None = None):
        self._settings = settings
        self._knowledge_file = knowledge_file or (REPO_ROOT / "backend" / "data" / "knowledge_base.json")

    def harvest(self) -> dict:
        if not self._settings.kb_harvest_enabled:
            now_iso = self._iso_now()
            return HarvestResult(0, 0, 0, 0.0, now_iso).as_dict()

        if not self._knowledge_file.exists():
            raise FileNotFoundError(f"Knowledge base file not found: {self._knowledge_file}")

        document = json.loads(self._knowledge_file.read_text(encoding="utf-8"))
        seed_keywords = [str(keyword).strip() for keyword in document.get("seedKeywords", []) if str(keyword).strip()]
        items = list(document.get("items", []))

        attempted = 0
        succeeded = 0
        failed = 0
        now_iso = self._iso_now()

        with httpx.Client(
            timeout=self._settings.kb_harvest_timeout_seconds,
            follow_redirects=True,
            trust_env=False,
            headers={"User-Agent": "IntelliFarmKnowledgeHarvester/1.0"},
        ) as client:
            for item in items:
                source = dict(item.get("source", {}))
                attempted += 1
                source.setdefault("type", "public_html")
                item["lastAttemptAt"] = now_iso

                try:
                    fetched_title, fetched_summary = self._fetch_source(
                        client=client,
                        source=source,
                        fallback_summary=str(item.get("summary", "")),
                    )

                    if fetched_title and len(str(source.get("title", "")).strip()) < 3:
                        source["title"] = fetched_title
                    if fetched_summary and not str(item.get("summary", "")).strip():
                        item["summary"] = fetched_summary

                    source_text = self._normalize_text(" ".join([fetched_title or "", fetched_summary or "", str(item.get("summary", ""))]))
                    existing_keywords = {str(keyword).strip() for keyword in item.get("keywords", []) if str(keyword).strip()}
                    for keyword in seed_keywords:
                        if self._normalize_text(keyword) in source_text:
                            existing_keywords.add(keyword)

                    item["keywords"] = sorted(existing_keywords, key=lambda keyword: (len(keyword), keyword))
                    source["fetchedAt"] = now_iso
                    item["updatedAt"] = now_iso
                    item["fetchStatus"] = "success"
                    item["lastError"] = None
                    succeeded += 1
                except Exception as exc:  # noqa: BLE001
                    item["fetchStatus"] = "failed"
                    item["lastError"] = str(exc)
                    failed += 1

                item["source"] = source

        success_rate = round((succeeded / attempted) * 100, 2) if attempted else 0.0
        document["items"] = items
        document["generatedAt"] = now_iso
        document["version"] = f"{datetime.now(UTC).strftime('%Y.%m.%d')}-kb-auto"
        document["harvest"] = {
            "lastRunAt": now_iso,
            "attempted": attempted,
            "succeeded": succeeded,
            "failed": failed,
            "successRate": success_rate,
        }

        self._knowledge_file.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

        return HarvestResult(
            attempted=attempted,
            succeeded=succeeded,
            failed=failed,
            success_rate=success_rate,
            generated_at=now_iso,
        ).as_dict()

    def _fetch_source(self, *, client: httpx.Client, source: dict, fallback_summary: str) -> tuple[str | None, str | None]:
        source_type = str(source.get("type", "public_html")).strip().lower()
        if source_type == "rss":
            return self._fetch_rss(client=client, source=source)
        if source_type == "api_key_source":
            return self._fetch_api_key_source(client=client, source=source)
        return self._fetch_public_html(client=client, source=source, fallback_summary=fallback_summary)

    def _fetch_public_html(self, *, client: httpx.Client, source: dict, fallback_summary: str) -> tuple[str | None, str | None]:
        url = str(source.get("url", "")).strip()
        if not url:
            raise ValueError("Missing source.url")

        response = client.get(url)
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} from {url}")

        html = response.text
        title = self._extract_html_title(html)
        summary = self._extract_meta_description(html) or (fallback_summary if fallback_summary.strip() else None)
        return title, summary

    def _fetch_rss(self, *, client: httpx.Client, source: dict) -> tuple[str | None, str | None]:
        url = str(source.get("url", "")).strip()
        if not url:
            raise ValueError("Missing RSS source.url")

        response = client.get(url)
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} from {url}")

        root = ET.fromstring(response.text)
        first_item = root.find("./channel/item") or root.find("./entry")
        if first_item is None:
            return source.get("title"), None

        title_node = first_item.find("title")
        summary_node = first_item.find("description") or first_item.find("summary")
        title = title_node.text.strip() if title_node is not None and title_node.text else source.get("title")
        summary = summary_node.text.strip() if summary_node is not None and summary_node.text else None
        return title, summary

    def _fetch_api_key_source(self, *, client: httpx.Client, source: dict) -> tuple[str | None, str | None]:
        source_id = str(source.get("sourceId", "")).strip().upper().replace("-", "_")
        api_key_env = str(source.get("apiKeyEnv", "")).strip() or (f"KB_SOURCE_{source_id}_API_KEY" if source_id else "")
        base_url_env = str(source.get("baseUrlEnv", "")).strip() or (f"KB_SOURCE_{source_id}_BASE_URL" if source_id else "")
        api_key = os.getenv(api_key_env) if api_key_env else None
        base_url = os.getenv(base_url_env) if base_url_env else None

        if not api_key:
            raise RuntimeError(f"Missing API key env: {api_key_env or 'KB_SOURCE_*_API_KEY'}")

        raw_url = str(source.get("url", "")).strip()
        if not raw_url:
            raise ValueError("Missing API source.url")
        final_url = raw_url
        if base_url and not raw_url.startswith("http://") and not raw_url.startswith("https://"):
            final_url = urljoin(base_url.rstrip("/") + "/", raw_url.lstrip("/"))

        header_name = str(source.get("apiKeyHeader", "Authorization")).strip() or "Authorization"
        auth_scheme = str(source.get("apiKeyScheme", "Bearer")).strip()
        header_value = f"{auth_scheme} {api_key}".strip() if auth_scheme else api_key

        response = client.get(final_url, headers={header_name: header_value, "Accept": "application/json"})
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} from {final_url}")

        payload = response.json()
        title = None
        summary = None
        if isinstance(payload, dict):
            title = str(payload.get("title") or payload.get("name") or source.get("title") or "").strip() or None
            summary = str(payload.get("summary") or payload.get("description") or payload.get("abstract") or "").strip() or None
        return title, summary

    def _extract_html_title(self, html: str) -> str | None:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        return title or None

    def _extract_meta_description(self, html: str) -> str | None:
        patterns = [
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
            if match:
                value = re.sub(r"\s+", " ", match.group(1)).strip()
                if value:
                    return value
        return None

    def _normalize_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().lower()

    def _iso_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

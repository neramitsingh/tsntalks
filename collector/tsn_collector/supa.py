from __future__ import annotations

import json
from typing import Any

import requests


class Supa:
    """Thin PostgREST + Storage client using the service-role key."""

    def __init__(self, url: str, service_key: str, chunk: int = 500, timeout: int = 60):
        self.url = url.rstrip("/")
        self.key = service_key
        self.chunk = chunk
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({"apikey": service_key, "Authorization": f"Bearer {service_key}"})

    def upsert(self, table: str, rows: list[dict[str, Any]], on_conflict: str) -> int:
        if not rows:
            return 0
        n = 0
        for i in range(0, len(rows), self.chunk):
            batch = rows[i:i + self.chunk]
            r = self.s.post(
                f"{self.url}/rest/v1/{table}", params={"on_conflict": on_conflict},
                headers={"Prefer": "resolution=merge-duplicates,return=minimal", "Content-Type": "application/json"},
                data=json.dumps(batch, default=str), timeout=self.timeout,
            )
            if r.status_code >= 300:
                raise RuntimeError(f"upsert {table} failed {r.status_code}: {r.text[:300]}")
            n += len(batch)
        return n

    def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        r = self.s.post(f"{self.url}/rest/v1/{table}", headers={"Prefer": "return=representation",
                        "Content-Type": "application/json"}, data=json.dumps(row, default=str), timeout=self.timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"insert {table} failed {r.status_code}: {r.text[:300]}")
        return r.json()[0]

    def update(self, table: str, match: dict[str, Any], values: dict[str, Any]) -> None:
        params = {k: f"eq.{v}" for k, v in match.items()}
        r = self.s.patch(f"{self.url}/rest/v1/{table}", params=params, headers={"Prefer": "return=minimal",
                         "Content-Type": "application/json"}, data=json.dumps(values, default=str), timeout=self.timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"update {table} failed {r.status_code}: {r.text[:300]}")

    def select(self, table: str, **params: Any) -> list[dict[str, Any]]:
        r = self.s.get(f"{self.url}/rest/v1/{table}", params=params, timeout=self.timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"select {table} failed {r.status_code}: {r.text[:300]}")
        return r.json()

    def rpc(self, fn: str, args: dict[str, Any]) -> Any:
        r = self.s.post(f"{self.url}/rest/v1/rpc/{fn}", json=args, timeout=self.timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"rpc {fn} failed {r.status_code}: {r.text[:300]}")
        return r.json()

    def upload_public(self, bucket: str, path: str, data: bytes, content_type: str, max_age: int = 300) -> None:
        """Note (2026-09-15): this project's Storage serves `Cache-Control: no-cache` whatever we send —
        tried as a raw header and as a `cacheControl` multipart field, on an existing path and a fresh one.
        Left as the header form because it is simpler and the pages fetch with `cache: no-store` anyway."""
        r = self.s.post(f"{self.url}/storage/v1/object/{bucket}/{path}", data=data, timeout=self.timeout,
                        headers={"Content-Type": content_type, "x-upsert": "true", "cache-control": f"max-age={max_age}"})
        if r.status_code >= 300:
            raise RuntimeError(f"upload {bucket}/{path} failed {r.status_code}: {r.text[:300]}")
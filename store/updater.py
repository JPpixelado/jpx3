"""Sistema de atualização automática do XMB-PY.

Fontes:
  - store  → GET {base}/api/updates
  - github → GitHub Releases (tag + asset .zip)
  - auto   → tenta GitHub e depois a loja

Config (config.json):
  "update_source": "github",
  "github_repo": "usuario/repo",
  "github_token": "",
  "store_server_url": "https://..."
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
UPDATES_DIR = ROOT / "data" / "updates"


def parse_version(text: str) -> tuple:
    """Extrai tupla de versão de '4.0', '3.1.0.zip', 'v2.0'."""
    if not text:
        return (0,)
    name = Path(str(text)).stem
    name = re.sub(r"^[vV]", "", name)
    nums = re.findall(r"\d+", name)
    if not nums:
        return (0,)
    return tuple(int(n) for n in nums)


def version_to_str(v: tuple) -> str:
    return ".".join(str(x) for x in v)


def get_local_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "0.0.0"
    return "0.0.0"


def set_local_version(version: str):
    VERSION_FILE.write_text(version.strip() + "\n", encoding="utf-8")


class UpdateInfo:
    def __init__(self, version: str, filename: str, url: str, size: int = 0, source: str = ""):
        self.version = version
        self.filename = filename
        self.url = url
        self.size = size
        self.source = source
        self.parsed = parse_version(version)


class Updater:
    def __init__(
        self,
        base_url: str = "",
        timeout: int = 12,
        *,
        source: str = "auto",
        github_repo: str = "",
        github_token: str = "",
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self.source = (source or "auto").lower()
        self.github_repo = (github_repo or "").strip().strip("/")
        self.github_token = (github_token or "").strip()

    def _headers_github(self) -> dict:
        h = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "XMB-PY-Updater",
        }
        if self.github_token:
            h["Authorization"] = f"Bearer {self.github_token}"
        return h

    def fetch_from_store(self) -> list:
        if not self.base_url:
            return []
        try:
            r = requests.get(f"{self.base_url}/api/updates", timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError):
            return []

        updates = []
        for item in data.get("updates") or []:
            ver = item.get("version") or item.get("filename") or ""
            filename = item.get("filename") or f"{ver}.zip"
            url = item.get("url") or f"/api/updates/{filename}"
            if url.startswith("/"):
                url = self.base_url + url
            updates.append(
                UpdateInfo(ver, filename, url, int(item.get("size") or 0), source="store")
            )
        updates.sort(key=lambda u: u.parsed, reverse=True)
        return updates

    def fetch_from_github(self) -> list:
        if not self.github_repo:
            return []

        url = f"https://api.github.com/repos/{self.github_repo}/releases"
        try:
            r = requests.get(url, timeout=self.timeout, headers=self._headers_github())
            r.raise_for_status()
            releases = r.json()
        except (requests.RequestException, ValueError):
            return []

        if not isinstance(releases, list):
            return []

        updates = []
        for rel in releases:
            if rel.get("draft"):
                continue
            tag = rel.get("tag_name") or rel.get("name") or ""
            ver = re.sub(r"^[vV]", "", tag.strip())
            assets = rel.get("assets") or []
            zip_assets = [
                a for a in assets
                if str(a.get("name", "")).lower().endswith(".zip")
            ]
            if not zip_assets:
                zipball = rel.get("zipball_url")
                if zipball:
                    updates.append(
                        UpdateInfo(
                            ver or tag,
                            f"{ver or 'release'}.zip",
                            zipball,
                            0,
                            source="github",
                        )
                    )
                continue

            chosen = None
            for a in zip_assets:
                if ver and ver in a.get("name", ""):
                    chosen = a
                    break
            if chosen is None:
                chosen = zip_assets[0]

            updates.append(
                UpdateInfo(
                    ver or Path(chosen["name"]).stem,
                    chosen["name"],
                    chosen["browser_download_url"],
                    int(chosen.get("size") or 0),
                    source="github",
                )
            )

        updates.sort(key=lambda u: u.parsed, reverse=True)
        return updates

    def fetch_available(self) -> list:
        buckets = []
        if self.source in ("github", "auto") and self.github_repo:
            buckets.extend(self.fetch_from_github())
        if self.source in ("store", "auto"):
            buckets.extend(self.fetch_from_store())

        seen = set()
        unique = []
        for u in sorted(buckets, key=lambda x: x.parsed, reverse=True):
            if u.parsed in seen:
                continue
            seen.add(u.parsed)
            unique.append(u)
        return unique

    def latest_newer_than_local(self) -> Optional[UpdateInfo]:
        local = parse_version(get_local_version())
        for u in self.fetch_available():
            if u.parsed > local:
                return u
        return None

    def download(self, info: UpdateInfo) -> Path:
        UPDATES_DIR.mkdir(parents=True, exist_ok=True)
        dest = UPDATES_DIR / info.filename
        headers = {}
        if info.source == "github":
            headers = self._headers_github()
            headers["Accept"] = "application/octet-stream"

        r = requests.get(
            info.url,
            timeout=max(self.timeout, 120),
            stream=True,
            headers=headers,
        )
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(65536):
                if chunk:
                    f.write(chunk)
        return dest

    def apply(self, zip_path: Path, version: str) -> list:
        written = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = [m for m in zf.namelist() if m and not m.endswith("/")]
            tops = {m.split("/")[0] for m in members if "/" in m}
            strip = None
            if len(tops) == 1:
                only = next(iter(tops))
                if all(
                    m.startswith(only + "/") or m.rstrip("/") == only
                    for m in zf.namelist()
                ):
                    strip = only + "/"

            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/")
                if strip and name.startswith(strip):
                    name = name[len(strip):]
                if not name or ".." in name.split("/"):
                    continue
                if name.startswith("wallpapers/") or "session" in name:
                    continue
                target = ROOT / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as out:
                    out.write(src.read())
                written.append(name)

        set_local_version(version)
        return written
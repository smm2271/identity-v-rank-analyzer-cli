from typing import Dict, Any
from urllib.parse import urlparse, urlunparse

import aiohttp
from config import ConfigManager

class AbstractUploader:
    async def upload(self, data: Dict[str, Any]) -> None:
        raise NotImplementedError

class BackendUploader(AbstractUploader):
    def __init__(self, config: ConfigManager):
        self.config = config

    @staticmethod
    def _normalize_backend_url(raw_url: str) -> str:
        url = raw_url.strip()
        if not url:
            return url

        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"

        parsed = urlparse(url)
        path = parsed.path.rstrip("/")

        if path.endswith("/api/v1/matches"):
            final_path = path
        elif path.endswith("/api/v1"):
            final_path = f"{path}/matches"
        elif path.endswith("/api"):
            final_path = f"{path}/v1/matches"
        elif not path:
            final_path = "/api/v1/matches"
        else:
            final_path = f"{path}/api/v1/matches"

        return urlunparse((parsed.scheme, parsed.netloc, final_path, "", parsed.query, parsed.fragment))

    async def upload(self, data: Dict[str, Any]) -> None:
        raw_url = self.config.get("backend_url")
        key = self.config.get("backend_key")
        if not raw_url or not key:
            # 設定未完備則不上傳
            return

        url = self._normalize_backend_url(str(raw_url))

        headers = {"X-API-Key": key, "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as resp:
                if resp.status < 200 or resp.status >= 300:
                    raise Exception(f"後端伺服器回應錯誤: {resp.status}")
                print(f"📤 資料已傳送到後端伺服器: {url}")

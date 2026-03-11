from typing import Dict, Any
import aiohttp
from config import ConfigManager

class AbstractUploader:
    async def upload(self, data: Dict[str, Any]) -> None:
        raise NotImplementedError

class BackendUploader(AbstractUploader):
    def __init__(self, config: ConfigManager):
        self.config = config

    async def upload(self, data: Dict[str, Any]) -> None:
        url = self.config.get("backend_url")
        key = self.config.get("backend_key")
        if not url or not key:
            # 設定未完備則不上傳
            return

        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as resp:
                if resp.status != 200:
                    raise Exception(f"後端伺服器回應錯誤: {resp.status}")
                print(f"📤 資料已傳送到後端伺服器: {url}")

import os
import json
from typing import Dict, Any

class ConfigManager:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config_data = self.load()

    def load(self) -> Dict[str, Any]:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"replay_path": "", "last_user": "", "backend_url": "", "backend_key": ""}

    def save(self, **kwargs):
        self.config_data.update(kwargs)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config_data, f, indent=4)

    def get(self, key: str, default: Any = "") -> Any:
        return self.config_data.get(key, default)

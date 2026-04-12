import asyncio
import json
import os
import pickle
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import ConfigManager
from parsers import AbstractReplayParser
from uploaders import AbstractUploader


class SyncManager:
    def __init__(self, config: ConfigManager, parser: AbstractReplayParser, uploader: AbstractUploader):
        self.config = config
        self.parser = parser
        self.uploader = uploader
        self._lock = threading.Lock()
        base_dir = os.path.dirname(os.path.abspath(self.config.config_file))
        self.storage_dir = os.path.join(base_dir, "sync_records")
        os.makedirs(self.storage_dir, exist_ok=True)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _safe_basename(path: str) -> str:
        return os.path.basename(path.rstrip("/\\")) or path

    def _record_path(self, record_id: str) -> str:
        return os.path.join(self.storage_dir, f"{record_id}.json")

    def _load_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        path = self._record_path(record_id)
        if not os.path.exists(path):
            return None

        with self._lock:
            with open(path, "r", encoding="utf-8") as file:
                return json.load(file)

    def _write_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        record_id = record["id"]
        path = self._record_path(record_id)

        with self._lock:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(record, file, ensure_ascii=False, indent=2)

        return record

    def _update_record(self, record_id: str, **updates: Any) -> Optional[Dict[str, Any]]:
        record = self._load_record(record_id)
        if record is None:
            return None

        record.update(updates)
        record["updated_at"] = self._now_iso()
        return self._write_record(record)

    def _list_all_records(self) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        if not os.path.exists(self.storage_dir):
            return records

        for name in os.listdir(self.storage_dir):
            if not name.endswith(".json"):
                continue

            path = os.path.join(self.storage_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as file:
                    records.append(json.load(file))
            except Exception:
                continue

        records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return records

    @staticmethod
    def _build_summary(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        players = parsed_data.get("players") or []
        return {
            "room_guuid": parsed_data.get("room_guuid"),
            "game_save_time": parsed_data.get("game_save_time"),
            "match_type": parsed_data.get("match_type"),
            "rank_level": parsed_data.get("rank_level"),
            "player_count": len(players),
            "scene_id": parsed_data.get("scene_id"),
            "pid": parsed_data.get("pid"),
        }

    def _build_record(
        self,
        source_path: str,
        parsed_data: Optional[Dict[str, Any]],
        status: str,
        last_error: str = "",
    ) -> Dict[str, Any]:
        record_id = uuid.uuid4().hex
        record: Dict[str, Any] = {
            "id": record_id,
            "source_path": source_path,
            "source_name": self._safe_basename(source_path),
            "status": status,
            "created_at": self._now_iso(),
            "updated_at": self._now_iso(),
            "uploaded_at": None,
            "attempts": 0,
            "last_error": last_error,
            "parsed_data": parsed_data,
            "room_guuid": None,
            "game_save_time": None,
            "match_type": None,
            "rank_level": None,
            "player_count": 0,
            "scene_id": None,
            "pid": None,
        }

        if parsed_data:
            record.update(self._build_summary(parsed_data))

        return self._write_record(record)

    def queue_replay(self, source_path: str) -> None:
        threading.Thread(target=self.process_replay_file, args=(source_path,), daemon=True).start()

    def process_replay_file(self, source_path: str) -> Optional[Dict[str, Any]]:
        source_path = os.path.abspath(source_path)

        try:
            with open(source_path, "rb") as file:
                raw_data = pickle.load(file)
            parsed_data = self.parser.parse(raw_data)
        except Exception as exc:
            record = self._build_record(source_path, None, "parse_failed", str(exc))
            print(f"❌ 解析失敗並已本地保存: {source_path} / {exc}")
            return record

        record = self._build_record(source_path, parsed_data, "pending")
        self._upload_record(record["id"])
        return record

    def _upload_record(self, record_id: str) -> None:
        record = self._load_record(record_id)
        if record is None:
            return

        parsed_data = record.get("parsed_data")
        if not parsed_data:
            source_path = record.get("source_path")
            if not source_path or not os.path.exists(source_path):
                self._update_record(record_id, status="parse_failed", last_error="原始錄影檔案不存在，無法重試")
                return

            try:
                with open(source_path, "rb") as file:
                    raw_data = pickle.load(file)
                parsed_data = self.parser.parse(raw_data)
                self._update_record(record_id, **self._build_summary(parsed_data), parsed_data=parsed_data)
            except Exception as exc:
                self._update_record(record_id, status="parse_failed", last_error=str(exc))
                return

        raw_url = self.config.get("backend_url")
        backend_key = self.config.get("backend_key")
        if not raw_url or not backend_key:
            self._update_record(record_id, status="waiting_for_config", last_error="尚未設定後端網址或 API Key")
            return

        self._update_record(record_id, status="uploading", attempts=int(record.get("attempts", 0)) + 1, last_error="")

        try:
            asyncio.run(self.uploader.upload(parsed_data))
            self._update_record(record_id, status="uploaded", uploaded_at=self._now_iso(), last_error="")
            print(f"✅ 已同步對局: {record.get('source_name')}")
        except Exception as exc:
            self._update_record(record_id, status="failed", last_error=str(exc))
            print(f"❌ 同步失敗: {record.get('source_name')} / {exc}")

    def retry_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        record = self._load_record(record_id)
        if record is None:
            return None

        threading.Thread(target=self._upload_record, args=(record_id,), daemon=True).start()
        return record

    def retry_failed_records(self) -> int:
        retried = 0
        for record in self._list_all_records():
            if record.get("status") in {"failed", "parse_failed", "waiting_for_config"}:
                retried += 1
                threading.Thread(target=self._upload_record, args=(record["id"],), daemon=True).start()
        return retried

    def list_records(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        records = self._list_all_records()
        if status:
            records = [record for record in records if record.get("status") == status]

        return [self._sanitize_record(record) for record in records]

    def summary(self) -> Dict[str, int]:
        counts = {
            "total": 0,
            "pending": 0,
            "uploading": 0,
            "uploaded": 0,
            "failed": 0,
            "parse_failed": 0,
            "waiting_for_config": 0,
        }

        for record in self._list_all_records():
            counts["total"] += 1
            status = record.get("status", "")
            if status in counts:
                counts[status] += 1

        return counts

    @staticmethod
    def _sanitize_record(record: Dict[str, Any]) -> Dict[str, Any]:
        status = record.get("status", "pending")
        return {
            "id": record.get("id"),
            "source_path": record.get("source_path"),
            "source_name": record.get("source_name"),
            "status": status,
            "retryable": status in {"failed", "parse_failed", "waiting_for_config"},
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
            "uploaded_at": record.get("uploaded_at"),
            "attempts": record.get("attempts", 0),
            "last_error": record.get("last_error", ""),
            "room_guuid": record.get("room_guuid"),
            "game_save_time": record.get("game_save_time"),
            "match_type": record.get("match_type"),
            "rank_level": record.get("rank_level"),
            "player_count": record.get("player_count", 0),
            "scene_id": record.get("scene_id"),
            "pid": record.get("pid"),
        }
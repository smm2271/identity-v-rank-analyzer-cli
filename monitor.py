import os
import time
import pickle
import threading
from datetime import datetime
from typing import Optional, List

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from sync_manager import SyncManager

class ReplayEventHandler(FileSystemEventHandler):
    def __init__(self, sync_manager: SyncManager, record_games: list):
        super().__init__()
        self.sync_manager = sync_manager
        self.record_games = record_games

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith("game_info.txt"):
            print(f"[{datetime.now()}] 偵測到新錄影: {event.src_path}")
            time.sleep(2)  # 等待檔案寫入完成
            try:
                self.sync_manager.queue_replay(event.src_path)
                print(f"✅ 解析完成: {event.src_path}")
                self.record_games.append(time.time())
            except Exception as e:
                print(f"❌ 解析失敗: {e}")

class ReplayMonitorManager:
    """SRP: 專責管理 Observer 的啟動與關閉"""
    def __init__(self, sync_manager: SyncManager):
        self.observer: Optional[Observer] = None
        self.sync_manager = sync_manager
        self.record_games: List[float] = []
        self.current_user = ""

    def start(self, user_dir: str, user_id: str) -> bool:
        if not os.path.exists(user_dir):
            return False
            
        self.stop()

        self.observer = Observer()
        handler = ReplayEventHandler(self.sync_manager, self.record_games)
        self.observer.schedule(handler, path=user_dir, recursive=True)
        self.observer.start()
        self.current_user = user_id
        return True

    def stop(self) -> None:
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

    def is_alive(self) -> bool:
        return self.observer.is_alive() if self.observer else False

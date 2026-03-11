import os
import time
import pickle
import threading
import asyncio
from datetime import datetime
from typing import Optional, List

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from parsers import AbstractReplayParser
from uploaders import AbstractUploader

class ReplayEventHandler(FileSystemEventHandler):
    def __init__(self, parser: AbstractReplayParser, uploader: AbstractUploader, record_games: list):
        super().__init__()
        self.parser = parser
        self.uploader = uploader
        self.record_games = record_games

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith("game_info.txt"):
            print(f"[{datetime.now()}] 偵測到新錄影: {event.src_path}")
            time.sleep(2)  # 等待檔案寫入完成
            try:
                with open(event.src_path, "rb") as f:
                    raw_data = pickle.load(f)
                
                # 依賴反轉，調用抽象方法
                parsed_data = self.parser.parse(raw_data)
                
                # 在執行緒中發送請求，避免阻塞 Watchdog Observer
                def run_upload():
                    try:
                        asyncio.run(self.uploader.upload(parsed_data))
                    except Exception as e:
                        print(f"❌ 上傳失敗: {e}")

                threading.Thread(target=run_upload, daemon=True).start()
                
                print(f"✅ 解析完成: {event.src_path}")
                self.record_games.append(time.time())
            except Exception as e:
                print(f"❌ 解析失敗: {e}")

class ReplayMonitorManager:
    """SRP: 專責管理 Observer 的啟動與關閉"""
    def __init__(self, parser: AbstractReplayParser, uploader: AbstractUploader):
        self.observer: Optional[Observer] = None
        self.parser = parser
        self.uploader = uploader
        self.record_games: List[float] = []
        self.current_user = ""

    def start(self, user_dir: str, user_id: str) -> bool:
        if not os.path.exists(user_dir):
            return False
            
        self.stop()

        self.observer = Observer()
        handler = ReplayEventHandler(self.parser, self.uploader, self.record_games)
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

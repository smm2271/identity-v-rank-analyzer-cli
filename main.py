import os
import time
import socket
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog
import uvicorn

from config import ConfigManager
from parsers import IdentityVReplayParser
from uploaders import BackendUploader
from monitor import ReplayMonitorManager
from api import create_app

def find_free_port(start_port: int = 8000, max_tries: int = 100) -> int:
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except socket.error:
                continue
    raise IOError("無法找到可用的網路端口")

def prompt_for_replay_path() -> str:
    root = tk.Tk()
    root.withdraw()
    selected = filedialog.askdirectory(title="選擇第五人格安裝資料夾")
    if selected:
        return os.path.join(selected, "Documents", "video").replace("\\", "/")
    return ""

def main():
    # DIP 依賴反轉：在這裡「組合」所有的實例並注入，避免模組間的強耦合
    config = ConfigManager()
    parser = IdentityVReplayParser()
    uploader = BackendUploader(config)
    monitor = ReplayMonitorManager(parser, uploader)
    
    # 處理初次設定路徑
    replay_path = config.get("replay_path")
    if not replay_path or not os.path.exists(replay_path):
        replay_path = prompt_for_replay_path()
        if not replay_path:
            print("未選擇路徑，程式結束。")
            exit(0)
        config.save(replay_path=replay_path)

    # 啟動自動監控
    last_user = config.get("last_user")
    if last_user and os.path.exists(os.path.join(replay_path, last_user)):
        print(f"自動啟動監控玩家: {last_user}")
        monitor.start(os.path.join(replay_path, last_user), last_user)

    # 創造 FastAPI 實例並啟動 Web 伺服器
    app = create_app(config, monitor)
    running_port = find_free_port(8050)
    api_url = f"http://127.0.0.1:{running_port}"

    api_thread = threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=running_port, log_level="warning"),
        daemon=True
    )
    api_thread.start()

    print(f"\n" + "="*40)
    print(f"服務運行中: {api_url}")
    print(f"監控目錄: {replay_path}")
    print("="*40 + "\n")

    threading.Timer(1.5, lambda: webbrowser.open(api_url)).start()

    # 主執行緒保持執行
    try:
        while True: 
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        print("程式結束。")

if __name__ == "__main__":
    main()

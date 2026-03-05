import os
import time
import json
import pickle
import threading
import socket
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from typing import Optional, Dict, Any
import webbrowser
import aiohttp
import asyncio

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bson import ObjectId
import uvicorn

# --- 全域變數與初始化 ---
CONFIG_FILE = "config.json"
app = FastAPI()
templates = Jinja2Templates(directory="templates")

replay_path = "" 
backend_url = ""
backend_key = ""
observer = Observer()
current_user = "尚未設定"
record_games = [] # 紀錄已解析的遊戲時間戳記
running_port = 8000

# --- 1. 工具函式 ---

def find_free_port(start_port: int = 8000, max_tries: int = 100) -> int:
    """尋找電腦中未被佔用的端口"""
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except socket.error:
                continue
    raise IOError("無法找到可用的網路端口")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"replay_path": "", "last_user": "", "backend_url": "", "backend_key": ""}

def save_config(path, user, backend_url, backend_key):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"replay_path": path, "last_user": user, "backend_url": backend_url, "backend_key": backend_key}, f, indent=4)

def universal_serializer(obj: Any) -> Any:
    if isinstance(obj, ObjectId): return str(obj)
    if isinstance(obj, set): return list(obj)
    if isinstance(obj, datetime): return obj.isoformat()
    return str(obj)

# --- 2. 解析與監控邏輯 ---

def parse_identity_v_replay(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    self_res = raw_data.get("self_result", {})
    spec_info = self_res.get("spec_info", {})
    all_players = raw_data.get("all_player_result", [])
    base_info = self_res.get("base_info", {})
    return {
        "game_info": {
            "scene_id": raw_data.get("scene_id_copy"),
            "match_type": raw_data.get("match_type"),
            "match_type": raw_data.get("match_type"),
            "kill_num": base_info.get("kill_num"),
            "is_mvp": raw_data.get("is_mvp"),
            "game_save_time": raw_data.get("game_save_time"),
            "cipher_progress": spec_info.get("generator_status", []),
            "room_guuid": raw_data.get("room_guuid")
        },
        "players": [
            {"uid": p.get("unique_id"), "player_name": p.get("player_name"), "pid": p.get("pid"), "utype": p.get("utype"), "res_type": p.get("res_type"), "is_self": p.get("is_self"), "result": p.get("result"), "spec_info": p.get("spec_info", {})} 
            for p in all_players
        ]
    }

class ReplayHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith("game_info.txt"):
            print(f"[{datetime.now()}] 偵測到新錄影: {event.src_path}")
            time.sleep(2) # 等待檔案寫入完成
            try:
                with open(event.src_path, "rb") as f:
                    raw_data = pickle.load(f)
                parsed_data = parse_identity_v_replay(raw_data)
                # 傳送到後端伺服器
                if backend_url and backend_key:
                    headers = {"Authorization": f"Bearer {backend_key}", "Content-Type": "application/json"}
                    async def send_data():
                        async with aiohttp.ClientSession() as session:
                            async with session.post(backend_url, json=parsed_data, headers=headers) as resp:
                                if resp.status != 200:
                                    raise Exception(f"後端伺服器回應錯誤: {resp.status}")
                                print(f"📤 資料已傳送到後端伺服器: {backend_url}")
                    threading.Thread(target=lambda: asyncio.run(send_data())).start()
                
                print(f"✅ 解析完成: {event.src_path}")
                record_games.append(time.time())
            except Exception as e:
                print(f"❌ 解析失敗: {e}")

def start_monitoring(user_id):
    global observer, current_user, replay_path, backend_url, backend_key
    user_dir = os.path.join(replay_path, user_id)
    if not os.path.exists(user_dir):
        return False
    
    if observer.is_alive():
        observer.stop()
        observer.join()

    observer = Observer()
    observer.schedule(ReplayHandler(), path=user_dir, recursive=True)
    observer.start()
    current_user = user_id
    save_config(replay_path, user_id, backend_url, backend_key)
    return True

# --- 3. FastAPI 路由 ---

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "replay_path": replay_path,
        "current_user": current_user
    })

@app.get("/user_list")
async def get_user_list():
    if not replay_path or not os.path.exists(replay_path):
        return {"users": []}
    user_dirs = [d for d in os.listdir(replay_path) if os.path.isdir(os.path.join(replay_path, d))]
    return {"users": user_dirs}

@app.post("/update_settings")
async def update_settings(request: Request):
    global replay_path, current_user, backend_url, backend_key
    data = await request.json()
    new_path = data.get("record_path", "").replace("\\", "/")
    new_user = data.get("user")
    new_backend_url = data.get("backend_url", "")
    new_backend_key = data.get("backend_key", "")

    if new_path and new_path != replay_path:
        if os.path.exists(new_path):
            replay_path = new_path
        else:
            raise HTTPException(status_code=400, detail="路徑不存在")
    
    if new_backend_url:
        backend_url = new_backend_url
    
    if new_backend_key:
        backend_key = new_backend_key
        save_config(replay_path, current_user, backend_url, backend_key)

    if new_user:
        if start_monitoring(new_user):
            return {"message": f"設定已更新！監控中: {new_user}", "refresh_users": True}
    
    save_config(replay_path, current_user, backend_url, backend_key)
    return {"message": "設定已儲存", "refresh": True}

@app.get("/recorded_games")
async def get_recorded_games():
    return {"recorded_games": record_games}

@app.get("/health_check")
async def health_check():
    return {"status": "ok", "is_monitoring": observer.is_alive(), "current_path": f"{replay_path}/{current_user}"}

# --- 4. 主程式啟動 ---

if __name__ == "__main__":
    # A. 載入設定與處理路徑
    config = load_config()
    replay_path = config.get("replay_path", "").replace("\\", "/")
    last_user = config.get("last_user", "")

    if not replay_path or not os.path.exists(replay_path):
        root = tk.Tk()
        root.withdraw()
        selected = filedialog.askdirectory(title="選擇第五人格安裝資料夾")
        if selected:
            replay_path = os.path.join(selected, "Documents", "video").replace("\\", "/")
            save_config(replay_path, "")
        else:
            print("未選擇路徑，程式結束。")
            exit(0)

    # B. 啟動自動監控
    if last_user and os.path.exists(os.path.join(replay_path, last_user)):
        print(f"自動啟動監控玩家: {last_user}")
        start_monitoring(last_user)

    # C. 尋找端口並啟動伺服器
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

    # D. 自動開啟瀏覽器
    threading.Timer(1.5, lambda: webbrowser.open(api_url)).start()

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        if observer.is_alive():
            observer.stop()
            observer.join()
        print("程式結束。")
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import ConfigManager
from monitor import ReplayMonitorManager
from sync_manager import SyncManager

def create_app(config: ConfigManager, monitor: ReplayMonitorManager, sync_manager: SyncManager) -> FastAPI:
    app = FastAPI()
    templates = Jinja2Templates(directory="templates")

    @app.get("/", response_class=HTMLResponse)
    async def get_index(request: Request):
        return templates.TemplateResponse("index.html", {
            "request": request,
            "replay_path": config.get("replay_path"),
            "current_user": monitor.current_user if monitor.current_user else "尚未設定"
        })

    @app.get("/user_list")
    async def get_user_list():
        r_path = config.get("replay_path")
        if not r_path or not os.path.exists(r_path):
            return {"users": []}
        user_dirs = [d for d in os.listdir(r_path) if os.path.isdir(os.path.join(r_path, d))]
        return {"users": user_dirs}

    @app.post("/update_settings")
    async def update_settings(request: Request):
        data = await request.json()
        new_path = data.get("record_path", "").replace("\\", "/")
        new_user = data.get("user")
        new_backend_url = data.get("backend_url", config.get("backend_url"))
        new_backend_key = data.get("backend_key", config.get("backend_key"))

        current_path = config.get("replay_path")
        if new_path and new_path != current_path:
            if not os.path.exists(new_path):
                raise HTTPException(status_code=400, detail="路徑不存在")
            current_path = new_path

        # 統一委派 ConfigManager 儲存
        config.save(
            replay_path=current_path,
            backend_url=new_backend_url,
            backend_key=new_backend_key
        )

        if new_user:
            user_dir = os.path.join(current_path, new_user)
            if monitor.start(user_dir, new_user):
                config.save(last_user=new_user)
                return {"message": f"設定已更新！監控中: {new_user}", "refresh_users": True}
        
        return {"message": "設定已儲存", "refresh": True}

    @app.get("/sync_records")
    async def get_sync_records():
        return {
            "records": sync_manager.list_records(),
            "summary": sync_manager.summary(),
            "storage_dir": sync_manager.storage_dir,
        }

    @app.get("/recorded_games")
    async def get_recorded_games():
        return {"recorded_games": monitor.record_games}

    @app.post("/sync_records/{record_id}/retry")
    async def retry_sync_record(record_id: str):
        record = sync_manager.retry_record(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="找不到同步紀錄")
        return {"message": "已排程重傳", "record_id": record_id}

    @app.post("/sync_records/retry_failed")
    async def retry_failed_sync_records():
        count = sync_manager.retry_failed_records()
        return {"message": f"已排程重傳 {count} 筆失敗紀錄", "count": count}

    @app.get("/health_check")
    async def health_check():
        return {
            "status": "ok", 
            "is_monitoring": monitor.is_alive(), 
            "current_path": f"{config.get('replay_path')}/{monitor.current_user}",
            "sync_summary": sync_manager.summary(),
        }

    return app

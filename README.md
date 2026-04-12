# Identity V Rank Analyzer CLI

此工具會監控第五人格本機錄影資料夾，偵測新產生的 game_info.txt，解析後自動上傳到後端 API。

## 功能

- 自動監控指定玩家錄影目錄（Watchdog）
- 解析錄影 pickle 資料為可上傳 JSON
- 透過本機 Web 介面調整設定
- 背景自動上傳至後端（使用 X-API-Key）

## 需求環境

- Python 3.10+
- 可讀取第五人格錄影資料夾權限

## 安裝

1. 進入專案目錄
2. 安裝相依套件

```bash
pip install -r requirements.txt
```

## 啟動

```bash
python main.py
```

啟動後程式會：

1. 嘗試讀取 config.json
2. 若 replay_path 無效，彈出資料夾選擇視窗
3. 啟動本機 Web 服務（預設從 8050 往上找可用埠）
4. 自動開啟瀏覽器設定頁面

## 設定檔

設定檔為 config.json，欄位如下：

```json
{
	"replay_path": "C:/IdentityV2/Documents/video",
	"last_user": "9793569",
	"backend_url": "http://127.0.0.1:9999/api/v1/matches",
	"backend_key": "your-api-key"
}
```

- replay_path：錄影根目錄（底下會有玩家編號子目錄）
- last_user：上次監控的玩家編號
- backend_url：後端上傳端點
- backend_key：後端 API Key（HTTP Header 使用 X-API-Key）

## Web 介面

啟動後可在首頁設定：

- 錄影路徑
- 要監控的玩家
- 後端 URL
- 後端 API Key

設定儲存後會即時切換監控目標。

## 上傳流程

1. Watchdog 偵測到新檔 game_info.txt
2. 讀取 pickle 並解析
3. 非同步發送 POST 到 backend_url
4. Header 帶入：

```text
X-API-Key: <backend_key>
Content-Type: application/json
```

上傳內容已對齊後端 `POST /api/v1/matches` 契約，會送出以下核心欄位：

- `room_guuid`
- `scene_id`
- `match_type`
- `rank_level`
- `kill_num`
- `utype`
- `pid`
- `game_save_time`
- `cipher_progress`（object）
- `players[]`（`player_id`, `character_id`, `player_name`, `res_type`）
- `ladder_score_info[]`（`pid`, `score`）

## 常見問題

### 啟動後沒有偵測到錄影

- 確認 replay_path 指向包含玩家子目錄的 video 根目錄
- 確認選到正確玩家（last_user）
- 確認作業系統權限允許讀取該資料夾

### 顯示上傳失敗

- 檢查 backend_url 是否可連線
- 檢查 backend_key 是否正確且仍有效
- 確認後端服務已啟動並接受 POST /api/v1/matches

### 沒有彈出瀏覽器

- 手動開啟終端機顯示的本機網址，例如 http://127.0.0.1:8050

## 專案結構

- main.py：程式進入點，組裝所有元件
- api.py：本機設定頁 API 與模板渲染
- monitor.py：檔案監控與觸發上傳
- parsers.py：錄影資料解析
- uploaders.py：後端上傳邏輯
- config.py：設定檔讀寫


# -*- coding: utf-8 -*-
from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form, Depends, BackgroundTasks, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import uvicorn
import os
import shutil
import re
from datetime import datetime, timezone
import traceback
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
import json
import logging # 引入 logging 模組
import sys # 用於更嚴格的啟動錯誤處理
import sqlite3

from pytubefix import YouTube
from pytubefix.exceptions import RegexMatchError, VideoUnavailable, PytubeFixError

import google.generativeai as genai

# --- 配置日誌 (重要) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 設定常數和目錄 ---
TEMP_AUDIO_STORAGE_DIR = os.getenv("APP_TEMP_AUDIO_STORAGE_DIR", "./temp_audio")
GENERATED_REPORTS_DIR = os.getenv("APP_GENERATED_REPORTS_DIR", "./generated_reports")
DATABASE_URL = "data/tasks.db" # SQLite 資料庫檔案路徑
MAX_CONCURRENT_TASKS = 2 # 最大並行任務數

# global_api_key: Optional[str] = None # Replaced by dependency injection
# api_key_is_valid: bool = False # Replaced by dependency injection logic
temporary_api_key_storage: Optional[str] = None # Stores API key set via /api/set_api_key

# tasks_db: Dict[str, Dict[str, Any]] = {} # Replaced by SQLite
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TASKS)

app = FastAPI(title="AI_paper API v2.4 (穩定性優化版 - SQLite & DI)")

# --- 自訂 RequestValidationError 例外處理 (強化錯誤日誌) ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_details = exc.errors()
    logger.error(f"--- [ERROR_VALIDATION] Request to '{request.url}' failed Pydantic validation ---")
    logger.error(f"[ERROR_VALIDATION] Details: {json.dumps(error_details, indent=2, ensure_ascii=False)}")
    logger.error(f"--- [ERROR_VALIDATION] End of Pydantic validation error details ---")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": error_details},
    )

# --- Jinja2 模板設定 ---
templates_main_dir = "templates"
report_content_template_str = """
<div id='report-title-display' class='report-main-title'>{{ report_title }} (由 {{ model_id }} 生成)</div>
{% if summary_data %}
<div id='report-summary' class='report-content'>
  <h3><i class='fas fa-lightbulb icon-accent'></i> 重點摘要</h3>
  {% if summary_data.intro_paragraph %}
    <p class='intro-paragraph'>{{ summary_data.intro_paragraph }}</p>
  {% endif %}
  {% if summary_data.items %}
    {% for item in summary_data.items %}
      <h3><strong>{{ loop.index }}. {{ item.subtitle }}</strong></h3>
      {% if item.details %}
        <ul>
          {% for detail in item.details %}
            <li>{{ detail }}</li>
          {% endfor %}
        </ul>
      {% endif %}
    {% endfor %}
  {% endif %}
  {% if summary_data.bilingual_append %}
    <p>{{ summary_data.bilingual_append }}</p>
  {% endif %}
</div>
{% endif %}

{% if transcript_paragraphs %}
<div id='report-transcript' class='report-content'>
  <h3><i class='fas fa-file-alt icon-accent'></i> 逐字稿</h3>
  {% if transcript_paragraphs.bilingual_prepend %}
    <p>{{ transcript_paragraphs.bilingual_prepend }}</p>
  {% endif %}
  {% for p_item in transcript_paragraphs.paragraphs %}
    {% if p_item.is_speaker_line %}
      <p><strong>{{ p_item.speaker }}:</strong> {{ p_item.content }}</p>
    {% else %}
      <p>{{ p_item.content }}</p>
    {% endif %}
    {% if p_item.insert_hr_after %}
      <hr class='transcript-divider'>
    {% endif %}
  {% endfor %}
</div>
{% endif %}
"""
from jinja2 import Template
report_content_jinja_template = Template(report_content_template_str)

# --- Pydantic 模型定義 (添加了更詳細的 Field 驗證) ---
class ProcessUrlRequest(BaseModel):
    url: str = Field(..., pattern=r"^https?:\/\/(www\.)?(youtube\.com|youtu\.be)\/.*$", description="有效的 YouTube 網址")

class GenerateReportRequest(BaseModel):
    source_type: str = Field(..., pattern="^(youtube|upload)$", description="來源類型，只能是 'youtube' 或 'upload'")
    source_path: str = Field(..., min_length=1, description="音訊來源的本地檔案路徑")
    model_id: str = Field(..., min_length=1, description="用於生成報告的 AI 模型 ID")
    output_options: List[str] = Field(..., min_items=1, description="報告輸出格式選項，例如 'summary_tc', 'md', 'txt'")
    # custom_prompts 仍為 Optional，前端會根據邏輯判斷是否傳遞
    custom_prompts: Optional[Dict[str, str]] = Field(None, description="自訂提示詞，鍵為 'summary_prompt' 或 'transcript_prompt'")

class SetApiKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=10, description="Google API 金鑰")

# --- FastAPI 事件處理 ---
@app.on_event("startup")
async def startup_event():
    os.makedirs(TEMP_AUDIO_STORAGE_DIR, exist_ok=True)
    os.makedirs(GENERATED_REPORTS_DIR, exist_ok=True)
    logger.info(f"臨時音訊儲存目錄 '{TEMP_AUDIO_STORAGE_DIR}' 已確認存在。")
    logger.info(f"生成報告儲存目錄 '{GENERATED_REPORTS_DIR}' 已確認存在。")
    logger.info(f"資料庫檔案將儲存在 '{DATABASE_URL}'。")

    init_db() # 初始化資料庫和表

    # 環境變數中的 API 金鑰優先於應用程式啟動時的配置
    env_api_key = os.getenv("GOOGLE_API_KEY")
    if env_api_key:
        logger.info("[STARTUP] 在環境變數中找到 GOOGLE_API_KEY。嘗試使用其配置 genai...")
        try:
            genai.configure(api_key=env_api_key)
            next(genai.list_models(), None) # 驗證金鑰
            logger.info("[STARTUP] [SUCCESS] 使用環境變數中的 GOOGLE_API_KEY 成功配置並驗證 genai。")
        except Exception as e_configure:
            logger.error(f"[STARTUP] [ERROR] 使用環境變數中的 GOOGLE_API_KEY 配置 genai 時發生錯誤: {e_configure}")
            # 即使這裡失敗，如果稍後透過 /api/set_api_key 設定了有效的金鑰，應用仍可能工作
    else:
        logger.info("[STARTUP] 未在環境變數中找到 GOOGLE_API_KEY。genai 將等待 API 金鑰透過端點設定。")

    # 清理舊的臨時音訊檔案 (簡單示例：清理一天前的檔案)
    # 實際應用中，可能需要更複雜的清理策略或透過外部排程任務來執行
    # 注意：這裡只清理 TEMP_AUDIO_STORAGE_DIR，不清理 GENERATED_REPORTS_DIR
    for filename in os.listdir(TEMP_AUDIO_STORAGE_DIR):
        file_path = os.path.join(TEMP_AUDIO_STORAGE_DIR, filename)
        try:
            if os.path.isfile(file_path) and (datetime.now() - datetime.fromtimestamp(os.path.getmtime(file_path))).days > 1:
                os.remove(file_path)
                logger.info(f"已清理過期臨時檔案: {filename}")
        except Exception as e:
            logger.warning(f"清理臨時檔案 {filename} 時發生錯誤: {e}")

# --- 資料庫輔助函式 ---
def get_db_connection():
    os.makedirs(os.path.dirname(DATABASE_URL), exist_ok=True) # 確保 data 目錄存在
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False) # 允許在不同線程中使用
    conn.row_factory = sqlite3.Row # 讓查詢結果可以像字典一樣訪問列
    return conn

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            source_name TEXT,
            model_id TEXT,
            submit_time TEXT NOT NULL,
            start_time TEXT,
            completion_time TEXT,
            result_preview_html TEXT,
            download_links TEXT, -- Store as JSON string
            error_message TEXT,
            request_data TEXT     -- Store as JSON string
        )
        ''')
        conn.commit()
        logger.info("SQLite database and tasks table initialized successfully.")
    except sqlite3.Error as e:
        logger.error(f"Error initializing SQLite database: {e}")
        # 根據需要，這裡可以決定是否要讓應用程式在資料庫初始化失敗時終止
        # raise # 重新拋出異常可能會導致應用程式啟動失敗
    except Exception as e_global:
        logger.error(f"An unexpected error occurred during database initialization: {e_global}")
        # raise
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@app.on_event("shutdown")
async def shutdown_event():
    executor.shutdown(wait=True)
    logger.info("[INFO] ThreadPoolExecutor 已關閉。")

# --- API 金鑰依賴注入 ---
async def get_validated_api_key(request: Request) -> str:
    # 優先從環境變數讀取
    api_key_to_test = os.getenv("GOOGLE_API_KEY")
    source = "environment variable"

    # 如果環境變數沒有，則嘗試從臨時存儲讀取
    global temporary_api_key_storage
    if not api_key_to_test and temporary_api_key_storage:
        api_key_to_test = temporary_api_key_storage
        source = "temporary storage"

    if not api_key_to_test:
        logger.warning("[API_KEY_DEP] API key not found in environment variables or temporary storage.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API 金鑰尚未設定。請透過環境變數或 API 端點設定。")

    try:
        # 基本檢查
        if len(api_key_to_test) < 10: # 假設 API key 長度至少為10
            raise ValueError("API key is too short.")

        # 關鍵：使用此金鑰配置 genai 並執行輕量級驗證
        # 這樣，依賴此函式的路由可以直接使用 genai 功能，而不需再次配置
        genai.configure(api_key=api_key_to_test)
        logger.info(f"[API_KEY_DEP] genai configured with API key from {source}.")
        # 嘗試 list_models 作為最終驗證步驟
        next(genai.list_models(), None)
        logger.info(f"[API_KEY_DEP] API key from {source} validated by listing models.")
        return api_key_to_test
    except Exception as e:
        logger.error(f"[API_KEY_DEP] Error during validation or configuration of API key from {source}: {e}")
        # 清除可能已設定的無效臨時金鑰，防止後續請求嘗試使用它
        if source == "temporary storage":
            temporary_api_key_storage = None
            logger.info("[API_KEY_DEP] Invalid temporary API key cleared due to validation failure.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"提供的 API 金鑰 ({source}) 無效或驗證失敗: {e}")

# --- 靜態檔案與主模板 (強化啟動檢查) ---
try:
    # Get the directory where app.py is located
    app_dir = os.path.dirname(os.path.abspath(__file__))
    logger.debug(f"FastAPI app.py 啟動時的 app_dir: {app_dir}")
    static_dir_path = os.path.join(app_dir, "static")
    templates_dir_path = os.path.join(app_dir, templates_main_dir) # templates_main_dir is "templates"

    # 嚴格檢查目錄是否存在，如果不存在則終止應用程式啟動
    if not os.path.exists(static_dir_path):
        logger.critical(f"靜態檔案目錄 '{static_dir_path}' 不存在。應用程式無法啟動。")
        sys.exit(1) # 強制退出
    if not os.path.exists(templates_dir_path):
        logger.critical(f"主模板目錄 '{templates_dir_path}' 不存在。應用程式無法啟動。")
        sys.exit(1) # 強制退出

    app.mount("/static", StaticFiles(directory=static_dir_path), name="static")
    templates = Jinja2Templates(directory=templates_dir_path)
except Exception as e:
    logger.critical(f"設定靜態檔案或主模板時發生嚴重錯誤: {e}。應用程式無法啟動。")
    sys.exit(1) # 強制退出


# --- API 金鑰管理 API (強化驗證邏輯) ---
@app.post("/api/set_api_key")
async def set_api_key(request_data: SetApiKeyRequest):
    global temporary_api_key_storage
    logger.debug(f"Received request to set temporary API key.")
    try:
        # Validate and configure genai with the new key
        genai.configure(api_key=request_data.api_key)
        next(genai.list_models(), None) # Validate by trying to list models

        temporary_api_key_storage = request_data.api_key
        logger.info(f"[SUCCESS] Temporary API key set and validated successfully.")
        return {"message": "臨時 API 金鑰已設定並驗證成功。"}
    except Exception as e_val:
        logger.error(f"[ERROR] Failed to validate or set temporary API key: {e_val}")
        # temporary_api_key_storage = None # Ensure it's not set if validation fails - get_validated_api_key handles this
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"提供的臨時 API 金鑰驗證失敗: {e_val}")

@app.get("/api/check_api_key_status")
async def check_api_key_status(api_key: str = Depends(get_validated_api_key)):
    # If get_validated_api_key dependency succeeds, it means an API key (either from env or temp)
    # has been found and successfully used to configure and validate genai.
    # The actual key string is in api_key variable but we don't need to use it here explicitly.
    env_key_exists = bool(os.getenv("GOOGLE_API_KEY"))
    temp_key_exists = bool(temporary_api_key_storage)

    status_detail = "API 金鑰有效。"
    if env_key_exists:
        status_detail += " (來源：環境變數)"
    elif temp_key_exists:
        status_detail += " (來源：臨時設定)"
    else:
        # This case should ideally not be reached if get_validated_api_key works correctly,
        # as it would raise an exception if no key is found.
        status_detail = "API 金鑰有效，但無法判斷來源 (異常情況)。"

    logger.debug(f"API 金鑰狀態檢查：{status_detail}")
    return {"status": "set_and_valid", "message": status_detail}
    # --- Old logic commented out ---
    # global global_api_key, api_key_is_valid
    # if global_api_key and api_key_is_valid:
    #     logger.debug("API 金鑰狀態檢查：已設定且有效。")
    #     return {"status": "set_and_valid", "message": "API 金鑰已設定且有效。"}
    # elif global_api_key and not api_key_is_valid:
    #     logger.debug("API 金鑰狀態檢查：已設定但驗證失敗。")
    #     return {"status": "set_but_invalid", "message": "API 金鑰已設定但驗證失敗，請重新設定。"}
    # else:
    #     logger.debug("API 金鑰狀態檢查：未設定。")
    #     return {"status": "not_set", "message": "API 金鑰尚未設定，請設定 API 金鑰。"}


# --- 輔助函式 (sanitize_filename, generate_html_report_content_via_jinja) ---
def sanitize_base_filename(title: str, max_length: int = 50) -> str:
    if not title: title = "untitled_audio"
    title = str(title)
    title = re.sub(r'[\\/:*?"<>|&]', "_", title)
    title = title.replace(" ", "_")
    title = re.sub(r"_+", "_", title)
    title = title.strip('_')
    if title.startswith('.'): title = "_" + title[1:]
    return title[:max_length]

def generate_html_report_content_via_jinja(report_title: str, summary_data: Optional[Dict], transcript_data: Optional[Dict], model_id: str) -> str:
    try:
        return report_content_jinja_template.render(
            report_title=report_title,
            summary_data=summary_data,
            transcript_paragraphs=transcript_data,
            model_id=model_id
        )
    except Exception as e:
        logger.error(f"Jinja2 模板渲染報告內容時發生錯誤: {e}")
        traceback.print_exc()
        return f"<div class='report-content'><p style='color:red;'>抱歉，生成報告預覽時發生內部錯誤：{str(e)}</p></div>"

# --- process_audio_and_generate_report_task (強化錯誤處理) ---
async def process_audio_and_generate_report_task(task_id: str, request_data: GenerateReportRequest, api_key: str):
    # api_key is passed from the route that used Depends(get_validated_api_key)
    # Configure genai for this background task execution context
    try:
        genai.configure(api_key=api_key)
        # Optional: further validation like list_models() if desired, but get_validated_api_key should have done it.
        logger.info(f"[TASK {task_id}] genai configured successfully for background execution.")
    except Exception as e_conf_bg:
        logger.error(f"[TASK {task_id}] [ERROR_CRITICAL] Failed to configure genai in background task: {e_conf_bg}")
        # Update task status to failed
        error_message = f"背景任務中 API 金鑰配置失敗: {e_conf_bg}"
        completion_time_iso = datetime.now(timezone.utc).isoformat()
        try:
            conn_err = get_db_connection()
            cursor_err = conn_err.cursor()
            cursor_err.execute("UPDATE tasks SET status = ?, error_message = ?, completion_time = ? WHERE task_id = ?",
                               ("failed", error_message, completion_time_iso, task_id))
            conn_err.commit()
        except sqlite3.Error as e_sql_err:
            logger.error(f"[TASK {task_id}] [ERROR_DB] 更新任務狀態為 'failed' (背景金鑰配置錯誤) 時 SQLite 錯誤: {e_sql_err}")
        finally:
            if 'conn_err' in locals() and conn_err: conn_err.close()
        return # Critical failure, cannot proceed

    start_time_iso = datetime.now(timezone.utc).isoformat()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET status = ?, start_time = ? WHERE task_id = ?",
                       ("processing", start_time_iso, task_id))
        conn.commit()
        logger.info(f"[TASK {task_id}] 狀態更新為 'processing', 開始時間: {start_time_iso}")
    except sqlite3.Error as e_sql:
        logger.error(f"[TASK {task_id}] [ERROR_DB] 更新任務狀態為 'processing' 時 SQLite 錯誤: {e_sql}")
        # 如果初始狀態更新失敗，可能需要決定是否繼續任務
        # 此處選擇繼續，但記錄錯誤
    finally:
        if 'conn' in locals() and conn: conn.close()

    logger.info(f"[TASK {task_id}] 處理開始: {request_data.source_path} (模型: {request_data.model_id})")

    # Removed check for global_api_key and api_key_is_valid, as api_key is now passed and configured.
    # if not global_api_key or not api_key_is_valid:
    #     error_message = "API 金鑰無效或未設定於背景任務啟動時。請先設定有效的 API 金鑰。"
    #     completion_time_iso = datetime.now(timezone.utc).isoformat()
    #     try:
    #         conn = get_db_connection()
    #         cursor = conn.cursor()
    #         cursor.execute("UPDATE tasks SET status = ?, error_message = ?, completion_time = ? WHERE task_id = ?",
    #                        ("failed", error_message, completion_time_iso, task_id))
    #         conn.commit()
    #     except sqlite3.Error as e_sql_fail:
    #         logger.error(f"[TASK {task_id}] [ERROR_DB] 更新任務狀態為 'failed' (API 金鑰無效) 時 SQLite 錯誤: {e_sql_fail}")
    #     finally:
    #         if 'conn' in locals() and conn: conn.close()
    #     logger.error(f"[TASK {task_id}] [ERROR] 失敗 - {error_message}"); return

    try:
        # 模擬 AI 輸出和結構化資料轉換邏輯
        # 這裡應該是實際調用 genai API 的地方
        # 注意：之前使用 len(tasks_db) * 0.5 的模擬延時，現在 tasks_db 不再是記憶體字典。
        # 如果需要基於當前任務數量的延時，需要從資料庫查詢。為簡化，這裡使用固定延時。
        await asyncio.sleep(5 + 2 * 0.5) # 假設平均有2個任務在運行

        # --- 指導原則：處理同步阻塞的 AI 呼叫 ---
        # 未來將此處的模擬操作替換為實際的 AI 模型呼叫 (例如 google-generativeai)。
        # 由於 genai.GenerativeModel().generate_content() 是同步阻塞操作，
        # 必須在 asyncio 事件迴圈中透過 await asyncio.to_thread() 或
        # await loop.run_in_executor(executor, ...) 來執行，以避免阻塞伺服器。
        # 範例:
        # model = genai.GenerativeModel(request_data.model_id) # 假設 genai 已配置 API Key
        #
        # # 使用 asyncio.to_thread (Python 3.9+)
        # # response_summary = await asyncio.to_thread(model.generate_content, "提示詞摘要: " + source_basename)
        # # simulated_summary_text = response_summary.text
        #
        # # 或者使用 loop.run_in_executor (需要獲取 loop 和 executor)
        # # loop = asyncio.get_running_loop()
        # # response_transcript = await loop.run_in_executor(executor, model.generate_content, "提示詞逐字稿: " + source_basename)
        # # simulated_transcript_text = response_transcript.text
        #
        # # 請確保 genai.configure(api_key=...) 已在應用程式啟動時或透過依賴注入有效執行。
        # --- 結束指導原則 ---

        simulated_summary_text: Optional[str] = None
        simulated_transcript_text: Optional[str] = None
        source_basename = os.path.basename(request_data.source_path)

        # 根據 output_options 和 custom_prompts 生成模擬內容
        # 這裡可以加入 genai.GenerativeModel().generate_content() 的實際呼叫
        # 示例：
        # model = genai.GenerativeModel(request_data.model_id)
        # response = model.generate_content("請總結這段音訊的內容：" + source_basename, stream=False)
        # simulated_summary_text = response.text

        if "summary_tc" in request_data.output_options or "summary_transcript_tc" in request_data.output_options or "transcript_bilingual_summary" in request_data.output_options:
            base_summary = f"這是對 '{source_basename}' 使用 '{request_data.model_id}' 模型生成的繁體中文重點摘要的開頭總結段落。\n" \
                           f"**重點1子標題**\n- 這是第一個重點的第一個細節。\n- 這是第一個重點的第二個細節。\n" \
                           f"**重點2子標題**\n- 這是第二個重點的第一個細節，它可能比較長一點。\n- 這是第二個重點的第二個細節。"
            if request_data.custom_prompts and request_data.custom_prompts.get("summary_prompt"):
                base_summary = f"根據自訂提示詞 '{request_data.custom_prompts['summary_prompt'][:50]}...' 生成的摘要：\n" + base_summary
            simulated_summary_text = base_summary
            if "transcript_bilingual_summary" in request_data.output_options: simulated_summary_text += "\n(This is the English part of the bilingual summary.)"

        if "summary_transcript_tc" in request_data.output_options or "transcript_bilingual_summary" in request_data.output_options:
            base_transcript = f"這是 '{source_basename}' 的模擬逐字稿內容的第一段。\n" \
                              f"這是第二段。\n發言者A：模擬對話開始。\n發言者B：好的。\n第五段，觸發分隔線。\n第六段。"
            if request_data.custom_prompts and request_data.custom_prompts.get("transcript_prompt"):
                base_transcript = f"根據自訂提示詞 '{request_data.custom_prompts['transcript_prompt'][:50]}...' 生成的逐字稿：\n" + base_transcript
            simulated_transcript_text = base_transcript
            if "transcript_bilingual_summary" in request_data.output_options: simulated_transcript_text = f"(Original Language Transcript for '{source_basename}')\n" + simulated_transcript_text

        # 轉換為結構化資料
        structured_summary_data = None
        if simulated_summary_text:
            lines = simulated_summary_text.strip().split('\n')
            intro = lines.pop(0) if lines else ""
            bilingual_append_text = None
            if "transcript_bilingual_summary" in request_data.output_options and lines and "(This is the English part" in lines[-1]:
                bilingual_append_text = lines.pop(-1)
            items = []
            current_item_details = []
            current_subtitle = None
            for line in lines:
                if line.startswith("**") and line.endswith("**"):
                    if current_subtitle:
                        items.append({"subtitle": current_subtitle.strip('*'), "details": list(current_item_details)})
                    current_subtitle = line.strip('*')
                    current_item_details.clear()
                elif line.startswith("- ") and current_subtitle:
                    current_item_details.append(line[2:])
                elif current_subtitle and current_item_details: # 處理多行細節
                    current_item_details[-1] += "\n" + line
                elif current_subtitle: # 處理沒有 - 開頭的細節
                    current_item_details.append(line)

            if current_subtitle: # 添加最後一個項目
                items.append({"subtitle": current_subtitle.strip('*'), "details": list(current_item_details)})
            structured_summary_data = {"intro_paragraph": intro, "items": items, "bilingual_append": bilingual_append_text}

        structured_transcript_data = None
        if simulated_transcript_text:
            paragraphs_raw = simulated_transcript_text.strip().split('\n')
            hr_interval = 5
            formatted_paragraphs = []
            bilingual_prepend_text = None
            if "transcript_bilingual_summary" in request_data.output_options and paragraphs_raw and paragraphs_raw[0].startswith("(Original Language Transcript"):
                bilingual_prepend_text = paragraphs_raw.pop(0)
            for i, p_text in enumerate(paragraphs_raw):
                if p_text.strip():
                    match = re.match(r"^(發言者\s?[A-Za-z0-9]+)[:：]\s*(.*)", p_text)
                    formatted_paragraphs.append({
                        "content": match.group(2) if match else p_text,
                        "is_speaker_line": bool(match),
                        "speaker": match.group(1) if match else None,
                        "insert_hr_after": (i + 1) % hr_interval == 0 and i < len(paragraphs_raw) - 1
                    })
            structured_transcript_data = {"bilingual_prepend": bilingual_prepend_text, "paragraphs": formatted_paragraphs}

        # 檔案生成邏輯
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("generating_report", task_id))
            conn.commit()
            logger.info(f"[TASK {task_id}] 狀態更新為 'generating_report'")
        except sqlite3.Error as e_sql_gen_report_status:
            logger.warning(f"[TASK {task_id}] [ERROR_DB] 更新任務狀態為 'generating_report' 時 SQLite 錯誤: {e_sql_gen_report_status}")
        finally:
            if 'conn' in locals() and conn: conn.close()

        await asyncio.sleep(1) # 模擬生成報告的時間

        report_title = f"'{source_basename}' 的 AI 分析報告"
        preview_html = generate_html_report_content_via_jinja(report_title, structured_summary_data, structured_transcript_data, request_data.model_id)

        base_report_filename = f"{sanitize_base_filename(source_basename, 30)}_{request_data.model_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        download_links = {}

        # 生成完整的 HTML 報告
        full_html_content = f"""<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{report_title}</title><link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"></head><body class="dark-mode"><div class="container content-wrapper" style="padding-top: 20px; padding-bottom: 20px;"><section class="card animated" style="margin-bottom:0;">{preview_html}</section></div></body></html>"""
        html_file_path = os.path.join(GENERATED_REPORTS_DIR, f"{base_report_filename}.html")
        try:
            with open(html_file_path, "w", encoding="utf-8") as f:
                f.write(full_html_content)
            download_links["html"] = f"/generated_reports/{os.path.basename(html_file_path)}"
        except Exception as e:
            logger.error(f"[TASK {task_id}] [ERROR] 儲存 HTML 報告時發生錯誤: {e}")

        # 生成 Markdown 報告
        if "md" in request_data.output_options:
            md_parts = [f"# {report_title}\n\n"]
            if structured_summary_data:
                md_parts.extend(
                    [f"## 重點摘要\n\n{structured_summary_data['intro_paragraph']}\n\n" if structured_summary_data.get('intro_paragraph') else "## 重點摘要\n\n"] +
                    [f"### {item['subtitle']}\n" + "".join([f"- {d}\n" for d in item.get('details', [])]) + "\n" for item in structured_summary_data.get('items', [])] +
                    ([f"{structured_summary_data['bilingual_append']}\n\n"] if structured_summary_data.get('bilingual_append') else [])
                )
            if structured_transcript_data:
                md_parts.extend(
                    ["## 逐字稿\n\n"] +
                    ([f"{structured_transcript_data['bilingual_prepend']}\n\n"] if structured_transcript_data.get('bilingual_prepend') else []) +
                    [f"**{p['speaker']}:** {p['content']}\n\n" if p["is_speaker_line"] else f"{p['content']}\n\n" for p in structured_transcript_data.get('paragraphs', [])]
                )
            md_file_path = os.path.join(GENERATED_REPORTS_DIR, f"{base_report_filename}.md")
            try:
                with open(md_file_path, "w", encoding="utf-8") as f:
                    f.write("".join(md_parts))
                download_links["md"] = f"/generated_reports/{os.path.basename(md_file_path)}"
            except Exception as e:
                logger.error(f"[TASK {task_id}] [ERROR] 儲存 Markdown 報告錯誤: {e}")

        # 生成 TXT 報告
        if "txt" in request_data.output_options:
            txt_parts = [f"{report_title}\n\n"]
            if structured_summary_data:
                txt_parts.extend(
                    ["重點摘要\n--------------------\n"] +
                    ([f"{structured_summary_data['intro_paragraph']}\n\n"] if structured_summary_data.get('intro_paragraph') else []) +
                    [f"{item['subtitle']}\n" + "".join([f"  - {d}\n" for d in item.get('details', [])]) + "\n" for item in structured_summary_data.get('items', [])] +
                    ([f"{structured_summary_data['bilingual_append']}\n\n"] if structured_summary_data.get('bilingual_append') else [])
                )
            if structured_transcript_data:
                txt_parts.extend(
                    ["逐字稿\n--------------------\n"] +
                    ([f"{structured_transcript_data['bilingual_prepend']}\n\n"] if structured_transcript_data.get('bilingual_prepend') else []) +
                    [f"{p['speaker']}: {p['content']}\n\n" if p["is_speaker_line"] else f"{p['content']}\n\n" for p in structured_transcript_data.get('paragraphs', [])]
                )
            txt_file_path = os.path.join(GENERATED_REPORTS_DIR, f"{base_report_filename}.txt")
            try:
                with open(txt_file_path, "w", encoding="utf-8") as f:
                    f.write("".join(txt_parts))
                download_links["txt"] = f"/generated_reports/{os.path.basename(txt_file_path)}"
            except Exception as e:
                logger.error(f"[TASK {task_id}] [ERROR] 儲存 TXT 報告錯誤: {e}")

        completion_time_iso = datetime.now(timezone.utc).isoformat()
        download_links_json = json.dumps(download_links)
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tasks SET status = ?, result_preview_html = ?, download_links = ?, completion_time = ? WHERE task_id = ?",
                ("completed", preview_html, download_links_json, completion_time_iso, task_id)
            )
            conn.commit()
            logger.info(f"[TASK {task_id}] [SUCCESS] 處理完成。結果已存入資料庫。")
        except sqlite3.Error as e_sql_complete:
            logger.error(f"[TASK {task_id}] [ERROR_DB] 更新任務狀態為 'completed' 並儲存結果時 SQLite 錯誤: {e_sql_complete}")
            # 即使資料庫更新失敗，任務實際上可能已完成，但狀態未正確反映
        finally:
            if 'conn' in locals() and conn: conn.close()

    except Exception as e:
        error_message = f"背景任務處理失敗: {str(e)}"
        completion_time_iso = datetime.now(timezone.utc).isoformat()
        logger.error(f"[TASK {task_id}] [ERROR] {error_message}")
        traceback.print_exc()
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE tasks SET status = ?, error_message = ?, completion_time = ? WHERE task_id = ?",
                           ("failed", error_message, completion_time_iso, task_id))
            conn.commit()
        except sqlite3.Error as e_sql_final_fail:
            logger.error(f"[TASK {task_id}] [ERROR_DB] 更新任務狀態為 'failed' (一般錯誤) 時 SQLite 錯誤: {e_sql_final_fail}")
        finally:
            if 'conn' in locals() and conn: conn.close()


# --- 音訊來源處理 API ---
def _download_youtube_audio_sync(youtube_url: str, task_id_for_log: Optional[str]="N/A") -> str:
    logger.info(f"[TASK {task_id_for_log}] [SYNC_DOWNLOAD] 開始下載 YouTube 音訊: {youtube_url}")
    try:
        yt = YouTube(youtube_url)
        audio_stream = yt.streams.get_audio_only()
        if not audio_stream:
            audio_stream = yt.streams.filter(only_audio=True, file_extension='m4a').order_by('abr').desc().first()
        if not audio_stream:
            audio_stream = yt.streams.filter(only_audio=True, file_extension='webm').order_by('abr').desc().first()
        if not audio_stream:
            raise PytubeFixError(f"在 YouTube 影片 '{youtube_url}' 中找不到合適的音訊流。")

        title_part = sanitize_base_filename(yt.title, max_length=30)
        timestamp_part = datetime.now().strftime("%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        file_extension = audio_stream.subtype if audio_stream.subtype else "mp4"
        final_filename = f"{title_part}_{timestamp_part}_{unique_id}.{file_extension}"
        actual_downloaded_path = audio_stream.download(output_path=TEMP_AUDIO_STORAGE_DIR, filename=final_filename)

        if not os.path.exists(actual_downloaded_path) or os.path.getsize(actual_downloaded_path) == 0:
            raise PytubeFixError(f"YouTube 音訊檔案 '{final_filename}' 下載後未找到或為空。")

        logger.info(f"[TASK {task_id_for_log}] [SYNC_DOWNLOAD] [SUCCESS] YouTube 音訊成功下載至: {actual_downloaded_path}")
        return actual_downloaded_path
    except PytubeFixError as pte:
        error_msg = f"PytubeFix 在處理 YouTube 音訊 '{youtube_url}' 時發生錯誤: {str(pte)}"
        logger.error(f"[TASK {task_id_for_log}] [SYNC_DOWNLOAD] [ERROR] {error_msg}")
        traceback.print_exc()
        raise PytubeFixError(error_msg) from pte
    except Exception as e:
        error_msg = f"下載 YouTube 音訊 '{youtube_url}' 時發生未預期錯誤: {str(e)}"
        logger.error(f"[TASK {task_id_for_log}] [SYNC_DOWNLOAD] [ERROR] {error_msg}")
        traceback.print_exc()
        raise RuntimeError(error_msg) from e

@app.post("/api/process_youtube_url", response_model=Dict[str, str])
async def api_process_youtube_url(request_data: ProcessUrlRequest):
    log_task_id = str(uuid.uuid4())[:8]
    logger.info(f"[API_YT_URL] [TASK {log_task_id}] 收到 YouTube 網址處理請求: {request_data.url}")
    # Pydantic 已經做了 URL 格式驗證，這裡可以簡化
    try:
        loop = asyncio.get_event_loop()
        local_audio_path = await loop.run_in_executor(executor, _download_youtube_audio_sync, request_data.url, log_task_id)
        return {"message": f"YouTube 音訊 '{os.path.basename(local_audio_path)}' 已成功下載至伺服器。", "youtube_url": request_data.url, "processed_audio_path": local_audio_path}
    except PytubeFixError as pte:
        raise HTTPException(status_code=500, detail=str(pte))
    except Exception as e:
        logger.error(f"[API_YT_URL] [TASK {log_task_id}] [ERROR] 處理 YouTube 網址時發生未預期錯誤: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"處理 YouTube 網址時發生伺服器內部錯誤: {str(e)}")

@app.post("/api/upload_audio_file", response_model=Dict[str, str])
async def api_upload_audio_file(audio_file: UploadFile = File(...)):
    log_task_id = str(uuid.uuid4())[:8]
    logger.info(f"[API_UPLOAD] [TASK {log_task_id}] 收到檔案上傳: {audio_file.filename}, 類型: {audio_file.content_type}")
    original_name, original_ext = os.path.splitext(audio_file.filename if audio_file.filename else "uploaded_audio")

    # 嘗試從 content_type 推斷副檔名
    if not original_ext and audio_file.content_type:
        content_type_map = {
            "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/webm": ".webm",
            "audio/wav": ".wav", "audio/ogg": ".ogg", "audio/aac": ".aac"
        }
        original_ext = content_type_map.get(audio_file.content_type, ".bin") # 預設為 .bin 以防萬一

    base_name = sanitize_base_filename(original_name, max_length=30)
    timestamp = datetime.now().strftime("%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    temp_upload_filename = f"{base_name}_{timestamp}_{unique_id}{original_ext}"
    temp_upload_path = os.path.join(TEMP_AUDIO_STORAGE_DIR, temp_upload_filename)

    try:
        # 使用 asyncio.to_thread 確保檔案寫入不會阻塞 FastAPI 事件循環
        await asyncio.to_thread(shutil.copyfileobj, audio_file.file, open(temp_upload_path, "wb"))
        logger.info(f"[API_UPLOAD] [TASK {log_task_id}] [SUCCESS] 檔案成功儲存至: {temp_upload_path} (大小: {os.path.getsize(temp_upload_path)} bytes)")
        return {"message": f"音訊檔案 '{audio_file.filename}' 上傳並儲存成功。", "filename": audio_file.filename, "content_type": audio_file.content_type, "processed_audio_path": temp_upload_path}
    except Exception as e:
        logger.error(f"[API_UPLOAD] [TASK {log_task_id}] [ERROR] 儲存上傳檔案失敗: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"處理上傳檔案時發生錯誤: {str(e)}")
    finally:
        await audio_file.close()


# --- AI 模型與報告生成 API ---

# 預定義模型資料 (包含中文介紹和排序資訊)
PREDEFINED_MODELS_DATA_APP = {
    "models/gemini-1.5-flash-latest": {
        "id": "models/gemini-1.5-flash-latest",
        "dropdown_display_name": "⚡ Gemini 1.5 Flash (最新版)",
        "chinese_display_name": "Gemini 1.5 Flash 最新版",
        "chinese_summary_parenthesized": "（速度快、多功能、多模態、適用於多樣化任務擴展）",
        "chinese_input_output": "輸入：文字、音訊、圖片、影片 (詳見官方文件)；輸出：文字",
        "chinese_suitable_for": "需要快速回應的多樣化任務、大規模應用、聊天、摘要、音訊處理。",
        "original_description_from_api": "Alias that points to the most recent production (non-experimental) release of Gemini 1.5 Flash, our fast and versatile multimodal model for scaling across diverse tasks.",
        "sort_priority": 1 # 排序優先級，數字越小越靠前
    },
    "models/gemini-1.5-pro-latest": {
        "id": "models/gemini-1.5-pro-latest",
        "dropdown_display_name": "🌟 Gemini 1.5 Pro (最新版)",
        "chinese_display_name": "Gemini 1.5 Pro 最新版",
        "chinese_summary_parenthesized": "（功能強大、大型上下文、多模態、理解複雜情境）",
        "chinese_input_output": "輸入：文字、音訊、圖片、影片 (最高達2百萬token，詳見官方文件)；輸出：文字",
        "chinese_suitable_for": "複雜推理、長篇內容理解與生成、多模態分析、程式碼生成與解釋。",
        "original_description_from_api": "Alias that points to the most recent production (non-experimental) release of Gemini 1.5 Pro, our mid-size multimodal model that supports up to 2 million tokens.",
        "sort_priority": 0 # 最高優先級
    },
    "models/gemini-pro": { # 假設這是純文字的 gemini-pro
        "id": "models/gemini-pro",
        "dropdown_display_name": "Gemini Pro (純文字)",
        "chinese_display_name": "Gemini Pro (純文字版)",
        "chinese_summary_parenthesized": "（優化的純文字生成與理解）",
        "chinese_input_output": "輸入：文字；輸出：文字",
        "chinese_suitable_for": "純文字的問答、摘要、寫作、翻譯等。",
        "original_description_from_api": "Optimized for text-only prompts.",
        "sort_priority": 10
    }
    # 您可以根據需要加入更多預定義模型和它們的中文資訊
}

def get_model_version_score(api_name_lower: str) -> int:
    score = 9999 # 預設較低優先級
    if "latest" in api_name_lower: score = 0
    elif "preview" in api_name_lower:
        score = 1000
        date_match = re.search(r'preview[_-](\d{2})[_-]?(\d{2})', api_name_lower) # 例如 preview-0527
        if date_match:
            try:
                # 組合日期，例如 0527 -> 527，數字越大代表日期越新
                date_score = int(date_match.group(1)) * 100 + int(date_match.group(2))
                score -= date_score # 數字越大越新，所以要減，讓總分數變小
            except ValueError:
                pass # 解析失敗則使用預設值
        else: score += 100 # 無日期的 preview 比有日期的舊
    elif "-exp" in api_name_lower or "experimental" in api_name_lower: score = 2000
    else: # 嘗試解析數字版本號，例如 -001
        num_version_match = re.search(r'-(\d+)$', api_name_lower.split('/')[-1])
        if num_version_match:
            try:
                score = 3000 - int(num_version_match.group(1)) # 數字越大版本越新，所以減
            except ValueError:
                score = 3500
    return score

def sort_models_key_function(model_dict: Dict[str, Any]):
    api_name = model_dict.get("id", "")
    name_lower = api_name.lower()

    # 優先級組 (來自預定義資料或根據名稱猜測)
    priority_group = model_dict.get("sort_priority", 99) # 預定義的優先級
    if priority_group == 99: # 如果沒有預定義的，嘗試猜測
        if "gemini-1.5-pro" in name_lower: priority_group = 2 # 比 flash latest 稍低
        elif "gemini-1.5-flash" in name_lower: priority_group = 3
        elif "gemini-pro" in name_lower and "vision" not in name_lower : priority_group = 12
        elif "gemini" in name_lower: priority_group = 15
        else: priority_group = 20

    version_score = get_model_version_score(name_lower)

    # 主要版本號 (例如 1.5, 1.0) 用於次級排序
    main_version_num = 0.0
    main_version_match = re.search(r'(gemini(?:-1\.5)?)-(\d+\.\d+|\d+)', name_lower) # gemini-1.5-pro, gemini-pro
    if not main_version_match: main_version_match = re.search(r'gemini-(\d+\.\d+|\d+)', name_lower)

    if main_version_match:
        try:
            main_version_num = float(main_version_match.groups()[-1]) # 取最後捕獲的數字組
        except ValueError:
            pass

    # 排序規則：優先級組 (越小越優先) -> 主要版本號 (越大越優先，所以取負值) -> 版本分數 (越小越優先) -> 字母順序
    return (priority_group, -main_version_num, version_score, name_lower)


@app.get("/api/get_models")
async def api_get_models_enhanced(api_key: str = Depends(get_validated_api_key)):
    # api_key parameter is now populated by the dependency, which also configures and validates genai
    logger.info("[API_GET_MODELS_ENHANCED] 請求獲取增強型 AI 模型列表。金鑰已透過依賴注入驗證。")

    # The get_validated_api_key dependency will raise HTTPException if the key is invalid or not found,
    # so we don't need the explicit check here anymore. The code will only proceed if a valid key is available
    # and genai has been configured by the dependency.

    all_models_combined = {}
    try:
        logger.debug("[API_GET_MODELS_ENHANCED] 正在從 Google genai.list_models() 查詢線上模型...")
        online_models_count = 0
        for m_obj in genai.list_models():
            # 確保模型支援 generateContent 方法
            if 'generateContent' in m_obj.supported_generation_methods:
                online_models_count +=1
                model_data = {
                    "id": m_obj.name,
                    "dropdown_display_name": m_obj.display_name if m_obj.display_name else m_obj.name.replace("models/", ""),
                    "chinese_display_name": m_obj.display_name if m_obj.display_name else m_obj.name.replace("models/", ""), # 預設使用 display_name
                    "chinese_summary_parenthesized": "", # 預設空
                    "chinese_input_output": f"輸入 Tokens: {m_obj.input_token_limit}, 輸出 Tokens: {m_obj.output_token_limit}",
                    "chinese_suitable_for": "請參考 API 原始描述。",
                    "original_description_from_api": m_obj.description if m_obj.description else "N/A",
                    "sort_priority": 99 # 預設一個較低的優先級給線上獲取的、未在預定義中出現的模型
                }
                all_models_combined[m_obj.name] = model_data
        logger.debug(f"[API_GET_MODELS_ENHANCED] 從 API 獲取到 {online_models_count} 個支援 generateContent 的模型。")

    except Exception as e_list_models:
        logger.error(f"[API_GET_MODELS_ENHANCED] 呼叫 genai.list_models() 失敗: {e_list_models}")
        # 如果 API 呼叫失敗，返回明確的錯誤模型狀態給前端
        return JSONResponse(content=[
            {"id": "error-api-key-or-network",
             "dropdown_display_name": "錯誤：無法獲取模型 (API金鑰或網路問題)",
             "chinese_display_name": "API金鑰或網路問題",
             "chinese_summary_parenthesized": "（無法連線到 Google API，請檢查網路或金鑰狀態）",
             "chinese_input_output": "N/A",
             "chinese_suitable_for": "請檢查您的 API 金鑰是否正確，並確保網路連接正常。",
             "original_description_from_api": "Failed to retrieve models from Google API. Check API key and network connectivity.",
             "sort_priority": -1 # 最高優先級
            }
        ], status_code=500) # 返回 500 錯誤狀態

    # 將預定義的資料覆蓋或添加到合併列表中 (預定義的優先)
    for predefined_id, predefined_data in PREDEFINED_MODELS_DATA_APP.items():
        all_models_combined[predefined_id] = predefined_data # 預定義的資料有更高優先級

    # 轉換為列表並排序
    sorted_models_list = sorted(all_models_combined.values(), key=sort_models_key_function)

    logger.info(f"[API_GET_MODELS_ENHANCED] 返回 {len(sorted_models_list)} 個模型給前端。")
    return JSONResponse(content=sorted_models_list)


@app.post("/api/generate_report", status_code=202)
async def api_submit_generate_report_task(
    request_data: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_validated_api_key) # Inject and validate API key
):
    task_id = str(uuid.uuid4())
    logger.info(f"[API_GEN_REPORT] [TASK {task_id}] 收到報告生成請求: 來源='{request_data.source_path}', 模型='{request_data.model_id}'。API金鑰已注入。")

    # Removed direct check of global_api_key and api_key_is_valid
    # if not global_api_key or not api_key_is_valid:
    #     logger.warning(f"[API_GEN_REPORT] [TASK {task_id}] API 金鑰無效或未設定。")
    #     raise HTTPException(status_code=401, detail="無效或未設定的 API 金鑰。請先設定有效的 API 金鑰。")

    if not os.path.exists(request_data.source_path):
        logger.error(f"[API_GEN_REPORT] [TASK {task_id}] 音訊來源檔案不存在: {request_data.source_path}")
        raise HTTPException(status_code=404, detail=f"指定的音訊來源檔案不存在: {os.path.basename(request_data.source_path)}")

    # 將任務資訊存入 SQLite
    try:
        request_data_json = json.dumps(request_data.model_dump()) # Pydantic v2
        download_links_json = json.dumps(None) # 初始化 download_links 為 null JSON
        submit_time_iso = datetime.now(timezone.utc).isoformat()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (task_id, status, source_name, model_id, submit_time, request_data, download_links)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, "queued", os.path.basename(request_data.source_path), request_data.model_id,
             submit_time_iso, request_data_json, download_links_json)
        )
        conn.commit()
        logger.info(f"[API_GEN_REPORT] [TASK {task_id}] 任務資訊成功寫入資料庫。")
    except sqlite3.Error as e_sql:
        logger.error(f"[API_GEN_REPORT] [TASK {task_id}] [ERROR_DB] 將任務資訊寫入 SQLite 時發生錯誤: {e_sql}")
        traceback.print_exc()
        # 即使資料庫寫入失敗，也可能希望任務繼續（如果記憶體處理可行），或在此處拋出錯誤
        # 為了保持與之前行為一致（記憶體處理），這裡暫不拋出 HTTP 錯誤，但記錄嚴重錯誤
        # raise HTTPException(status_code=500, detail="儲存任務資訊到資料庫時發生錯誤。")
        # 不過，如果資料庫是主要狀態來源，則應拋出錯誤：
        raise HTTPException(status_code=500, detail=f"任務提交失敗：無法將任務資訊儲存到資料庫。錯誤: {e_sql}")
    except Exception as e_gen:
        logger.error(f"[API_GEN_REPORT] [TASK {task_id}] [ERROR_UNEXPECTED] 準備任務資料時發生未預期錯誤: {e_gen}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"任務提交失敗：準備任務資料時發生未預期錯誤。錯誤: {e_gen}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

    # Pass the validated api_key to the background task
    background_tasks.add_task(process_audio_and_generate_report_task, task_id, request_data, api_key)
    logger.info(f"[API_GEN_REPORT] [TASK {task_id}] 任務已加入佇列。")
    return {"task_id": task_id, "message": "報告生成任務已加入佇列。", "status": "queued"}


# --- 任務狀態查詢 API ---
@app.get("/api/tasks")
async def get_all_tasks_status():
    logger.debug("[API_TASKS_ALL] 請求獲取所有任務的狀態。")
    tasks_list = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks ORDER BY submit_time DESC")
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            task_data = dict(row) # 將 sqlite3.Row 轉換為字典
            # 解析 JSON 字串欄位
            if task_data.get("download_links"):
                try:
                    task_data["download_links"] = json.loads(task_data["download_links"])
                except json.JSONDecodeError:
                    logger.warning(f"[API_TASKS_ALL] 解析任務 {task_data['task_id']} 的 download_links JSON 失敗。")
                    task_data["download_links"] = None # 或設為錯誤提示
            # request_data 通常不需要在列表視圖中完整顯示，可以選擇不解析或只解析部分
            # if task_data.get("request_data"):
            #     try:
            #         task_data["request_data"] = json.loads(task_data["request_data"])
            #     except json.JSONDecodeError:
            #         logger.warning(f"[API_TASKS_ALL] 解析任務 {task_data['task_id']} 的 request_data JSON 失敗。")
            #         task_data["request_data"] = None
            del task_data["request_data"] # 從列表視圖中移除詳細請求資料，以減少傳輸量
            del task_data["result_preview_html"] # 也移除 HTML 預覽

            tasks_list.append(task_data)

        logger.info(f"[API_TASKS_ALL] 成功從資料庫檢索到 {len(tasks_list)} 個任務。")

    except sqlite3.Error as e_sql:
        logger.error(f"[API_TASKS_ALL] [ERROR_DB] 從 SQLite 讀取所有任務時發生錯誤: {e_sql}")
        traceback.print_exc()
        # 返回空列表或錯誤訊息，取決於期望的行為
        # return JSONResponse(content={"error": "無法獲取任務列表", "detail": str(e_sql)}, status_code=500)
        # 為了前端相容性，暫時返回空列表
    except Exception as e_gen:
        logger.error(f"[API_TASKS_ALL] [ERROR_UNEXPECTED] 處理所有任務狀態時發生未預期錯誤: {e_gen}")
        traceback.print_exc()
        # return JSONResponse(content={"error": "處理任務列表時發生未預期錯誤", "detail": str(e_gen)}, status_code=500)

    return JSONResponse(content=tasks_list) # 已按 submit_time DESC 排序

@app.get("/api/tasks/{task_id}")
async def get_task_status_and_result(task_id: str):
    logger.debug(f"[API_TASK_ID] 請求獲取任務 {task_id} 的詳細狀態。")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            logger.warning(f"[API_TASK_ID] 在資料庫中找不到任務 ID: {task_id}")
            raise HTTPException(status_code=404, detail="找不到指定的任務 ID。")

        task_data = dict(row) # 將 sqlite3.Row 轉換為字典

        # 解析 JSON 字串欄位
        if task_data.get("download_links"):
            try:
                task_data["download_links"] = json.loads(task_data["download_links"])
            except json.JSONDecodeError:
                logger.warning(f"[API_TASK_ID] 解析任務 {task_id} 的 download_links JSON 失敗。")
                task_data["download_links"] = {"error": "Failed to parse download links"}

        # request_data 通常不需要在單任務詳細視圖中返回給客戶端，除非特定需求
        if 'request_data' in task_data:
            del task_data['request_data'] # 通常不返回完整的原始請求

        logger.info(f"[API_TASK_ID] 成功從資料庫檢索到任務 {task_id} 的詳細資訊。")
        return JSONResponse(content=task_data)

    except sqlite3.Error as e_sql:
        logger.error(f"[API_TASK_ID] [ERROR_DB] 從 SQLite 讀取任務 {task_id} 時發生錯誤: {e_sql}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查詢任務狀態時發生資料庫錯誤: {e_sql}")
    except Exception as e_gen:
        logger.error(f"[API_TASK_ID] [ERROR_UNEXPECTED] 處理任務 {task_id} 狀態時發生未預期錯誤: {e_gen}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查詢任務狀態時發生未預期錯誤: {e_gen}")


# --- 下載生成的報告檔案 API ---
try:
    if os.path.exists(GENERATED_REPORTS_DIR):
        app.mount("/generated_reports", StaticFiles(directory=GENERATED_REPORTS_DIR), name="generated_reports")
        logger.info(f"已掛載 '{GENERATED_REPORTS_DIR}' 至 '/generated_reports' 以供直接下載。")
except Exception as e:
    logger.error(f"掛載 generated_reports 目錄時發生錯誤: {e}")

# --- 主頁面 ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    logger.debug("[API_ROOT] 請求主頁面。")
    if templates is None:
        error_msg = "<html><body><h1>錯誤：主模板引擎未初始化。請檢查伺服器日誌。</h1></body></html>"
        logger.critical("主模板引擎未初始化。")
        return HTMLResponse(error_msg, status_code=500)
    return templates.TemplateResponse("index.html", {"request": request, "title": "AI_paper 智能助理 v2.4 (穩定版)"})


# --- API 狀態 ---
@app.get("/api/status")
async def get_api_status():
    logger.debug("[API_STATUS] 請求 API 狀態。")
    return {"status": "AI_paper API v2.4 is running", "version": "2.4.0_optimized"}

if __name__ == "__main__":
    logger.info("若在本地執行 app.py，請確保 CWD 設定正確。")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True, workers=1)



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

from pytubefix import YouTube
from pytubefix.exceptions import RegexMatchError, VideoUnavailable, PytubeFixError

import google.generativeai as genai

# --- Default Prompts ---
DEFAULT_SUMMARY_PROMPT_PY = "請提供這份文件的繁體中文摘要，風格應專業且資訊豐富，包含一個引人入勝的開頭段落，接著列出3-5個帶有子標題的關鍵重點，每個重點應有2-3個詳細說明。語言風格：專業、學術、客觀。"
DEFAULT_TRANSCRIPT_PROMPT_PY = "請將這份音訊逐字稿轉換成繁體中文，並修正明顯的語法錯誤或口語贅詞，使其更流暢易讀。如果音檔內容包含多位發言者，請盡可能標示出不同的發言者 (例如：發言者A, 發言者B)。"

# --- P-Prompt Definitions ---
P1_AUDIO_TO_TC_TRANSCRIPT = DEFAULT_TRANSCRIPT_PROMPT_PY

P2_AUDIO_TO_ORIGINAL_TRANSCRIPT = """# 提示詞 P2: 音訊轉原文逐字稿

## 任務說明:
請將提供的音訊檔案(檔案名稱: `{audio_filename}`, 原始影片標題: `{video_title}`)轉換為一份"詳細的原文逐字稿".

## 指示:
1.  **語言:** 請以音訊中實際使用的語言進行逐字稿的撰寫. 如果音訊中包含多種語言混合(例如中文夾雜英文, 或英文夾雜日文等), 請在逐字稿中"完整如實地呈現"這種多語言混合情況, 無需翻譯成單一語言.
2.  **準確性:** 力求準確捕捉所有口語內容.
3.  **格式:**
    * 逐字稿應為純文字格式.
    * 如果音訊中有多位發言者, 請盡可能嘗試區分(例如: Speaker A:, Speaker B:, 發言者甲:). 若難以區分,則無需特別標註.
    * 對於專有名詞, 品牌名稱, 人名等, 請依照其在音訊中被讀出的原始語言呈現.
4.  **內容:** 請勿添加任何非口語內容的摘要, 評論或註解. 只需提供純粹的逐字稿.
5.  **時間戳記:** 請勿包含任何時間戳記.
"""

P3_TC_TRANSCRIPT_TO_TC_SUMMARY = DEFAULT_SUMMARY_PROMPT_PY

P4_ORIGINAL_TRANSCRIPT_TO_TC_SUMMARY = """# 提示詞 P4: 從原文逐字稿生成繁體中文重點摘要

## 任務說明:
您將收到一段"音訊原文逐字稿"的文字內容(此逐字稿可能包含多種語言). 請根據此逐字稿, 理解其核心思想, 並生成一份精煉、準確的"繁體中文重點摘要".

## 指示:
1.  **目標語言:** 摘要的全部內容必須使用繁體中文(台灣用語習慣).
2.  **結構與格式要求(請嚴格遵守):**
    * **開頭段落:** 首先, 撰寫一個簡短的段落(繁體中文), 清晰地概括整個逐字稿的整體主旨、核心議題或主要觀點.
    * **重點條目:** 接著, 列出數個(建議3-5個)主要的重點條目(繁體中文).
        * 每個重點條目必須有一個以 `<strong>` HTML 標籤包裹的**粗體**子標題, 並以數字編號(例如:"<strong>1. 主題一:[子標題文字]</strong>").
        * 在每個粗體子標題下方, 使用無序列表 (`<ul>` 和 `<li>` HTML 標籤) 的形式, 簡潔地列出該重點下的 2-4 個關鍵細節或支撐論點(繁體中文). 每個 `<li>` 內的文字應精煉.
3.  **內容要求:**
    * 摘要內容應忠實反映逐字稿的核心思想和關鍵資訊, 避免加入個人詮釋或逐字稿中未提及的內容.
    * 文字應精煉、準確、易於理解.
4.  **請勿包含:**
    * 任何時間戳記.
    * "重點摘要"或類似的標題文字. 請直接以開頭段落開始您的回應.

## 待處理的音訊原文逐字稿內容:
---[逐字稿文字開始]---
{original_transcript_text}
---[逐字稿文字結束]---
"""

P5_ORIGINAL_TRANSCRIPT_TO_EN_SUMMARY = """# Prompt P5: Generate English Key Summary from Original Transcript

## Task Description:
You will receive the text of an "Original Audio Transcript" (this transcript may contain multiple languages). Based on this transcript, understand its core ideas and generate a concise and accurate "English Key Summary".

## Instructions:
1.  **Target Language:** The entire summary must be in English.
2.  **Structure and Formatting Requirements (Please adhere strictly):**
    * **Opening Paragraph:** First, write a brief paragraph (in English) that clearly summarizes the overall theme, core issues, or main points of the entire transcript.
    * **Key Points:** Then, list several (3-5 recommended) main key points (in English).
        * Each key point must have a **bold** subheading using `<strong>` HTML tags and be numbered (e.g., "<strong>1. Topic One: [Subheading Text]</strong>").
        * Below each bold subheading, use an unordered list (with `<ul>` and `<li>` HTML tags) to concisely list 2-4 key details or supporting arguments for that point (in English). Each `<li>` should contain refined text.
3.  **Content Requirements:**
    * The summary should faithfully reflect the core ideas and key information from the transcript, avoiding personal interpretations or information not mentioned in the transcript.
    * The text should be concise, accurate, and easy to understand.
4.  **Do Not Include:**
    * Any timestamps.
    * Titles like "Key Summary". Please begin your response directly with the opening paragraph.

## Original Audio Transcript to Process:
---[Transcript Text Start]---
{original_transcript_text}
---[Transcript Text End]---
"""

# Standardize punctuation for all relevant prompts
prompt_names_to_standardize = [
    "DEFAULT_SUMMARY_PROMPT_PY", "DEFAULT_TRANSCRIPT_PROMPT_PY",
    "P2_AUDIO_TO_ORIGINAL_TRANSCRIPT",
    "P4_ORIGINAL_TRANSCRIPT_TO_TC_SUMMARY", "P5_ORIGINAL_TRANSCRIPT_TO_EN_SUMMARY"
]

punctuation_map = {
    '（': '(', '）': ')', '：': ':', '，': ',', '。': '.',
    '「': '"', '」': '"', '『': '"', '』': '"', '、': ','
}

for name in prompt_names_to_standardize:
    if name in globals():
        current_value = globals()[name]
        for full, half in punctuation_map.items():
            current_value = current_value.replace(full, half)
        globals()[name] = current_value

# Re-assign P1 and P3 after their base prompts are standardized
P1_AUDIO_TO_TC_TRANSCRIPT = DEFAULT_TRANSCRIPT_PROMPT_PY
P3_TC_TRANSCRIPT_TO_TC_SUMMARY = DEFAULT_SUMMARY_PROMPT_PY


# --- 配置日誌 (重要) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 設定常數和目錄 ---
TEMP_AUDIO_STORAGE_DIR = "/content/ai_paper_temp_audio"
GENERATED_REPORTS_DIR = "/content/ai_paper_generated_reports"
MAX_CONCURRENT_TASKS = 2 # 最大並行任務數

global_api_key: Optional[str] = None
api_key_is_valid: bool = False # 追蹤 API 金鑰的有效性
tasks_db: Dict[str, Dict[str, Any]] = {}
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TASKS)

app = FastAPI(title="AI_paper API v2.4 (穩定性優化版)")

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
    <div class='intro-paragraph-container'>{{ summary_data.intro_paragraph | safe }}</div>
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


    global global_api_key, api_key_is_valid
    env_api_key = os.getenv("GOOGLE_API_KEY")
    if env_api_key:
        logger.info("[INFO] 在環境變數中找到 GOOGLE_API_KEY。嘗試驗證...")
        try:
            genai.configure(api_key=env_api_key)
            # 嘗試一個輕量級的 API 呼叫來實質驗證金鑰
            # 如果能成功列出模型，則金鑰應有效
            next(genai.list_models(), None) # 嘗試迭代一個以觸發潛在錯誤或驗證成功
            global_api_key = env_api_key
            api_key_is_valid = True
            logger.info("[SUCCESS] 環境變數中的 GOOGLE_API_KEY 已設定並驗證成功。")
        except Exception as e_configure:
            logger.error(f"[ERROR] 使用環境變數中的 GOOGLE_API_KEY 配置 genai 時發生錯誤: {e_configure}")
            api_key_is_valid = False
    else:
        logger.info("[INFO] 未在環境變數中找到 GOOGLE_API_KEY。等待使用者透過 API 設定。")

@app.on_event("shutdown")
async def shutdown_event():
    executor.shutdown(wait=True)
    logger.info("[INFO] ThreadPoolExecutor 已關閉。")

# --- 靜態檔案與主模板 (強化啟動檢查) ---
try:
    current_cwd = os.getcwd()
    logger.debug(f"FastAPI app.py 啟動時的 CWD: {current_cwd}")
    static_dir_path = os.path.join(current_cwd, "static")
    templates_dir_path = os.path.join(current_cwd, templates_main_dir)

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
    global global_api_key, api_key_is_valid
    logger.debug(f"接收到設定 API 金鑰請求。金鑰 (遮罩後): {'*' * (len(request_data.api_key) - 4) + request_data.api_key[-4:] if len(request_data.api_key) > 4 else '***'}...")
    is_successfully_validated = False
    try:
        genai.configure(api_key=request_data.api_key)
        # 實際驗證：嘗試列出模型，如果失敗則金鑰可能無效或權限不足
        next(genai.list_models(), None) # 嘗試迭代一個以觸發潛在錯誤
        is_successfully_validated = True
    except Exception as e_val:
        logger.error(f"[ERROR] 驗證提供的 API 金鑰時發生錯誤: {e_val}")
        is_successfully_validated = False

    if is_successfully_validated:
        global_api_key = request_data.api_key
        api_key_is_valid = True
        logger.info(f"[SUCCESS] 臨時 API 金鑰已設定並驗證成功。")
        return {"message": "API 金鑰已設定並驗證成功。"}
    else:
        api_key_is_valid = False # 確保標記為無效
        logger.error(f"[ERROR] 提供的臨時 API 金鑰驗證失敗。")
        raise HTTPException(status_code=400, detail="提供的 API 金鑰驗證失敗。請檢查金鑰是否正確且具有所需權限。")

@app.get("/api/check_api_key_status")
async def check_api_key_status():
    global global_api_key, api_key_is_valid
    if global_api_key and api_key_is_valid:
        logger.debug("API 金鑰狀態檢查：已設定且有效。")
        return {"status": "set_and_valid", "message": "API 金鑰已設定且有效。"}
    elif global_api_key and not api_key_is_valid:
        logger.debug("API 金鑰狀態檢查：已設定但驗證失敗。")
        return {"status": "set_but_invalid", "message": "API 金鑰已設定但驗證失敗，請重新設定。"}
    else:
        logger.debug("API 金鑰狀態檢查：未設定。")
        return {"status": "not_set", "message": "API 金鑰尚未設定，請設定 API 金鑰。"}


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

def sanitize_model_id_for_filename(model_id: str) -> str:
    sanitized = model_id.replace("models/", "").replace("/", "_")
    # Further sanitization can be added if other problematic characters are found
    return sanitized

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
async def process_audio_and_generate_report_task(task_id: str, request_data: GenerateReportRequest):
    tasks_db[task_id]["status"] = "processing"
    tasks_db[task_id]["start_time"] = datetime.now(timezone.utc).isoformat()
    logger.info(f"[TASK {task_id}] 處理開始: {request_data.source_path} (模型: {request_data.model_id})")

    if not global_api_key or not api_key_is_valid:
        tasks_db[task_id]["status"] = "failed"
        tasks_db[task_id]["error_message"] = "API 金鑰無效或未設定於背景任務啟動時。請先設定有效的 API 金鑰。"
        tasks_db[task_id]["completion_time"] = datetime.now(timezone.utc).isoformat()
        logger.error(f"[TASK {task_id}] [ERROR] 失敗 - API 金鑰無效。"); return

    source_basename = os.path.basename(request_data.source_path)
    audio_file_for_api = None # Initialize outside try block for access in finally

    try:
        # Ensure genai is configured with the API key for this task
        genai.configure(api_key=global_api_key)
        logger.info(f"[TASK {task_id}] genai configured with API key for task.")

        # Upload audio file
        logger.info(f"[TASK {task_id}] Starting audio file upload for: {request_data.source_path}")
        try:
            audio_file_for_api = genai.upload_file(path=request_data.source_path)
            logger.info(f"[TASK {task_id}] Successfully uploaded audio file. File ID: {audio_file_for_api.name}, URI: {audio_file_for_api.uri}. Initial state: {audio_file_for_api.state}")
        except Exception as e_upload:
            logger.error(f"[TASK {task_id}] Error uploading audio file: {e_upload}")
            tasks_db[task_id]["status"] = "failed"
            tasks_db[task_id]["error_message"] = f"Audio file upload failed: {e_upload}"
            tasks_db[task_id]["completion_time"] = datetime.now(timezone.utc).isoformat()
            return # Exit if upload fails

        # Polling for ACTIVE state
        if audio_file_for_api:
            max_polling_attempts = 15
            polling_interval_seconds = 2
            for attempt in range(max_polling_attempts):
                logger.info(f"[TASK {task_id}] Checking file state for {audio_file_for_api.name} (Attempt {attempt + 1}/{max_polling_attempts}). Current state: {audio_file_for_api.state}")
                if audio_file_for_api.state == genai.types.FileState.ACTIVE:
                    logger.info(f"[TASK {task_id}] File {audio_file_for_api.name} is now ACTIVE.")
                    break
                elif audio_file_for_api.state == genai.types.FileState.PROCESSING:
                    if attempt == max_polling_attempts - 1:
                        logger.error(f"[TASK {task_id}] File {audio_file_for_api.name} still PROCESSING after {max_polling_attempts} attempts. Timeout.")
                        tasks_db[task_id]["status"] = "failed"
                        tasks_db[task_id]["error_message"] = f"File processing timeout for {audio_file_for_api.name} after {max_polling_attempts * polling_interval_seconds} seconds."
                        tasks_db[task_id]["completion_time"] = datetime.now(timezone.utc).isoformat()
                        return
                    logger.info(f"[TASK {task_id}] File {audio_file_for_api.name} is PROCESSING. Waiting for {polling_interval_seconds} seconds.")
                    await asyncio.sleep(polling_interval_seconds)
                    try:
                        updated_file = genai.get_file(name=audio_file_for_api.name)
                        if updated_file:
                            audio_file_for_api = updated_file
                        else:
                            logger.warning(f"[TASK {task_id}] genai.get_file({audio_file_for_api.name}) returned None unexpectedly.")
                            # Continue to next attempt or timeout
                    except Exception as e_get_file:
                        logger.error(f"[TASK {task_id}] Error fetching file state for {audio_file_for_api.name}: {e_get_file}")
                        # Continue to next attempt or timeout
                else: # FAILED or unspecified state
                    logger.error(f"[TASK {task_id}] File {audio_file_for_api.name} is in a terminal non-ACTIVE state: {audio_file_for_api.state}.")
                    tasks_db[task_id]["status"] = "failed"
                    tasks_db[task_id]["error_message"] = f"File {audio_file_for_api.name} entered state {audio_file_for_api.state}."
                    tasks_db[task_id]["completion_time"] = datetime.now(timezone.utc).isoformat()
                    return
            else: # Loop completed without break
                if audio_file_for_api.state != genai.types.FileState.ACTIVE:
                    logger.error(f"[TASK {task_id}] File {audio_file_for_api.name} did not become ACTIVE after polling. Final state: {audio_file_for_api.state}")
                    tasks_db[task_id]["status"] = "failed"
                    tasks_db[task_id]["error_message"] = f"File {audio_file_for_api.name} failed to become ACTIVE. Final state: {audio_file_for_api.state}."
                    tasks_db[task_id]["completion_time"] = datetime.now(timezone.utc).isoformat()
                    return
        else: # audio_file_for_api is None
            logger.error(f"[TASK {task_id}] audio_file_for_api is None before polling. This indicates an issue with the upload logic prior to polling.")
            tasks_db[task_id]["status"] = "failed"
            tasks_db[task_id]["error_message"] = "Internal error: Audio file object not available for state polling."
            tasks_db[task_id]["completion_time"] = datetime.now(timezone.utc).isoformat()
            return

        # Instantiate Gemini Model
        model = genai.GenerativeModel(request_data.model_id)
        logger.info(f"[TASK {task_id}] Gemini model '{request_data.model_id}' instantiated.")

        # Determine Processing Option (A, B, C)
        option_choice = None
        if "transcript_bilingual_summary" in request_data.output_options:
            option_choice = "C"
        elif "summary_transcript_tc" in request_data.output_options:
            option_choice = "B"
        elif "summary_tc" in request_data.output_options:
            option_choice = "A"
        else:
            logger.warning(f"[TASK {task_id}] Could not determine option choice from output_options: {request_data.output_options}. Defaulting to Option B.")
            option_choice = "B" # Fallback
        logger.info(f"[TASK {task_id}] Determined processing option: {option_choice} based on output_options: {request_data.output_options}")

        generated_tc_transcript_text: Optional[str] = None
        generated_original_transcript_text: Optional[str] = None
        generated_tc_summary_text: Optional[str] = None
        generated_en_summary_text: Optional[str] = None

        # --- Transcript Generation (P1 or P2) ---
        current_transcript_prompt = None
        # transcript_is_for_report = False # This variable is not strictly needed as we assign to specific text vars

        if option_choice == "A" or option_choice == "B":
            current_transcript_prompt = P1_AUDIO_TO_TC_TRANSCRIPT
            if request_data.custom_prompts and request_data.custom_prompts.get("transcript_prompt"):
                current_transcript_prompt = request_data.custom_prompts["transcript_prompt"]
                logger.info(f"[TASK {task_id}] Using custom transcript prompt (for P1-like audio to TC transcript).")
            else:
                logger.info(f"[TASK {task_id}] Using P1_AUDIO_TO_TC_TRANSCRIPT.")
        elif option_choice == "C":
            current_transcript_prompt = P2_AUDIO_TO_ORIGINAL_TRANSCRIPT
            if request_data.custom_prompts and request_data.custom_prompts.get("transcript_prompt"): # Assuming "transcript_prompt" can be for original lang too
                current_transcript_prompt = request_data.custom_prompts["transcript_prompt"]
                logger.info(f"[TASK {task_id}] Using custom transcript prompt (for P2-like audio to Original transcript).")
            else:
                logger.info(f"[TASK {task_id}] Using P2_AUDIO_TO_ORIGINAL_TRANSCRIPT.")

        if current_transcript_prompt and audio_file_for_api:
            try:
                logger.info(f"[TASK {task_id}] Calling Gemini API for transcript (P1/P2) with prompt: '{current_transcript_prompt[:100]}...'")
                response_transcript_gen = model.generate_content([current_transcript_prompt, audio_file_for_api], generation_config=genai.types.GenerationConfig())
                if option_choice == "A" or option_choice == "B":
                    generated_tc_transcript_text = response_transcript_gen.text
                    logger.info(f"[TASK {task_id}] Received TC transcript (P1). Length: {len(generated_tc_transcript_text) if generated_tc_transcript_text else 0}")
                elif option_choice == "C":
                    generated_original_transcript_text = response_transcript_gen.text
                    logger.info(f"[TASK {task_id}] Received Original transcript (P2). Length: {len(generated_original_transcript_text) if generated_original_transcript_text else 0}")
            except Exception as e_transcript_gen:
                err_msg = f"Error generating transcript (P1/P2): {e_transcript_gen}"
                logger.error(f"[TASK {task_id}] {err_msg}")
                if option_choice == "A" or option_choice == "B": generated_tc_transcript_text = err_msg
                elif option_choice == "C": generated_original_transcript_text = err_msg

        # --- Summary Generation (P3, P4, P5) ---
        if (option_choice == "A" or option_choice == "B"):
            if generated_tc_transcript_text and not generated_tc_transcript_text.startswith("Error"):
                current_summary_prompt = P3_TC_TRANSCRIPT_TO_TC_SUMMARY
                if request_data.custom_prompts and request_data.custom_prompts.get("summary_prompt"):
                    current_summary_prompt = request_data.custom_prompts["summary_prompt"]
                    logger.info(f"[TASK {task_id}] Using custom summary prompt (for P3-like TC summary from TC transcript).")
                else:
                    logger.info(f"[TASK {task_id}] Using P3_TC_TRANSCRIPT_TO_TC_SUMMARY.")
                try:
                    logger.info(f"[TASK {task_id}] Calling Gemini API for TC summary (P3) with prompt: '{current_summary_prompt[:100]}...' Input text length: {len(generated_tc_transcript_text)}")
                    response_summary_tc = model.generate_content([current_summary_prompt, generated_tc_transcript_text], generation_config=genai.types.GenerationConfig())
                    generated_tc_summary_text = response_summary_tc.text
                    logger.info(f"[TASK {task_id}] Received TC summary (P3). Length: {len(generated_tc_summary_text) if generated_tc_summary_text else 0}")
                except Exception as e_summary_tc:
                    err_msg = f"Error generating TC summary (P3): {e_summary_tc}"
                    logger.error(f"[TASK {task_id}] {err_msg}")
                    generated_tc_summary_text = err_msg
            else: # Error or missing TC transcript
                 err_msg_skip = f"Skipped TC summary (P3) due to error or missing TC transcript. Transcript: {generated_tc_transcript_text[:100] if generated_tc_transcript_text else 'None'}"
                 generated_tc_summary_text = err_msg_skip
                 logger.warning(f"[TASK {task_id}] {err_msg_skip}")

        elif option_choice == "C":
            if generated_original_transcript_text and not generated_original_transcript_text.startswith("Error"):
                # P4: Original Transcript to TC Summary
                current_summary_prompt_p4 = P4_ORIGINAL_TRANSCRIPT_TO_TC_SUMMARY
                if request_data.custom_prompts and request_data.custom_prompts.get("summary_prompt"): # Assuming "summary_prompt" is for TC summary
                    current_summary_prompt_p4 = request_data.custom_prompts["summary_prompt"]
                    logger.info(f"[TASK {task_id}] Using custom summary prompt (for P4-like TC summary from Original transcript).")
                else:
                    logger.info(f"[TASK {task_id}] Using P4_ORIGINAL_TRANSCRIPT_TO_TC_SUMMARY.")
                try:
                    logger.info(f"[TASK {task_id}] Calling Gemini API for TC summary (P4) with prompt: '{current_summary_prompt_p4[:100]}...' Input text length: {len(generated_original_transcript_text)}")
                    response_summary_tc_p4 = model.generate_content([current_summary_prompt_p4, generated_original_transcript_text], generation_config=genai.types.GenerationConfig())
                    generated_tc_summary_text = response_summary_tc_p4.text
                    logger.info(f"[TASK {task_id}] Received TC summary (P4). Length: {len(generated_tc_summary_text) if generated_tc_summary_text else 0}")
                except Exception as e_summary_tc_p4:
                    err_msg = f"Error generating TC summary (P4): {e_summary_tc_p4}"
                    logger.error(f"[TASK {task_id}] {err_msg}")
                    generated_tc_summary_text = err_msg

                # P5: Original Transcript to EN Summary
                current_summary_prompt_p5 = P5_ORIGINAL_TRANSCRIPT_TO_EN_SUMMARY
                # Assuming no separate custom prompt for P5 for now. If "summary_prompt_en" exists, it could be used.
                # if request_data.custom_prompts and request_data.custom_prompts.get("summary_prompt_en"):
                #    current_summary_prompt_p5 = request_data.custom_prompts["summary_prompt_en"]
                #    logger.info(f"[TASK {task_id}] Using custom EN summary prompt (for P5-like EN summary from Original transcript).")
                # else:
                logger.info(f"[TASK {task_id}] Using P5_ORIGINAL_TRANSCRIPT_TO_EN_SUMMARY.")
                try:
                    logger.info(f"[TASK {task_id}] Calling Gemini API for EN summary (P5) with prompt: '{current_summary_prompt_p5[:100]}...' Input text length: {len(generated_original_transcript_text)}")
                    response_summary_en_p5 = model.generate_content([current_summary_prompt_p5, generated_original_transcript_text], generation_config=genai.types.GenerationConfig())
                    generated_en_summary_text = response_summary_en_p5.text
                    logger.info(f"[TASK {task_id}] Received EN summary (P5). Length: {len(generated_en_summary_text) if generated_en_summary_text else 0}")
                except Exception as e_summary_en_p5:
                    err_msg = f"Error generating EN summary (P5): {e_summary_en_p5}"
                    logger.error(f"[TASK {task_id}] {err_msg}")
                    generated_en_summary_text = err_msg
            else: # Error or missing original transcript
                err_msg_skip_c = f"Skipped P4 & P5 summaries due to error or missing original transcript. Transcript: {generated_original_transcript_text[:100] if generated_original_transcript_text else 'None'}"
                generated_tc_summary_text = err_msg_skip_c # Both will show this error
                generated_en_summary_text = err_msg_skip_c
                logger.warning(f"[TASK {task_id}] {err_msg_skip_c}")

        # --- Adapt for Parsing Logic ---
        actual_summary_text_for_parsing = generated_tc_summary_text
        actual_transcript_text_for_parsing = None

        if option_choice == "B":
            actual_transcript_text_for_parsing = generated_tc_transcript_text
        elif option_choice == "C":
            actual_transcript_text_for_parsing = generated_original_transcript_text

        if option_choice == "C" and generated_en_summary_text and not generated_en_summary_text.startswith("Error"):
            if actual_summary_text_for_parsing and not actual_summary_text_for_parsing.startswith("Error"):
                actual_summary_text_for_parsing += f"\n\n--- English Summary ---\n{generated_en_summary_text}"
            elif not actual_summary_text_for_parsing or actual_summary_text_for_parsing.startswith("Error"): # If TC summary failed or was skipped
                 actual_summary_text_for_parsing = (actual_summary_text_for_parsing + "\n\n" if actual_summary_text_for_parsing else "") + f"--- English Summary ---\n{generated_en_summary_text}"

        # Determine if summary is pre-formatted HTML
        summary_is_preformatted_html = False # Default to False, meaning Python parsing is needed.

        # Based on current P-prompt definitions (P3, P4, P5 all ask for no HTML tags),
        # and the assumption that custom prompts also do not return pre-formatted HTML
        # that should bypass Python parsing.
        # This flag will consistently be False unless a specific prompt is designed to output raw HTML for direct rendering.
        if request_data.custom_prompts and request_data.custom_prompts.get("summary_prompt"):
            logger.info(f"[TASK {task_id}] Custom summary prompt used; Python parsing will be applied.")
        else:
            logger.info(f"[TASK {task_id}] Default P-prompt used for summary (P3, P4, or P5); Python parsing will be applied as they don't request HTML tags.")

        logger.info(f"[TASK {task_id}] Summary is_preformatted_html set to: {summary_is_preformatted_html}")

        # 轉換為結構化資料
        structured_summary_data = None
        # The log line below already includes the summary_is_preformatted_html flag.
        logger.info(f"[TASK {task_id}] Parsing summary text (length: {len(actual_summary_text_for_parsing) if actual_summary_text_for_parsing else 0}). Preformatted HTML: {summary_is_preformatted_html}")

        if actual_summary_text_for_parsing and \
           (actual_summary_text_for_parsing.startswith("Error generating summary") or \
            actual_summary_text_for_parsing.startswith("Skipped TC summary") or \
            actual_summary_text_for_parsing.startswith("Skipped P4 & P5 summaries")):
            structured_summary_data = {"intro_paragraph": actual_summary_text_for_parsing, "items": []}
        elif summary_is_preformatted_html and actual_summary_text_for_parsing: # This branch will not be taken with current prompts
            structured_summary_data = {
                "intro_paragraph": actual_summary_text_for_parsing, # Store the raw HTML
                "items": [],
                "bilingual_append": None
            }
            logger.info(f"[TASK {task_id}] Using pre-formatted HTML for summary. Content length: {len(actual_summary_text_for_parsing)}")
        elif actual_summary_text_for_parsing: # Needs parsing (P3, P4, P5, or custom prompt)
            lines = [line.strip() for line in actual_summary_text_for_parsing.strip().split('\n') if line.strip()]
            intro = ""
            items = []
            current_item_details = []
            current_subtitle = None

            # Try to find the first paragraph as intro more reliably
            # The first non-subtitle line could be the intro.
            # Or, if the first line is not a subtitle, it's the intro.
            if lines and not re.match(r"^\s*\*\*(.*?)\*\*\s*$", lines[0]):
                intro = lines.pop(0)

            for line in lines:
                subtitle_match = re.match(r"^\s*\*\*(.*?)\*\*\s*$", line) # Allow leading/trailing spaces for subtitle
                if subtitle_match:
                    if current_subtitle: # Save previous item
                        items.append({"subtitle": current_subtitle, "details": list(current_item_details)})
                    current_subtitle = subtitle_match.group(1).strip()
                    current_item_details.clear()
                    if not intro and items: # If intro was not captured and we are already into items, means no dedicated intro line
                        pass
                elif current_subtitle: # This line is part of current_subtitle's details
                    detail_text = line
                    if line.startswith("- "):
                        detail_text = line[2:].strip()

                    if detail_text: # Add non-empty details
                        if current_item_details and not line.startswith("- "): # Continuation of previous detail
                            current_item_details[-1] += "\n" + detail_text
                        else:
                            current_item_details.append(detail_text)
                elif not intro: # If no subtitle context yet, and it's not a subtitle line, it could be part of intro
                    intro += ("\n" if intro else "") + line


            if current_subtitle: # Add the last item
                items.append({"subtitle": current_subtitle, "details": list(current_item_details)})

            if not items and intro and not actual_summary_text.startswith("Error"): # If no items were parsed, the whole text might be the intro
                # This check helps if the summary is just a single block of text without specific formatting.
                pass # intro is already set

            bilingual_append_text = None # This logic was specific to simulation, might remove or adapt if bilingual output is different
            # if "transcript_bilingual_summary" in request_data.output_options and lines and "(This is the English part" in lines[-1]:
            #     bilingual_append_text = lines.pop(-1)

            if not isinstance(items, list):
                logger.warning(f"[TASK {task_id}] 'items' was not a list before creating structured_summary_data. Forcing to empty list. Type was: {type(items)}")
                items = []
            structured_summary_data = {"intro_paragraph": intro.strip(), "items": items, "bilingual_append": bilingual_append_text}
        else: # actual_summary_text is None or empty
            structured_summary_data = {"intro_paragraph": "No summary content received or summary was empty.", "items": []}
        logger.debug(f"[TASK {task_id}] Parsed summary data: intro_len={len(structured_summary_data['intro_paragraph'])}, items_count={len(structured_summary_data.get('items', []))}")

        structured_transcript_data = None
        logger.info(f"[TASK {task_id}] Parsing transcript text (length: {len(actual_transcript_text) if actual_transcript_text else 0}).")
        if actual_transcript_text and actual_transcript_text.startswith("Error generating transcript:"):
            structured_transcript_data = {"paragraphs": [{"content": actual_transcript_text, "is_speaker_line": False, "speaker": None, "insert_hr_after": False}]}
        elif actual_transcript_text:
            paragraphs_raw = actual_transcript_text.strip().split('\n')
            hr_interval = 5 # This can be kept or removed based on desired output styling
            formatted_paragraphs = []
            bilingual_prepend_text = None # This logic was specific to simulation
            # if "transcript_bilingual_summary" in request_data.output_options and paragraphs_raw and paragraphs_raw[0].startswith("(Original Language Transcript"):
            #     bilingual_prepend_text = paragraphs_raw.pop(0)

            for i, p_text in enumerate(paragraphs_raw):
                p_text_stripped = p_text.strip()
                if p_text_stripped: # Process non-empty paragraphs
                    # Regex for speaker: "發言者 A:", "Speaker B:", "發言者C：", etc.
                    # Made it more flexible with speaker names (word characters) and colon/space variations.
                    match = re.match(r"^(發言者\s*[\w\d]+|Speaker\s*[\w\d]+)\s*[:：]\s*(.*)", p_text_stripped, re.IGNORECASE)
                    formatted_paragraphs.append({
                        "content": match.group(2) if match else p_text_stripped,
                        "is_speaker_line": bool(match),
                        "speaker": match.group(1).strip() if match else None,
                        "insert_hr_after": (i + 1) % hr_interval == 0 and i < len(paragraphs_raw) - 1 and bool(match) # HR only after speaker lines for now
                    })
            structured_transcript_data = {"bilingual_prepend": bilingual_prepend_text, "paragraphs": formatted_paragraphs}
        else: # actual_transcript_text is None or empty
            structured_transcript_data = {"paragraphs": [{"content": "No transcript content received or transcript was empty.", "is_speaker_line": False, "speaker": None, "insert_hr_after": False}]}
        logger.debug(f"[TASK {task_id}] Parsed transcript data: paragraphs_count={len(structured_transcript_data.get('paragraphs', []))}")

        # 檔案生成邏輯
        tasks_db[task_id]["status"] = "generating_report"
        # await asyncio.sleep(1) # Original delay, can be removed or adjusted

        report_title = f"'{source_basename}' 的 AI 分析報告"
        preview_html = generate_html_report_content_via_jinja(report_title, structured_summary_data, structured_transcript_data, request_data.model_id)

        sanitized_model_id = sanitize_model_id_for_filename(request_data.model_id)
        base_report_filename = f"{sanitize_base_filename(source_basename, 30)}_{sanitized_model_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"[TASK {task_id}] Sanitized model ID for filename: '{sanitized_model_id}'. Base report filename: '{base_report_filename}'.")
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

        tasks_db[task_id]["status"] = "completed"
        tasks_db[task_id]["result_preview_html"] = preview_html
        tasks_db[task_id]["download_links"] = download_links
        tasks_db[task_id]["completion_time"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[TASK {task_id}] [SUCCESS] 處理完成。")

    except Exception as e:
        tasks_db[task_id]["status"] = "failed"
        tasks_db[task_id]["error_message"] = f"背景任務處理失敗: {str(e)}"
        tasks_db[task_id]["completion_time"] = datetime.now(timezone.utc).isoformat()
        logger.error(f"[TASK {task_id}] [ERROR] 背景任務處理失敗: {e}")
        traceback.print_exc()
    finally:
        if audio_file_for_api:
            try:
                logger.info(f"[TASK {task_id}] Deleting uploaded file {audio_file_for_api.uri} ({audio_file_for_api.name}) from Google Cloud.")
                genai.delete_file(audio_file_for_api.name) # Use .name for deletion
                logger.info(f"[TASK {task_id}] Successfully deleted file {audio_file_for_api.uri}.")
            except Exception as e_delete_file:
                logger.warning(f"[TASK {task_id}] Failed to delete uploaded file {audio_file_for_api.uri}: {e_delete_file}")


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
async def api_get_models_enhanced():
    logger.info("[API_GET_MODELS_ENHANCED] 請求獲取增強型 AI 模型列表。")

    if not api_key_is_valid: # API Key 無效時不嘗試列出模型
        logger.warning("[API_GET_MODELS_ENHANCED] API Key 無效，返回包含錯誤訊息的模型列表。")
        return JSONResponse(content=[
            {"id": "error-api-key-or-network",
             "dropdown_display_name": "錯誤：無法獲取模型 (API金鑰無效)",
             "chinese_display_name": "API金鑰無效或網路問題",
             "chinese_summary_parenthesized": "（請檢查您的 Google API 金鑰是否正確且有權限訪問模型）",
             "chinese_input_output": "N/A",
             "chinese_suitable_for": "請在左側設定區輸入有效的 API 金鑰。",
             "original_description_from_api": "API Key is invalid or not set. Failed to retrieve models from Google API.",
             "sort_priority": -1 # 最高優先級，確保在列表頂部
            }
        ], status_code=500) # 返回 500 錯誤狀態，表示伺服器端獲取模型失敗

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
async def api_submit_generate_report_task(request_data: GenerateReportRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    logger.info(f"[API_GEN_REPORT] [TASK {task_id}] 收到報告生成請求: 來源='{request_data.source_path}', 模型='{request_data.model_id}'")

    if not global_api_key or not api_key_is_valid:
        logger.warning(f"[API_GEN_REPORT] [TASK {task_id}] API 金鑰無效或未設定。")
        raise HTTPException(status_code=401, detail="無效或未設定的 API 金鑰。請先設定有效的 API 金鑰。")

    if not os.path.exists(request_data.source_path):
        logger.error(f"[API_GEN_REPORT] [TASK {task_id}] 音訊來源檔案不存在: {request_data.source_path}")
        raise HTTPException(status_code=404, detail=f"指定的音訊來源檔案不存在: {os.path.basename(request_data.source_path)}")

    tasks_db[task_id] = {
        "task_id": task_id,
        "status": "queued",
        "source_name": os.path.basename(request_data.source_path),
        "model_id": request_data.model_id,
        "submit_time": datetime.now(timezone.utc).isoformat(),
        "start_time": None,
        "completion_time": None,
        "result_preview_html": None,
        "download_links": None,
        "error_message": None,
        "request_data": request_data.model_dump()
    }
    background_tasks.add_task(process_audio_and_generate_report_task, task_id, request_data)
    logger.info(f"[API_GEN_REPORT] [TASK {task_id}] 任務已加入佇列。")
    return {"task_id": task_id, "message": "報告生成任務已加入佇列。", "status": "queued"}


# --- 任務狀態查詢 API ---
@app.get("/api/tasks")
async def get_all_tasks_status():
    summary_tasks = [{
        "task_id": td["task_id"],
        "status": td["status"],
        "source_name": td["source_name"],
        "model_id": td["model_id"],
        "submit_time": td["submit_time"],
        "error_message": td.get("error_message"),
        "start_time": td.get("start_time"),
        "completion_time": td.get("completion_time"),
        "download_links": td.get("download_links")
    } for td in tasks_db.values()]
    return JSONResponse(content=sorted(summary_tasks, key=lambda x: x["submit_time"], reverse=True))

@app.get("/api/tasks/{task_id}")
async def get_task_status_and_result(task_id: str):
    logger.debug(f"[API_TASK_ID] 請求獲取任務 {task_id} 的詳細狀態。")
    task = tasks_db.get(task_id)
    if not task:
        logger.warning(f"[API_TASK_ID] 找不到任務 ID: {task_id}")
        raise HTTPException(status_code=404, detail="找不到指定的任務 ID。")
    response_data = {
        "task_id": task["task_id"],
        "status": task["status"],
        "source_name": task["source_name"],
        "model_id": task["model_id"],
        "submit_time": task["submit_time"],
        "start_time": task.get("start_time"),
        "completion_time": task.get("completion_time"),
        "error_message": task.get("error_message")
    }
    if task["status"] == "completed":
        response_data["result_preview_html"] = task.get("result_preview_html")
        response_data["download_links"] = task.get("download_links")
    return JSONResponse(content=response_data)


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


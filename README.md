# AI Paper 音訊分析工具

本應用程式能讓您使用 Google Gemini AI 模型分析音訊檔案（來自 YouTube 連結或直接上傳），以生成摘要和逐字稿。

## 在 Google Colab 中快速啟動 (推薦)

在 Google Colab 中執行此應用程式是最簡單快捷的方式，所有資料將儲存在您的 Google Drive 中，方便管理和持續存取。

### 方法一：一鍵複製腳本到 Colab (最推薦)

1.  **點擊下方按鈕**：
    [![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/gist/LaiHao-Alex/9262b3a90b0529900791997bb3f97815/ai_paper_audio_analysis_tool_colab_quick_launcher.ipynb)
2.  **開啟 Colab 筆記本**：點擊按鈕後，腳本將自動在 Google Colab 中開啟一個新的筆記本。
3.  **執行儲存格**：點擊筆記本中第一個儲存格左側的執行按鈕 (▶️) 開始設定。
    *   您需要授權 Google Drive 存取權限。
    *   如果 Colab 「密鑰」中未設定 `GOOGLE_API_KEY`，系統會提示您手動輸入。
4.  **等待應用程式啟動**：腳本執行完畢後，會提供一個公開的 URL (通常結尾是 `.ngrok.io` 或 `loca.lt`)。點擊此 URL 即可開始使用。

**腳本內容預覽：** (以下為 Colab 筆記本中將執行的腳本內容預覽)
```python
#@title AI Paper 音訊分析工具 Colab 快速啟動腳本
#@markdown ---
#@markdown ### 1. 設定與環境準備
#@markdown 此儲存格將會：
#@markdown 1. 掛載您的 Google Drive。
#@markdown 2. 在您的 Google Drive 中建立專案資料夾 (`AI_Paper_Colab_Data`)。
#@markdown 3. 從 GitHub 下載最新的應用程式碼到 Colab 虛擬機。
#@markdown 4. 安裝必要的 Python 套件。
#@markdown 5. 設定環境變數 (包含 API 金鑰和資料夾路徑)。
#@markdown 6. 啟動應用程式並提供公開存取 URL。
#@markdown ---
#@markdown **重要：**
#@markdown - 如果您使用本專案的 **Forked (分支) 版本**，請務必更新下面的 `github_repo_url` 為您自己分支的 URL。
#@markdown - 建議在 Colab 的「密鑰」(Secrets) 中設定 `GOOGLE_API_KEY` (和 `NGROK_AUTHTOKEN`，如果您使用 ngrok)。
#@markdown ---

# 通用設定
# 重要提示：如果您使用的是本儲存庫的 FORK 版本，請將此 URL 更改為您 FORK 的 URL！
github_repo_url = "https://github.com/LaiHao-Alex/AI_paper_audio_analysis.git" #@param {type:"string"}
#@markdown ---
#@markdown ### 2. 執行儲存格
#@markdown 點擊此儲存格左側的執行按鈕 (▶️) 開始設定。
#@markdown 您需要授權 Google Drive 存取權限。
#@markdown 應用程式啟動後，會提供一個 `ngrok.io` 或 `loca.lt` 的公開網址。
#@markdown ---

import os
import sys
import subprocess
from google.colab import drive, output
from IPython.display import display, HTML, Javascript
import threading
import time
import re

# --- 輔助函數 ---
def print_status(message):
    print(f"[*] {message}")

def print_success(message):
    print(f"[成功] {message}")

def print_error(message):
    print(f"[錯誤] {message}")
    # 在 Colab 環境中，sys.exit(1) 可能會導致 Kernel Restart，這裡選擇僅打印錯誤並繼續，讓使用者知曉
    # sys.exit(1) # 如果希望嚴格終止，可以取消註解此行

def run_command(command, description, check=True, capture_output=True):
    print_status(f"執行中: {description}...")
    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE if capture_output else None, stderr=subprocess.PIPE if capture_output else None, text=True)
        stdout, stderr = process.communicate()
        if process.returncode != 0 and check:
            error_message = f"{description} 失敗。"
            if capture_output:
                 error_message += f"\n標準輸出:\n{stdout}\n標準錯誤:\n{stderr}"
            print_error(error_message)
            if check: # 如果 check 為 True，則在此處停止執行後續命令
                 raise subprocess.CalledProcessError(process.returncode, command)
        elif process.returncode != 0 and capture_output:
             print(f"[警告] {description} 可能有非致命錯誤。\n標準輸出:\n{stdout}\n標準錯誤:\n{stderr}")
        else:
            print_success(f"{description} 完成。")
        return stdout, stderr
    except subprocess.CalledProcessError as e:
        # 如果 run_command 設定為 check=True，則異常會在這裡被捕獲並重新拋出，終止腳本的主要流程
        raise e
    except Exception as e:
        print_error(f"執行 '{description}' 時發生例外: {e}")
        if check: # 如果 check 為 True，也重新拋出異常
            raise e


# --- Google Drive 掛載與資料夾設定 ---
try:
    print_status("正在掛載 Google Drive...")
    drive.mount('/content/drive', force_remount=True)

    google_drive_project_root = "/content/drive/MyDrive/AI_Paper_Colab_Data"
    temp_audio_storage_dir_drive = os.path.join(google_drive_project_root, "temp_audio")
    generated_reports_dir_drive = os.path.join(google_drive_project_root, "generated_reports")
    app_code_dir_colab = "/content/app_code" # Colab 虛擬機中應用程式碼的克隆位置

    print_status(f"在 Google Drive 中建立資料夾 (如果不存在):")
    print_status(f"  - 專案根目錄: {google_drive_project_root}")
    os.makedirs(google_drive_project_root, exist_ok=True)
    print_status(f"  - 臨時音訊儲存目錄: {temp_audio_storage_dir_drive}")
    os.makedirs(temp_audio_storage_dir_drive, exist_ok=True)
    print_status(f"  - 生成報告儲存目錄: {generated_reports_dir_drive}")
    os.makedirs(generated_reports_dir_drive, exist_ok=True)
    print_success("Google Drive 資料夾結構設定完成。")

    # --- 應用程式碼克隆/更新 ---
    if os.path.exists(app_code_dir_colab):
        print_status(f"應用程式碼目錄 '{app_code_dir_colab}' 已存在，先移除舊版本...")
        run_command(f"rm -rf {app_code_dir_colab}", "移除舊的應用程式碼目錄")

    print_status(f"從 GitHub ({github_repo_url}) 下載最新的應用程式碼到 Colab 虛擬機 ({app_code_dir_colab})...")
    run_command(f"git clone --depth 1 {github_repo_url} {app_code_dir_colab}", "下載應用程式碼") # 使用 --depth 1 進行淺克隆

    project_root_colab = app_code_dir_colab
    os.chdir(project_root_colab)
    print_success(f"已將工作目錄變更至: {os.getcwd()}")

    # --- 安裝依賴 ---
    requirements_path = os.path.join(project_root_colab, "requirements.txt")
    if not os.path.exists(requirements_path):
        print_error(f"找不到 'requirements.txt' 檔案於: {requirements_path}")
        raise FileNotFoundError(f"找不到 'requirements.txt' 檔案於: {requirements_path}")
    run_command(f"{sys.executable} -m pip install --upgrade pip", "升級 pip")
    run_command(f"{sys.executable} -m pip install -r {requirements_path}", "安裝 Python 套件")

    # --- API 金鑰設定 ---
    print_status("正在設定 Google API 金鑰...")
    google_api_key = ""
    ngrok_auth_token = ""
    try:
        from google.colab import userdata
        google_api_key = userdata.get('GOOGLE_API_KEY')
        ngrok_auth_token = userdata.get('NGROK_AUTHTOKEN') # 也嘗試讀取 ngrok token
        if google_api_key:
            print_success("成功從 Colab Secrets 讀取 GOOGLE_API_KEY。")
        else:
            print_status("Colab Secrets 中未找到 GOOGLE_API_KEY，稍後將提示手動輸入。")
        if ngrok_auth_token:
            print_success("成功從 Colab Secrets 讀取 NGROK_AUTHTOKEN。")
        else:
            print_status("Colab Secrets 中未找到 NGROK_AUTHTOKEN。如果您計劃使用 ngrok 且有 token，建議設定。")

    except ImportError:
        print_status("無法導入 google.colab.userdata (可能為舊版 Colab)，將提示手動輸入金鑰。")
    except Exception as e:
        print_status(f"從 Colab Secrets 讀取金鑰時發生錯誤: {e}。將提示手動輸入。")

    if not google_api_key:
        print_status("請手動輸入您的 Google Gemini API 金鑰:")
        google_api_key = input()
        if google_api_key:
            print_success("已接收手動輸入的 API 金鑰。")
        else:
            print_error("未提供 API 金鑰，應用程式可能無法正常運作。")
            # 在此處可以選擇是否要強制停止，或者讓應用程式嘗試啟動（可能會失敗）
            # raise ValueError("未提供 API 金鑰")

    os.environ['GOOGLE_API_KEY'] = google_api_key
    os.environ['APP_TEMP_AUDIO_STORAGE_DIR'] = temp_audio_storage_dir_drive
    os.environ['APP_GENERATED_REPORTS_DIR'] = generated_reports_dir_drive
    # 如果 app.py 需要知道它在 Colab 環境中運行
    os.environ['RUNNING_IN_COLAB'] = 'true'


    print_success(f"環境變數設定完成。")
    print_status(f"  - GOOGLE_API_KEY: {'已設定 (長度: ' + str(len(google_api_key)) + ')' if google_api_key else '未設定'}")
    print_status(f"  - APP_TEMP_AUDIO_STORAGE_DIR: {os.environ['APP_TEMP_AUDIO_STORAGE_DIR']}")
    print_status(f"  - APP_GENERATED_REPORTS_DIR: {os.environ['APP_GENERATED_REPORTS_DIR']}")

    # --- 啟動伺服器 ---
    print_status("正在準備啟動 FastAPI 應用程式...")
    app_file_path = os.path.join(project_root_colab, "src", "app.py") # 確認路徑正確
    if not os.path.exists(app_file_path):
        print_error(f"找不到應用程式主檔案 'src/app.py' 於: {project_root_colab}")
        raise FileNotFoundError(f"找不到應用程式主檔案 'src/app.py' 於: {project_root_colab}")

    # 使用 threading 管理 ngrok/localtunnel 和 Uvicorn
    def run_uvicorn():
        print_status("正在啟動 Uvicorn 伺服器...")
        # 確保 Uvicorn 從 project_root_colab 運行，以便 src.app 可以被正確找到
        # 使用 sys.executable 確保使用的是 Colab 環境中的 Python 解釋器
        uvicorn_command = [
            sys.executable, "-m", "uvicorn",
            "src.app:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--workers", "1"
        ]
        # run_command(uvicorn_command, "啟動 Uvicorn", check=False, capture_output=False) # check=False 因為它是阻塞調用, capture_output=False 讓日誌直接輸出
        # 改為直接 Popen 以更好地控制日誌輸出和錯誤處理
        process = subprocess.Popen(uvicorn_command, stdout=sys.stdout, stderr=sys.stderr, cwd=project_root_colab)
        process.wait() # 等待 Uvicorn 結束

    uvicorn_thread = threading.Thread(target=run_uvicorn)
    uvicorn_thread.daemon = True # 允許主程式退出，即使線程正在運行
    uvicorn_thread.start()
    print_status("Uvicorn 伺服器應已在背景執行緒中啟動。")

    # --- 設定公開 URL (優先使用 ngrok，若失敗則嘗試 localtunnel) ---
    print_status("正在設定公開存取 URL...")
    time.sleep(5) # 給 Uvicorn 一點啟動時間

    public_url = ""
    # Ngrok 設定
    try:
        print_status("嘗試使用 ngrok 建立通道...")
        run_command(f"{sys.executable} -m pip install pyngrok", "安裝/更新 pyngrok")
        from pyngrok import ngrok, conf

        if ngrok_auth_token:
            print_status("使用 Colab Secrets 中的 NGROK_AUTHTOKEN 設定 ngrok。")
            conf.get_default().auth_token = ngrok_auth_token
        else:
            print_status("未在 Colab Secrets 中找到 NGROK_AUTHTOKEN。如果您有 ngrok 帳戶，建議設定以獲得更穩定的服務。")
            # 可以選擇在這裡提示用戶輸入 ngrok token
            # ngrok_token_manual = input("如果您有 ngrok Authtoken，請在此輸入 (否則請留空): ")
            # if ngrok_token_manual:
            #     conf.get_default().auth_token = ngrok_token_manual

        public_url = ngrok.connect(8000)
        print_success(f"Ngrok 通道已建立！")
    except Exception as e_ngrok:
        print_status(f"Ngrok 設定失敗: {e_ngrok}")
        print_status("嘗試備選方案 localtunnel...")
        try:
            # Localtunnel 通常需要全局安裝，如果 Colab 環境限制，可能會有問題
            run_command("npm install -g localtunnel", "安裝 localtunnel (如果尚未安裝)")
            # 使用 Popen 啟動 localtunnel 並捕獲其輸出以獲取 URL
            localtunnel_process = subprocess.Popen(
                f"lt --port 8000", # 可以嘗試添加 --print-requests 來查看更多日誌
                shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True
            )
            # 等待 localtunnel 輸出其 URL，這可能需要幾秒鐘
            # 實時讀取 stdout 來找到 URL
            lt_url_found = False
            for i in range(20): # 嘗試讀取最多 20 秒
                line = localtunnel_process.stdout.readline()
                if line:
                    print_status(f"Localtunnel output: {line.strip()}") # 打印原始輸出以供調試
                    url_match = re.search(r"your url is: (https?://[^\s]+)", line)
                    if url_match:
                        public_url = url_match.group(1)
                        print_success(f"Localtunnel 通道已建立！")
                        lt_url_found = True
                        break
                time.sleep(1)

            if not lt_url_found:
                print_error(f"無法從 localtunnel 輸出中提取 URL。請檢查 localtunnel 是否正確啟動。")
                stdout, stderr = localtunnel_process.communicate() # 獲取剩餘輸出
                if stdout: print_status(f"Localtunnel STDOUT:\n{stdout}")
                if stderr: print_error(f"Localtunnel STDERR:\n{stderr}")
                public_url = "無法建立通道，請檢查上方錯誤訊息。"

        except Exception as e_lt:
            print_error(f"Localtunnel 設定失敗: {e_lt}")
            public_url = "Ngrok 和 Localtunnel 皆設定失敗。"

    print("\n" + "="*50)
    if public_url and "http" in public_url:
        print_success(f"🚀 應用程式應該已經啟動！")
        print(f"🔗 公開存取網址 (Public URL): {public_url}")
        display(HTML(f"<p>點擊此連結開啟應用程式：<a href='{public_url}' target='_blank'>{public_url}</a></p>"))
    else:
        print_error(f"無法生成公開網址。請檢查日誌。")
        display(HTML(f"<p style='color:red;'>無法生成公開網址，請檢查日誌。</p>"))

    print(f"📁 您的資料將會儲存在 Google Drive 的這個位置: {google_drive_project_root}")
    print(f"🕒 您需要保持此 Colab 儲存格持續執行以使用應用程式。")
    print(f"💡 如果遇到問題，請檢查上方儲存格的輸出訊息。")
    print("="*50 + "\n")

    # 保持儲存格運行（可選，因為背景線程可能會使其保持活動狀態）
    # try:
    #     while True:
    #         time.sleep(3600) # 保持活動，偶爾打印狀態
    #         print_status(f"應用程式仍在運行中... 公開網址: {public_url}")
    # except KeyboardInterrupt:
    #     print_status("Colab 執行被使用者中斷。正在關閉...")
    #     if 'ngrok' in sys.modules and public_url and "ngrok.io" in public_url.address:
    #         ngrok.disconnect(public_url.public_url) # 確保傳遞正確的 URL 字符串
    #         ngrok.kill()
    #     # 如何關閉 localtunnel 取決於它是如何啟動的，如果用 Popen，可以嘗試 terminate()
    #     if 'localtunnel_process' in locals() and localtunnel_process.poll() is None:
    #         localtunnel_process.terminate()
    #     print_success("清理完成。")

except Exception as main_exception:
    print_error(f"腳本執行過程中發生未處理的錯誤: {main_exception}")
    # 可以在這裡添加更詳細的錯誤記錄或清理步驟

# 此處的註釋是為了防止 Colab 在腳本結束後自動斷開連接（如果沒有長時間運行的進程）
# 如果 uvicorn_thread.daemon = False，則此儲存格將保持活動狀態直到 Uvicorn 停止或被中斷
# 如果 uvicorn_thread.daemon = True，則主腳本執行完畢後，如果沒有其他前台任務，儲存格可能很快結束
# Ngrok/Localtunnel 的線程或進程是否能保持 Colab 活動取決於 Colab 的策略
# 通常，只要有正在運行的輸出或活動的網絡連接，Colab 會保持運行
# print_status("Colab 腳本主要部分執行完畢。應用程式和通道應在背景運行。")
```

### 方法二：上傳專案壓縮檔到 Colab

1.  **下載專案**：
    *   您可以前往本專案的 GitHub 頁面，點擊 "Code" 按鈕，然後選擇 "Download ZIP"，或者 [直接點擊這裡下載 ZIP 壓縮檔](https://github.com/LaiHao-Alex/AI_paper_audio_analysis/archive/refs/heads/main.zip)。
    *   將下載的 ZIP 檔案儲存到您的電腦。
2.  **開啟 Google Colab 並建立新筆記本**：
    *   前往 [Google Colab](https://colab.research.google.com/)。
    *   點擊 "File" -> "New notebook" 來建立一個新的 Colab 筆記本。
3.  **準備 Colab 環境**：
    *   在新 Colab 筆記本的第一個儲存格中，貼上下列腳本。
    *   執行此儲存格以上傳您的專案 ZIP 檔案並設定環境。
4.  **上傳 ZIP 檔案**：執行腳本後，會出現一個上傳按鈕。點擊它並選擇您之前下載的專案 ZIP 檔案。
5.  **等待設定完成**：腳本會自動解壓縮檔案、安裝依賴套件並啟動應用程式。
6.  **取得公開 URL**：完成後，輸出末尾會提供一個公開 URL。

**Colab 設定腳本：**
```python
#@title AI Paper 音訊分析工具 Colab 上傳啟動器
#@markdown ---
#@markdown ### 1. 環境準備與檔案上傳
#@markdown 此儲存格將會：
#@markdown 1. 掛載您的 Google Drive（可選，但建議用於資料持久化）。
#@markdown 2. 提示您上傳專案的 ZIP 檔案。
#@markdown 3. 解壓縮 ZIP 檔案。
#@markdown 4. 安裝必要的 Python 套件。
#@markdown 5. 設定環境變數（包含 API 金鑰和資料夾路徑）。
#@markdown 6. 啟動應用程式並提供公開存取 URL。
#@markdown ---
#@markdown **重要：**
#@markdown - 請先從 GitHub 下載本專案的 ZIP 壓縮檔。
#@markdown - 建議在 Colab 的「密鑰」(Secrets) 中設定 `GOOGLE_API_KEY` (和 `NGROK_AUTHTOKEN`，如果您使用 ngrok)。
#@markdown ---
#@markdown ### 2. 執行儲存格
#@markdown 點擊此儲存格左側的執行按鈕 (▶️) 開始。
#@markdown 您會被引導上傳 ZIP 檔案並可能需要授權 Google Drive。
#@markdown ---

import os
import sys
import subprocess
from google.colab import drive, files, output
from IPython.display import display, HTML
import threading
import time
import re
import zipfile
import shutil # 用於刪除目錄樹

# --- 輔助函數 ---
def print_status(message):
    print(f"[*] {message}")

def print_success(message):
    print(f"[成功] {message}")

def print_error(message):
    print(f"[錯誤] {message}")
    # sys.exit(1) # 避免 Kernel Restart

def run_command(command, description, check=True, capture_output=True):
    print_status(f"執行中: {description}...")
    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE if capture_output else None, stderr=subprocess.PIPE if capture_output else None, text=True)
        stdout, stderr = process.communicate()
        if process.returncode != 0 and check:
            error_message = f"{description} 失敗。"
            if capture_output:
                 error_message += f"\n標準輸出:\n{stdout}\n標準錯誤:\n{stderr}"
            print_error(error_message)
            if check: raise subprocess.CalledProcessError(process.returncode, command)
        elif process.returncode != 0 and capture_output:
             print(f"[警告] {description} 可能有非致命錯誤。\n標準輸出:\n{stdout}\n標準錯誤:\n{stderr}")
        else:
            print_success(f"{description} 完成。")
        return stdout, stderr
    except subprocess.CalledProcessError as e:
        raise e
    except Exception as e:
        print_error(f"執行 '{description}' 時發生例外: {e}")
        if check: raise e

# --- Google Drive 掛載 (可選但建議) ---
mount_google_drive = True #@param {type:"boolean"}
google_drive_project_root = "/content/drive/MyDrive/AI_Paper_Colab_Uploaded_Data" #@param {type:"string"}

if mount_google_drive:
    try:
        print_status("正在掛載 Google Drive...")
        drive.mount('/content/drive', force_remount=True)
        temp_audio_storage_dir_final = os.path.join(google_drive_project_root, "temp_audio")
        generated_reports_dir_final = os.path.join(google_drive_project_root, "generated_reports")

        print_status(f"在 Google Drive 中建立資料夾 (如果不存在):")
        print_status(f"  - 專案根目錄: {google_drive_project_root}")
        os.makedirs(google_drive_project_root, exist_ok=True)
        print_status(f"  - 臨時音訊儲存目錄: {temp_audio_storage_dir_final}")
        os.makedirs(temp_audio_storage_dir_final, exist_ok=True)
        print_status(f"  - 生成報告儲存目錄: {generated_reports_dir_final}")
        os.makedirs(generated_reports_dir_final, exist_ok=True)
        print_success("Google Drive 資料夾結構設定完成。")
        os.environ['APP_TEMP_AUDIO_STORAGE_DIR'] = temp_audio_storage_dir_final
        os.environ['APP_GENERATED_REPORTS_DIR'] = generated_reports_dir_final
    except Exception as e:
        print_error(f"Google Drive 掛載或資料夾建立失敗: {e}。資料將不會儲存在 Drive 中。")
        os.environ['APP_TEMP_AUDIO_STORAGE_DIR'] = "/content/temp_audio_local"
        os.environ['APP_GENERATED_REPORTS_DIR'] = "/content/generated_reports_local"
        os.makedirs(os.environ['APP_TEMP_AUDIO_STORAGE_DIR'], exist_ok=True)
        os.makedirs(os.environ['APP_GENERATED_REPORTS_DIR'], exist_ok=True)
else:
    print_status("未選擇掛載 Google Drive。資料將儲存在 Colab 臨時儲存空間中。")
    # 如果不使用 Google Drive，設定本地路徑
    os.environ['APP_TEMP_AUDIO_STORAGE_DIR'] = "/content/temp_audio_local"
    os.environ['APP_GENERATED_REPORTS_DIR'] = "/content/generated_reports_local"
    os.makedirs(os.environ['APP_TEMP_AUDIO_STORAGE_DIR'], exist_ok=True)
    os.makedirs(os.environ['APP_GENERATED_REPORTS_DIR'], exist_ok=True)


# --- 上傳專案 ZIP 檔案 ---
app_code_dir_colab = "/content/app_code"
if os.path.exists(app_code_dir_colab):
    print_status(f"舊的應用程式碼目錄 '{app_code_dir_colab}' 已存在，將其移除...")
    shutil.rmtree(app_code_dir_colab) # 使用 shutil.rmtree 刪除目錄及其內容
os.makedirs(app_code_dir_colab, exist_ok=True)

print_status("請上傳您的專案 ZIP 檔案。")
uploaded = files.upload()

if not uploaded:
    print_error("未上傳任何檔案。請重新執行此儲存格並上傳 ZIP 檔案。")
    raise ValueError("未上傳 ZIP 檔案")

zip_filename = list(uploaded.keys())[0]
zip_filepath = os.path.join("/content", zip_filename) # files.upload() 將檔案儲存在 /content/

print_status(f"正在解壓縮 '{zip_filename}' 到 '{app_code_dir_colab}'...")
try:
    with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
        zip_ref.extractall(app_code_dir_colab)
    print_success(f"檔案解壓縮完成。")

    # 檢查解壓縮後是否產生了額外的頂層目錄（常見情況）
    # 例如，如果 ZIP 內容是 project-main/src/...，解壓後會是 app_code/project-main/src
    extracted_items = os.listdir(app_code_dir_colab)
    if len(extracted_items) == 1 and os.path.isdir(os.path.join(app_code_dir_colab, extracted_items[0])):
        # 如果只有一個子目錄，則假設這是專案的實際根目錄
        project_actual_root = os.path.join(app_code_dir_colab, extracted_items[0])
        print_status(f"檢測到專案檔案位於子目錄 '{extracted_items[0]}' 中。調整專案根目錄...")
        # 將子目錄中的所有內容移動到 app_code_dir_colab
        for item_name in os.listdir(project_actual_root):
            shutil.move(os.path.join(project_actual_root, item_name), app_code_dir_colab)
        os.rmdir(project_actual_root) # 移除現在為空的子目錄
        print_success(f"專案根目錄已調整至 '{app_code_dir_colab}'。")

except zipfile.BadZipFile:
    print_error(f"檔案 '{zip_filename}' 不是一個有效的 ZIP 檔案。")
    raise
except Exception as e:
    print_error(f"解壓縮檔案時發生錯誤: {e}")
    raise

# --- 設定工作目錄並安裝依賴 ---
project_root_colab = app_code_dir_colab
os.chdir(project_root_colab)
print_success(f"已將工作目錄變更至: {os.getcwd()}")

requirements_path = os.path.join(project_root_colab, "requirements.txt")
if not os.path.exists(requirements_path):
    print_error(f"找不到 'requirements.txt' 檔案於: {requirements_path}。請確認 ZIP 檔案包含此檔案於根目錄。")
    raise FileNotFoundError(f"找不到 'requirements.txt' 檔案於: {requirements_path}")

try:
    run_command(f"{sys.executable} -m pip install --upgrade pip", "升級 pip")
    run_command(f"{sys.executable} -m pip install -r {requirements_path}", "安裝 Python 套件")

    # --- API 金鑰設定 ---
    print_status("正在設定 Google API 金鑰...")
    google_api_key = ""
    ngrok_auth_token = ""
    try:
        from google.colab import userdata
        google_api_key = userdata.get('GOOGLE_API_KEY')
        ngrok_auth_token = userdata.get('NGROK_AUTHTOKEN')
        if google_api_key: print_success("成功從 Colab Secrets 讀取 GOOGLE_API_KEY。")
        else: print_status("Colab Secrets 中未找到 GOOGLE_API_KEY，稍後將提示手動輸入。")
        if ngrok_auth_token: print_success("成功從 Colab Secrets 讀取 NGROK_AUTHTOKEN。")
        else: print_status("Colab Secrets 中未找到 NGROK_AUTHTOKEN。")
    except ImportError: print_status("無法導入 google.colab.userdata，將提示手動輸入金鑰。")
    except Exception as e: print_status(f"從 Colab Secrets 讀取金鑰時發生錯誤: {e}。")

    if not google_api_key:
        print_status("請手動輸入您的 Google Gemini API 金鑰:")
        google_api_key = input()
        if not google_api_key:
            print_error("未提供 API 金鑰。")
            raise ValueError("未提供 API 金鑰")
        print_success("已接收手動輸入的 API 金鑰。")

    os.environ['GOOGLE_API_KEY'] = google_api_key
    os.environ['RUNNING_IN_COLAB'] = 'true' # 標識為 Colab 環境

    print_success(f"環境變數設定完成。")
    print_status(f"  - GOOGLE_API_KEY: {'已設定' if google_api_key else '未設定'}")
    print_status(f"  - APP_TEMP_AUDIO_STORAGE_DIR: {os.environ['APP_TEMP_AUDIO_STORAGE_DIR']}")
    print_status(f"  - APP_GENERATED_REPORTS_DIR: {os.environ['APP_GENERATED_REPORTS_DIR']}")


    # --- 啟動伺服器 ---
    print_status("正在準備啟動 FastAPI 應用程式...")
    # 假設 app.py 位於 src 目錄下
    app_file_path = os.path.join(project_root_colab, "src", "app.py")
    if not os.path.exists(app_file_path):
        # 如果 src/app.py 不存在，嘗試尋找根目錄下的 app.py
        app_file_path_root = os.path.join(project_root_colab, "app.py")
        if os.path.exists(app_file_path_root):
            app_module = "app:app" # 主應用程式實例在 app.py 中
            print_status("在專案根目錄下找到 'app.py'。")
        else:
            print_error(f"找不到應用程式主檔案 (已嘗試 'src/app.py' 和 'app.py') 於: {project_root_colab}")
            raise FileNotFoundError(f"找不到應用程式主檔案於: {project_root_colab}")
    else:
        app_module = "src.app:app" # 主應用程式實例在 src/app.py 中
        print_status("在 'src' 目錄下找到 'app.py'。")


    def run_uvicorn_uploaded(): # 避免與第一個腳本中的函數名衝突
        print_status("正在啟動 Uvicorn 伺服器...")
        uvicorn_command = [
            sys.executable, "-m", "uvicorn",
            app_module, # 使用檢測到的模塊路徑
            "--host", "0.0.0.0",
            "--port", "8000",
            "--workers", "1"
        ]
        process = subprocess.Popen(uvicorn_command, stdout=sys.stdout, stderr=sys.stderr, cwd=project_root_colab)
        process.wait()

    uvicorn_thread_uploaded = threading.Thread(target=run_uvicorn_uploaded)
    uvicorn_thread_uploaded.daemon = True
    uvicorn_thread_uploaded.start()
    print_status("Uvicorn 伺服器應已在背景執行緒中啟動。")

    # --- 設定公開 URL ---
    print_status("正在設定公開存取 URL...")
    time.sleep(5) # 等待 Uvicorn 啟動
    public_url_uploaded = "" # 避免命名衝突
    try:
        print_status("嘗試使用 ngrok 建立通道...")
        run_command(f"{sys.executable} -m pip install pyngrok", "安裝/更新 pyngrok")
        from pyngrok import ngrok, conf
        if ngrok_auth_token:
            conf.get_default().auth_token = ngrok_auth_token
        public_url_uploaded = ngrok.connect(8000)
        print_success(f"Ngrok 通道已建立！")
    except Exception as e_ngrok_uploaded:
        print_status(f"Ngrok 設定失敗: {e_ngrok_uploaded}")
        print_status("嘗試備選方案 localtunnel...")
        try:
            run_command("npm install -g localtunnel", "安裝 localtunnel")
            localtunnel_process_uploaded = subprocess.Popen(
                f"lt --port 8000", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True
            )
            lt_url_found_uploaded = False
            for i in range(20):
                line = localtunnel_process_uploaded.stdout.readline()
                if line:
                    print_status(f"Localtunnel output: {line.strip()}")
                    url_match = re.search(r"your url is: (https?://[^\s]+)", line)
                    if url_match:
                        public_url_uploaded = url_match.group(1)
                        print_success(f"Localtunnel 通道已建立！")
                        lt_url_found_uploaded = True
                        break
                time.sleep(1)
            if not lt_url_found_uploaded:
                print_error("無法從 localtunnel 輸出中提取 URL。")
                public_url_uploaded = "Localtunnel 提取 URL 失敗"
        except Exception as e_lt_uploaded:
            print_error(f"Localtunnel 設定失敗: {e_lt_uploaded}")
            public_url_uploaded = "Ngrok 和 Localtunnel 皆設定失敗。"

    print("\n" + "="*50)
    if public_url_uploaded and "http" in public_url_uploaded:
        print_success(f"🚀 應用程式應該已經啟動！")
        print(f"🔗 公開存取網址 (Public URL): {public_url_uploaded}")
        display(HTML(f"<p>點擊此連結開啟應用程式：<a href='{public_url_uploaded}' target='_blank'>{public_url_uploaded}</a></p>"))
    else:
        print_error(f"無法生成公開網址。請檢查日誌。")
        display(HTML(f"<p style='color:red;'>無法生成公開網址，請檢查日誌。</p>"))

    if mount_google_drive and os.environ.get('APP_GENERATED_REPORTS_DIR', '').startswith("/content/drive"):
         print(f"📁 您的資料將會儲存在 Google Drive 的這個位置: {os.environ['APP_GENERATED_REPORTS_DIR']}")
    else:
        print(f"📁 您的資料將會儲存在 Colab 臨時目錄: {os.environ['APP_GENERATED_REPORTS_DIR']}")
    print(f"🕒 您需要保持此 Colab 儲存格持續執行以使用應用程式。")
    print("="*50 + "\n")

except Exception as main_exception_uploaded:
    print_error(f"腳本執行過程中發生未處理的錯誤: {main_exception_uploaded}")
finally:
    # 清理上傳的 ZIP 檔案
    if 'zip_filepath' in locals() and os.path.exists(zip_filepath):
        print_status(f"正在刪除已上傳的 ZIP 檔案 '{zip_filename}'...")
        os.remove(zip_filepath)
        print_success("已刪除 ZIP 檔案。")
```

<details>
<summary><h2>本地開發/進階使用者指南 (點擊展開)</h2></summary>

### 先決條件

*   您的系統已安裝 Python 3.7+。
*   可以存取終端機或命令提示字元。
*   Google Gemini API 金鑰。您可以從 [Google AI Studio](https://aistudio.google.com/app/apikey) 獲取。

### 本地安裝與執行

本節結合了通用安裝步驟以及如何在您的本機電腦上直接執行應用程式的說明。

1.  **下載或複製專案**：
    *   從 GitHub 下載專案 ZIP 檔案並解壓縮，或使用 `git clone https://github.com/LaiHao-Alex/AI_paper_audio_analysis.git` 複製本倉庫。
    *   您應該會有一個包含 `src/` 目錄、`requirements.txt` 等檔案的專案根目錄。

2.  **導航到專案根目錄**：
    *   開啟您的終端機或命令提示字元。
    *   切換到專案根目錄：
        ```bash
        cd path/to/your/project-root
        ```

3.  **安裝依賴套件**：
    *   建議先建立並啟用虛擬環境：
        ```bash
        python -m venv venv
        # Windows:
        # venv\Scripts\activate
        # macOS/Linux:
        # source venv/bin/activate
        ```
    *   使用 pip 和 `requirements.txt` 檔案安裝必要的 Python 套件：
        ```bash
        pip install -r requirements.txt
        ```

4.  **設定 Google API 金鑰 (建議方式：環境變數)**：
    *   本應用程式需要 Google Gemini API 金鑰。
    *   **在啟動應用程式之前**，建議將您的 API 金鑰設定為名為 `GOOGLE_API_KEY` 的環境變數。
        *   在 Linux/macOS 上 (將指令加到 `~/.bashrc` 或 `~/.zshrc` 中使其永久生效)：
            ```bash
            export GOOGLE_API_KEY="YOUR_API_KEY_HERE"
            ```
        *   在 Windows (命令提示字元) 上 (使用 `setx` 使其永久生效，或每次啟動時設定)：
            ```bash
            set GOOGLE_API_KEY="YOUR_API_KEY_HERE"
            ```
        *   在 Windows (PowerShell) 上 (若要永久設定，請查詢 PowerShell Profile 設定)：
            ```powershell
            $env:GOOGLE_API_KEY="YOUR_API_KEY_HERE"
            ```
        *   請將 `"YOUR_API_KEY_HERE"` 替換為您實際的 API 金鑰。
        *   應用程式 (`src/app.py`) 將在啟動時嘗試讀取此環境變數。
    *   或者，您可以在應用程式啟動後，透過網頁介面上的「API 金鑰設定」部分臨時輸入金鑰。

5.  **啟動伺服器**：
    *   使用 Uvicorn 執行應用程式。應用程式實例 `app` 位於 `src/app.py`。
        ```bash
        uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
        ```
    *   `--reload` 參數對開發很有用，因為它會在偵測到程式碼變更時自動重新載入伺服器。對於生產環境，請移除此參數。
    *   您應該會看到指示伺服器正在運行的輸出，通常在 `http://0.0.0.0:8000`。

6.  **在瀏覽器中存取**：
    *   開啟您的網頁瀏覽器並前往 `http://localhost:8000`。

### 檔案結構

應用程式的核心程式碼和設定應大致遵循以下結構：

```
your-project-root/
├── src/
│   ├── app.py               # FastAPI 應用程式主檔案
│   ├── static/              # 靜態資源 (CSS, JavaScript)
│   │   ├── main.js
│   │   └── style.css
│   └── templates/           # HTML 模板
│       └── index.html
├── requirements.txt         # Python 依賴套件列表
├── README.md                # 本說明檔案
├── .env.example             # (可選) 環境變數範本檔案, 可複製為 .env 並填入您的設定
├── temp_audio/              # 由 app.py 自動創建，用於臨時音訊儲存
└── generated_reports/       # 由 app.py 自動創建，用於儲存生成的報告
```
*註：`your_colab_launcher.ipynb` 檔案並非專案核心部分，僅為 Colab 使用者提供便利。*

**資料儲存目錄說明**：

*   **`temp_audio/`**：用於儲存臨時下載或上傳的音訊檔案。
*   **`generated_reports/`**：用於儲存生成的分析報告。

**對於本地執行**：
*   這些目錄 (`temp_audio/`, `generated_reports/`) 通常會在專案根目錄下由應用程式自動創建 (如果它們不存在)。
*   您可以透過設定 `APP_TEMP_AUDIO_STORAGE_DIR` 和 `APP_GENERATED_REPORTS_DIR` 環境變數來自訂這些目錄的路徑 (例如，在 `.env` 檔案中設定)。

**對於 Google Colab (使用上述啟動腳本)**：
*   啟動腳本會將這些資料夾 (`temp_audio/` 和 `generated_reports/`) 建立在您的 Google Drive 中的 `AI_Paper_Colab_Data` (方法一) 或 `AI_Paper_Colab_Uploaded_Data` (方法二，如果選擇掛載 Drive) 目錄下。
*   腳本會自動設定相應的環境變數，讓應用程式使用這些位於 Google Drive 的路徑。這確保了即使 Colab 執行階段結束，您的資料也會被保留。

</details>

## 使用應用程式

(本節說明在伺服器運行後與網頁 UI 互動的方式，無論是在本地還是透過 Colab)

1.  **API 金鑰設定**：
    *   如果應用程式啟動時未能從環境變數 (`GOOGLE_API_KEY`) 中讀取到有效的 Google Gemini API 金鑰，或者您希望在當前工作階段使用不同的金鑰，您可以在網頁介面的「API 金鑰設定」區域輸入或更新您的金鑰。
    *   **注意**：透過此介面設定的金鑰僅在當前瀏覽器工作階段有效，並儲存在瀏覽器的 `localStorage` 中。關閉瀏覽器分頁或清除瀏覽器資料可能會導致金鑰遺失。為持久化設定，建議使用環境變數。

2.  **提供音訊來源**：
    *   **YouTube 網址**：選擇「YouTube 網址」分頁，在輸入框中貼上完整的 YouTube 影片 URL，然後點擊「提交來源並繼續」。系統將嘗試從 YouTube 下載音訊。
    *   **上傳音訊檔案**：選擇「上傳音訊檔案」分頁，點擊「選擇音訊檔案...」按鈕，從您的電腦選擇一個支援的音訊檔案（例如：`.mp3`, `.wav`, `.ogg`, `.m4a` 等），然後點擊「提交來源並繼續」。檔案將上傳到伺服器進行處理。

3.  **設定分析選項**：
    *   音訊來源成功提交並處理後（如下載或儲存完畢），「設定分析選項」區域將會啟用。
    *   **選擇 AI 模型**：從下拉式選單中選擇您希望用於分析的 Gemini 模型 (例如 `gemini-1.5-flash-latest`, `gemini-1.5-pro-latest`, `gemini-1.0-pro` 等)。不同模型可能影響分析速度、品質和成本。
    *   **選擇輸出內容**：
        *   `僅摘要`：只生成音訊內容的摘要。
        *   `僅逐字稿`：只生成音訊內容的文字逐字稿。
        *   `摘要和逐字稿`：同時生成摘要和逐字稿。
    *   **額外下載格式 (選填)**：
        *   除了在網頁上預覽結果和下載 HTML 格式的報告外，您可以勾選希望額外生成的檔案格式：
            *   `Markdown (.md)`：生成 Markdown 格式的報告。
            *   `純文字 (.txt)`：生成純文字格式的報告。
    *   **自訂提示詞 (選填)**：
        *   您可以為「摘要生成」和「逐字稿生成」指定自訂的系統指令或使用者提示詞。留空則使用應用程式內建的預設提示詞。
        *   **摘要提示詞範例**：`請為這段音訊內容生成一個簡潔的摘要，包含主要觀點和結論。`
        *   **逐字稿提示詞範例**：`請將音訊內容準確地轉換為文字，注意區分不同的發言者（如果可能）。`

4.  **開始分析**：
    *   完成所有設定後，點擊「開始分析」按鈕。
    *   您的請求將被加入到「即時任務佇列」中。佇列系統允許應用程式依序處理多個請求。

5.  **查看與下載結果**：
    *   分析任務完成後，結果將顯示在「分析結果」區域。
    *   您可以直接在網頁上預覽生成的摘要和/或逐字稿。
    *   點擊提供的下載連結（例如「下載 HTML 報告」，或您選擇的 Markdown/純文字檔案連結）即可將報告儲存到您的電腦。
    *   如果啟用了 Google Drive 儲存（在 Colab 環境中），報告也會自動儲存到您 Drive 中指定的 `generated_reports` 資料夾內。

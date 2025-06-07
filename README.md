<!-- CHINESE VERSION -->

```markdown
# AI Paper 音訊分析工具

本應用程式能讓您使用 Google Gemini AI 模型分析音訊檔案（來自 YouTube 連結或直接上傳），以生成摘要和逐字稿。

## 先決條件

*   您的系統已安裝 Python 3.7+。
*   可以存取終端機或命令提示字元。
*   Google Gemini API 金鑰。您可以從 [Google AI Studio](https://aistudio.google.com/app/apikey) 獲取。

## 安裝設定 (通用)

本節說明通用的安裝步驟，主要適用於本地開發。對於 Colab 環境，啟動腳本通常會處理大部分這些步驟。

## 🚀 在 Google Colab 中快速啟動 (建議方法)

這個方法讓您直接在 Google Colab 中執行應用程式，並將所有資料（包含下載的音訊和生成的報告）儲存在您的 Google Drive 中，方便管理。

**先決條件：**

1.  **Google 帳戶**：您需要一個 Google 帳戶才能使用 Colab 和 Google Drive。
2.  **Google Gemini API 金鑰**：
    *   強烈建議將您的金鑰添加到 Colab 的「密鑰」(Secrets) 功能中。點擊 Colab 筆記本左側的鑰匙圖示 🔑，然後新增一個名為 `GOOGLE_API_KEY` 的密鑰，值設定為您的 API 金鑰。
    *   如果未設定密鑰，腳本執行時會提示您輸入金鑰。

**使用步驟：**

1.  **開啟 Colab 並建立新筆記本：**
    *   前往 [Google Colab](https://colab.research.google.com/)。
    *   點擊 "File" -> "New notebook"。

2.  **複製並貼上以下完整腳本** 到新筆記本的第一個儲存格中：

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
    #@markdown - 建議在 Colab 的「密鑰」(Secrets) 中設定 `GOOGLE_API_KEY`。
    #@markdown ---

    # GENERAL CONFIGURATION
    # IMPORTANT: If you are using a FORK of this repository, change this URL to your fork's URL!
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
    import re # Added for localtunnel URL parsing

    # --- Helper Functions ---
    def print_status(message):
        print(f"[*] {message}")

    def print_success(message):
        print(f"[SUCCESS] {message}")

    def print_error(message):
        print(f"[ERROR] {message}")
        sys.exit(1)

    def run_command(command, description, check=True):
        print_status(f"執行中: {description}...")
        try:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            if process.returncode != 0 and check:
                print_error(f"{description} 失敗。\n標準輸出:\n{stdout}\n標準錯誤:\n{stderr}")
            elif process.returncode != 0:
                 print(f"[WARNING] {description} 可能有非致命錯誤。\n標準輸出:\n{stdout}\n標準錯誤:\n{stderr}")
            else:
                print_success(f"{description} 完成。")
            return stdout, stderr
        except Exception as e:
            print_error(f"執行 '{description}' 時發生例外: {e}")

    # --- Google Drive Mounting and Folder Setup ---
    print_status("正在掛載 Google Drive...")
    drive.mount('/content/drive', force_remount=True)

    # Define paths in Google Drive
    google_drive_project_root = "/content/drive/MyDrive/AI_Paper_Colab_Data"
    temp_audio_storage_dir_drive = os.path.join(google_drive_project_root, "temp_audio")
    generated_reports_dir_drive = os.path.join(google_drive_project_root, "generated_reports")
    app_code_dir_colab = "/content/app_code" # Where the app code will be cloned in Colab VM

    print_status(f"在 Google Drive 中建立資料夾 (如果不存在):")
    print_status(f"  - 專案根目錄: {google_drive_project_root}")
    os.makedirs(google_drive_project_root, exist_ok=True)
    print_status(f"  - 臨時音訊儲存目錄: {temp_audio_storage_dir_drive}")
    os.makedirs(temp_audio_storage_dir_drive, exist_ok=True)
    print_status(f"  - 生成報告儲存目錄: {generated_reports_dir_drive}")
    os.makedirs(generated_reports_dir_drive, exist_ok=True)
    print_success("Google Drive 資料夾結構設定完成。")

    # --- Application Code Cloning/Updating ---
    if os.path.exists(app_code_dir_colab):
        print_status(f"應用程式碼目錄 '{app_code_dir_colab}' 已存在，先移除舊版本...")
        run_command(f"rm -rf {app_code_dir_colab}", "移除舊的應用程式碼目錄")

    print_status(f"從 GitHub ({github_repo_url}) 下載最新的應用程式碼到 Colab 虛擬機 ({app_code_dir_colab})...")
    run_command(f"git clone {github_repo_url} {app_code_dir_colab}", "下載應用程式碼")

    project_root_colab = app_code_dir_colab # The root for app.py and requirements.txt
    os.chdir(project_root_colab)
    print_success(f"已將工作目錄變更至: {os.getcwd()}")

    # --- Dependency Installation ---
    requirements_path = os.path.join(project_root_colab, "requirements.txt")
    if not os.path.exists(requirements_path):
        print_error(f"找不到 'requirements.txt' 檔案於: {requirements_path}")
    run_command(f"pip install --upgrade pip", "升級 pip")
    run_command(f"pip install -r {requirements_path}", "安裝 Python 套件")

    # --- API Key Setup ---
    print_status("正在設定 Google API 金鑰...")
    google_api_key = ""
    try:
        from google.colab import userdata
        google_api_key = userdata.get('GOOGLE_API_KEY')
        if google_api_key:
            print_success("成功從 Colab Secrets 讀取 GOOGLE_API_KEY。")
        else:
            print_status("Colab Secrets 中未找到 GOOGLE_API_KEY。")
    except ImportError:
        print_status("無法導入 google.colab.userdata (可能為舊版 Colab)，將提示手動輸入。")
    except Exception as e:
        print_status(f"從 Colab Secrets 讀取金鑰時發生錯誤: {e}。將提示手動輸入。")

    if not google_api_key:
        print_status("請手動輸入您的 Google Gemini API 金鑰:")
        google_api_key = input()
        if google_api_key:
            print_success("已接收手動輸入的 API 金鑰。")
        else:
            print_error("未提供 API 金鑰，應用程式可能無法正常運作。")

    os.environ['GOOGLE_API_KEY'] = google_api_key
    # Important: Set environment variables for the app to use Drive paths
    os.environ['APP_TEMP_AUDIO_STORAGE_DIR'] = temp_audio_storage_dir_drive
    os.environ['APP_GENERATED_REPORTS_DIR'] = generated_reports_dir_drive

    print_success(f"環境變數設定完成。")
    print_status(f"  - GOOGLE_API_KEY: {'已設定 (長度: ' + str(len(google_api_key)) + ')' if google_api_key else '未設定'}")
    print_status(f"  - APP_TEMP_AUDIO_STORAGE_DIR: {os.environ['APP_TEMP_AUDIO_STORAGE_DIR']}")
    print_status(f"  - APP_GENERATED_REPORTS_DIR: {os.environ['APP_GENERATED_REPORTS_DIR']}")

    # --- Server Launch ---
    print_status("正在準備啟動 FastAPI 應用程式...")
    app_file_path = os.path.join(project_root_colab, "src", "app.py")
    if not os.path.exists(app_file_path):
        print_error(f"找不到應用程式主檔案 'src/app.py' 於: {project_root_colab}")

    # Using threading to manage ngrok/localtunnel and Uvicorn
    def run_uvicorn():
        print_status("正在啟動 Uvicorn 伺服器...")
        # Ensure Uvicorn runs from the project_root_colab where src/app.py can be found as src.app
        run_command(f"uvicorn src.app:app --host 0.0.0.0 --port 8000 --workers 1", "啟動 Uvicorn", check=False) # check=False as it's a blocking call

    uvicorn_thread = threading.Thread(target=run_uvicorn)
    uvicorn_thread.daemon = True # Allow main program to exit even if thread is running
    uvicorn_thread.start()
    print_status("Uvicorn 伺服器應已在背景執行緒中啟動。")

    # --- Public URL Setup (using ngrok as primary, localtunnel as fallback) ---
    print_status("正在設定公開存取 URL...")
    time.sleep(5) # Give Uvicorn a moment to start

    public_url = ""
    try:
        print_status("嘗試使用 ngrok 建立通道...")
        # Install ngrok if not already (though Colab often has it)
        run_command("pip install pyngrok", "安裝/更新 pyngrok")
        from pyngrok import ngrok, conf
        # Check if NGROK_AUTHTOKEN is in Colab secrets
        try:
            ngrok_auth_token = userdata.get('NGROK_AUTHTOKEN')
            if ngrok_auth_token:
                print_status("從 Colab Secrets 讀取 NGROK_AUTHTOKEN。")
                conf.get_default().auth_token = ngrok_auth_token
            else:
                print_status("Colab Secrets 中未找到 NGROK_AUTHTOKEN。如果您有 ngrok 帳戶，建議設定以獲得更穩定服務。")
        except Exception:
            print_status("無法從 Colab Secrets 讀取 NGROK_AUTHTOKEN (可能為舊版 Colab 或未設定)。")

        public_url = ngrok.connect(8000)
        print_success(f"Ngrok 通道已建立！")
    except Exception as e_ngrok:
        print_status(f"Ngrok 設定失敗: {e_ngrok}")
        print_status("嘗試備選方案 localtunnel...")
        try:
            run_command("npm install -g localtunnel", "安裝 localtunnel")
            # Use a subprocess for localtunnel as it's interactive
            localtunnel_process = subprocess.Popen(
                f"lt --port 8000",
                shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            # Wait a bit for localtunnel to output its URL
            time.sleep(10) # Increased wait time
            stdout, stderr = localtunnel_process.stdout.read(), localtunnel_process.stderr.read() # Non-blocking read

            url_match = re.search(r"your url is: (https?://[^\s]+)", stdout)
            if url_match:
                public_url = url_match.group(1)
                print_success(f"Localtunnel 通道已建立！")
            else:
                print_error(f"無法從 localtunnel 輸出中提取 URL。\nstdout:\n{stdout}\nstderr:\n{stderr}")
                public_url = "無法建立通道，請檢查上方錯誤訊息。"
        except Exception as e_lt:
            print_error(f"Localtunnel 設定失敗: {e_lt}")
            public_url = "Ngrok 和 Localtunnel 皆設定失敗。"

    print("\n" + "="*50)
    print_success(f"🚀 應用程式應該已經啟動！")
    print(f"🔗 公開存取網址 (Public URL): {public_url}")
    print(f"📁 您的資料將會儲存在 Google Drive 的這個位置: {google_drive_project_root}")
    print(f"🕒 您需要保持此 Colab 儲存格持續執行以使用應用程式。")
    print(f"💡 如果遇到問題，請檢查上方儲存格的輸出訊息。")
    print("="*50 + "\n")

    # Display the link prominently
    if public_url and "http" in public_url:
      display(HTML(f"<p>點擊此連結開啟應用程式：<a href='{public_url}' target='_blank'>{public_url}</a></p>"))
    else:
      display(HTML(f"<p style='color:red;'>無法生成公開網址，請檢查日誌。</p>"))

    # Keep the cell running (optional, as background threads might keep it alive)
    # try:
    #     while True:
    #         time.sleep(3600) # Keep alive, print status occasionally
    #         print_status(f"應用程式仍在運行中... 公開網址: {public_url}")
    # except KeyboardInterrupt:
    #     print_status("Colab 執行被使用者中斷。正在關閉...")
    #     if 'ngrok' in sys.modules:
    #         ngrok.disconnect(public_url)
    #         ngrok.kill()
    #     print_success("清理完成。")
    ```

3.  **更新 GitHub 倉庫 URL (如果需要)：**
    *   **非常重要**：如果您是從本專案的 **Fork (分支)** 版本執行，請務必在貼上的腳本中找到 `github_repo_url` 變數，並將其值更改為您 Fork 版本的 GitHub URL。預設是主專案的 URL。
        ```python
        github_repo_url = "YOUR_FORKED_REPOSITORY_URL_HERE"
        ```

4.  **執行儲存格：**
    *   點擊儲存格左側的播放按鈕 (▶️)。
    *   首次執行時，Colab 會請求您授權存取 Google Drive。請允許。
    *   腳本會自動執行所有設定步驟。

5.  **等待應用程式啟動：**
    *   儲存格的輸出會顯示進度。
    *   成功啟動後，您會在輸出末尾看到一個公開的 URL (通常結尾是 `.ngrok.io` 或 `loca.lt`)。

6.  **開啟應用程式：**
    *   點擊該公開 URL，即可在新的瀏覽器分頁中開啟應用程式。

**資料儲存：**

*   所有透過 Colab 腳本處理的音訊檔案 (臨時儲存) 和生成的報告，都會儲存在您的 Google Drive 內名為 `AI_Paper_Colab_Data` 的資料夾中。
    *   臨時音訊檔案：`My Drive/AI_Paper_Colab_Data/temp_audio/`
    *   生成的報告：`My Drive/AI_Paper_Colab_Data/generated_reports/`

**注意事項：**

*   您需要保持該 Colab 儲存格的**執行狀態**才能讓應用程式持續運作。如果關閉 Colab 筆記本或執行階段中斷，應用程式將停止。
*   如果 Colab Secrets 中沒有設定 `GOOGLE_API_KEY`，腳本會提示您在儲存格的輸入欄中貼上您的 API 金鑰。
*   如果 `ngrok` 服務遇到問題，腳本會嘗試使用 `localtunnel` 作為備選方案。

1.  **下載或複製專案：**
    *   從 GitHub 下載專案 ZIP 檔案並解壓縮，或複製本倉庫。
    *   您應該會有一個包含 `src/` 目錄、`requirements.txt` 等檔案的專案根目錄。

2.  **導航到專案根目錄：**
    *   開啟您的終端機或命令提示字元。
    *   切換到專案根目錄：
        ```bash
        cd path/to/your/project-root
        ```

3.  **安裝依賴套件：**
    *   使用 pip 和 `requirements.txt` 檔案安裝必要的 Python 套件：
        ```bash
        pip install -r requirements.txt
        ```

## 部署的檔案結構

應用程式的核心程式碼和設定應大致遵循以下結構：

```
project-root/
├── src/
│   ├── app.py               # FastAPI 應用程式主檔案
│   ├── static/              # 靜態資源 (CSS, JavaScript)
│   │   ├── main.js
│   │   └── style.css
│   └── templates/           # HTML 模板
│       └── index.html
├── requirements.txt         # Python 依賴套件列表
├── README.md                # 本說明檔案
└── .env.example             # (可選) 環境變數範本檔案
```

**資料儲存目錄：**

*   **`temp_audio/`**：用於儲存臨時下載或上傳的音訊檔案。
*   **`generated_reports/`**：用於儲存生成的分析報告。

**對於本地執行：**
*   這些目錄 (`temp_audio/`, `generated_reports/`) 通常會在專案根目錄下由應用程式自動創建 (如果它們不存在)。
*   您可以透過設定 `APP_TEMP_AUDIO_STORAGE_DIR` 和 `APP_GENERATED_REPORTS_DIR` 環境變數來自訂這些目錄的路徑。

**對於 Google Colab (使用建議的快速啟動腳本)：**
*   上述的快速啟動腳本會將這些資料夾 (`temp_audio/` 和 `generated_reports/`) 建立在您的 Google Drive 中的 `AI_Paper_Colab_Data` 目錄下 (即 `My Drive/AI_Paper_Colab_Data/temp_audio/` 和 `My Drive/AI_Paper_Colab_Data/generated_reports/`)。
*   腳本會自動設定相應的環境變數，讓應用程式使用這些位於 Google Drive 的路徑。這確保了即使 Colab 執行階段結束，您的資料也會被保留。

## 執行應用程式 (獨立執行 / 本地開發)

本節說明如何在您的本機電腦上直接執行應用程式，而不透過特定的 Colab 啟動腳本。

1.  **設定 Google API 金鑰 (建議方式：環境變數)：**
    *   本應用程式需要 Google Gemini API 金鑰。
    *   **在啟動應用程式之前**，建議將您的 API 金鑰設定為名為 `GOOGLE_API_KEY` 的環境變數。
        *   在 Linux/macOS 上：
            ```bash
            export GOOGLE_API_KEY="YOUR_API_KEY_HERE"
            ```
        *   在 Windows (命令提示字元) 上：
            ```bash
            set GOOGLE_API_KEY="YOUR_API_KEY_HERE"
            ```
        *   在 Windows (PowerShell) 上：
            ```bash
            $env:GOOGLE_API_KEY="YOUR_API_KEY_HERE"
            ```
        *   請將 `"YOUR_API_KEY_HERE"` 替換為您實際的 API 金鑰。
        *   應用程式 (`src/app.py`) 將在啟動時嘗試讀取此環境變數。

2.  **導航到專案根目錄：**
    *   確保您的終端機位於專案根目錄（例如 `path/to/your/project-root`，其中包含 `src/` 目錄、`requirements.txt` 等）。

3.  **啟動伺服器：**
    *   使用 Uvicorn 執行應用程式。應用程式實例 `app` 位於 `src/app.py`。
        ```bash
        uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
        ```
    *   `--reload` 參數對開發很有用，因為它會在偵測到程式碼變更時自動重新載入伺服器。
    *   您應該會看到指示伺服器正在運行的輸出，通常在 `http://0.0.0.0:8000`。

4.  **在瀏覽器中存取：**
    *   開啟您的網頁瀏覽器並前往 `http://localhost:8000`。

下方的「使用應用程式」部分對於在伺服器運行後（無論是本地還是透過 Colab）與網頁介面互動仍然適用。

## 使用應用程式

（本節說明在伺服器運行後與網頁 UI 互動的方式，無論是在本地還是透過 Colab）

1.  **API 金鑰（如果未透過環境變數或啟動腳本設定）：**
    *   如果應用程式指示 API 金鑰未設定或無效（例如，如果在啟動前未設定 `GOOGLE_API_KEY` 環境變數），您可以使用網頁上的「API 金鑰設定」部分臨時為該工作階段輸入您的 Google Gemini API 金鑰。

2.  **提供音訊來源：**
    *   **YouTube 網址：** 選擇「YouTube 網址」，貼上影片 URL，然後點擊「提交來源並繼續」。
    *   **上傳音訊檔案：** 選擇「上傳音訊檔案」，點擊「選擇音訊檔案...」，選擇您的檔案，然後點擊「提交來源並繼續」。

3.  **設定分析選項：**
    *   音訊來源處理完成（下載或儲存）後，「設定分析選項」部分將會出現。
    *   **選擇 AI 模型：** 從下拉式選單中選擇所需的 Gemini 模型。
    *   **輸出內容：** 選擇您偏好的輸出格式（例如，僅摘要、摘要和逐字稿）。
    *   **額外下載格式：** 除了網頁預覽和 HTML 下載外，如果您還想要 `.md` 或 `.txt` 檔案，請選擇它們。
    *   **進階提示詞 (選填)：** 您可以自訂用於生成的提示詞。

4.  **開始分析：**
    *   點擊「開始分析」按鈕。

5.  **查看結果：**
    *   任務將被添加到「即時任務佇列」。
    *   完成後，「分析結果」部分將顯示報告。
    *   您可以使用提供的連結下載各種格式的報告。
```

---
<br/>
<br/>

<!-- ENGLISH VERSION -->

```markdown
# AI Paper Audio Analysis Tool

This application allows you to analyze audio files (from YouTube links or direct uploads) using Google Gemini AI models to generate summaries and transcripts.

## Prerequisites

*   Python 3.7+ installed on your system.
*   Access to a terminal or command prompt.
*   Google Gemini API Key. You can obtain one from [Google AI Studio](https://aistudio.google.com/app/apikey).

## Setup (General)

This section describes the general setup steps, primarily for local development. For Colab, the launcher script will handle most of these.

1.  **Download or Clone Project:**
    *   Download the project ZIP file from GitHub and extract it, or clone the repository.
    *   You should have a project root folder containing the `src/` directory, `requirements.txt`, etc.

2.  **Navigate to Project Root Directory:**
    *   Open your terminal or command prompt.
    *   Change to the project root directory:
        ```bash
        cd path/to/your/project-root
        ```

3.  **Install Dependencies:**
    *   Install the required Python packages using pip and the `requirements.txt` file:
        ```bash
        pip install -r requirements.txt
        ```

## File Structure for Deployment

When packaging or deploying, or setting up in Google Drive for the Colab launcher, ensure the following structure for the main project folder (e.g., `AI_paper/main/` as referred to by the Colab launcher):

```
your-project-root/  (e.g., AI_paper/main/)
├── src/
│   ├── app.py
│   ├── static/
│   │   ├── main.js
│   │   └── style.css
│   └── templates/
│       └── index.html
├── requirements.txt
├── README.md
├── your_colab_launcher.ipynb  # Or .py launcher script
├── temp_audio/                # Created automatically by app.py
└── generated_reports/         # Created automatically by app.py
```

**Note:**
*   The `temp_audio/` and `generated_reports/` directories will be created by `src/app.py` in its current working directory (e.g., `AI_paper/main/temp_audio/`).
*   The `your_colab_launcher.ipynb` is a placeholder for the Colab notebook or Python script the user has for launching the application.

## Running the Application (Standalone / Local Development)

This section describes how to run the application directly on your local machine, outside of the specific Colab launcher script.

1.  **Set Google API Key (Recommended: Environment Variable):**
    *   This application requires a Google Gemini API Key.
    *   **Before starting the application**, it's recommended to set your API key as an environment variable named `GOOGLE_API_KEY`.
        *   On Linux/macOS:
            ```bash
            export GOOGLE_API_KEY="YOUR_API_KEY_HERE"
            ```
        *   On Windows (Command Prompt):
            ```bash
            set GOOGLE_API_KEY="YOUR_API_KEY_HERE"
            ```
        *   On Windows (PowerShell):
            ```bash
            $env:GOOGLE_API_KEY="YOUR_API_KEY_HERE"
            ```
        *   Replace `"YOUR_API_KEY_HERE"` with your actual API key.
        *   The application (`src/app.py`) will attempt to read this environment variable on startup.

2.  **Navigate to Project Root:**
    *   Ensure your terminal is in the project root directory (e.g., `path/to/your/project-root` which contains the `src/` directory, `requirements.txt`, etc.).

3.  **Start the Server:**
    *   Use Uvicorn to run the application. The application instance `app` is located in `src/app.py`.
        ```bash
        uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
        ```
    *   The `--reload` flag is useful for development as it automatically reloads the server when code changes are detected.
    *   You should see output indicating the server is running, typically on `http://0.0.0.0:8000`.

4.  **Access in Browser:**
    *   Open your web browser and go to `http://localhost:8000`.

## 🚀 Quick Start in Google Colab (Recommended)

This method allows you to run the application directly in Google Colab, storing all data (downloaded audio, generated reports) in your Google Drive for easy access and persistence.

**Prerequisites:**

1.  **Google Account:** Needed for Colab and Google Drive.
2.  **Google Gemini API Key:**
    *   It's highly recommended to add your key to Colab's "Secrets" feature. Click the key icon 🔑 on the left sidebar in your Colab notebook, add a new secret named `GOOGLE_API_KEY`, and paste your API key as the value.
    *   If not set as a secret, the script will prompt you to enter it.

**Steps to Use:**

1.  **Open Colab and Create a New Notebook:**
    *   Go to [Google Colab](https://colab.research.google.com/).
    *   Click "File" -> "New notebook".

2.  **Copy and paste the entire script below** into the first cell of your new notebook:

    ```python
    #@title AI Paper Audio Analysis Tool Colab Quick Launcher
    #@markdown ---
    #@markdown ### 1. Setup and Environment Preparation
    #@markdown This cell will:
    #@markdown 1. Mount your Google Drive.
    #@markdown 2. Create a project data folder (`AI_Paper_Colab_Data`) in your Google Drive.
    #@markdown 3. Clone/pull the latest application code from GitHub into the Colab VM.
    #@markdown 4. Install necessary Python packages.
    #@markdown 5. Set up environment variables (including API key and data folder paths).
    #@markdown 6. Launch the application and provide a public URL.
    #@markdown ---
    #@markdown **Important:**
    #@markdown - If you are using a **Forked version** of this project, **YOU MUST update** the `github_repo_url` variable below to your fork's URL.
    #@markdown - Setting `GOOGLE_API_KEY` in Colab Secrets is recommended.
    #@markdown ---

    # GENERAL CONFIGURATION
    # IMPORTANT: If you are using a FORK of this repository, change this URL to your fork's URL!
    github_repo_url = "https://github.com/LaiHao-Alex/AI_paper_audio_analysis.git" #@param {type:"string"}
    #@markdown ---
    #@markdown ### 2. Run Cell
    #@markdown Click the play button (▶️) to the left of this cell to start.
    #@markdown You will need to authorize Google Drive access.
    #@markdown A public `ngrok.io` or `loca.lt` URL will be provided once the app starts.
    #@markdown ---

    import os
    import sys
    import subprocess
    from google.colab import drive, output
    from IPython.display import display, HTML, Javascript
    import threading
    import time
    import re # Added for localtunnel URL parsing

    # --- Helper Functions ---
    def print_status(message):
        print(f"[*] {message}")

    def print_success(message):
        print(f"[SUCCESS] {message}")

    def print_error(message):
        print(f"[ERROR] {message}")
        sys.exit(1)

    def run_command(command, description, check=True):
        print_status(f"Executing: {description}...")
        try:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            if process.returncode != 0 and check:
                print_error(f"{description} failed.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
            elif process.returncode != 0:
                 print(f"[WARNING] {description} may have non-fatal errors.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
            else:
                print_success(f"{description} completed.")
            return stdout, stderr
        except Exception as e:
            print_error(f"Exception during '{description}': {e}")

    # --- Google Drive Mounting and Folder Setup ---
    print_status("Mounting Google Drive...")
    drive.mount('/content/drive', force_remount=True)

    google_drive_project_root = "/content/drive/MyDrive/AI_Paper_Colab_Data"
    temp_audio_storage_dir_drive = os.path.join(google_drive_project_root, "temp_audio")
    generated_reports_dir_drive = os.path.join(google_drive_project_root, "generated_reports")
    app_code_dir_colab = "/content/app_code"

    print_status(f"Creating folders in Google Drive (if they don't exist):")
    print_status(f"  - Project Root: {google_drive_project_root}")
    os.makedirs(google_drive_project_root, exist_ok=True)
    print_status(f"  - Temp Audio Storage: {temp_audio_storage_dir_drive}")
    os.makedirs(temp_audio_storage_dir_drive, exist_ok=True)
    print_status(f"  - Generated Reports Storage: {generated_reports_dir_drive}")
    os.makedirs(generated_reports_dir_drive, exist_ok=True)
    print_success("Google Drive folder structure setup complete.")

    if os.path.exists(app_code_dir_colab):
        print_status(f"App code directory '{app_code_dir_colab}' exists. Removing old version...")
        run_command(f"rm -rf {app_code_dir_colab}", "Remove old app code directory")

    print_status(f"Cloning/pulling latest application code from GitHub ({github_repo_url}) to Colab VM ({app_code_dir_colab})...")
    run_command(f"git clone {github_repo_url} {app_code_dir_colab}", "Cloning application code")

    project_root_colab = app_code_dir_colab
    os.chdir(project_root_colab)
    print_success(f"Changed working directory to: {os.getcwd()}")

    requirements_path = os.path.join(project_root_colab, "requirements.txt")
    if not os.path.exists(requirements_path):
        print_error(f"'requirements.txt' not found at: {requirements_path}")
    run_command(f"pip install --upgrade pip", "Upgrading pip")
    run_command(f"pip install -r {requirements_path}", "Installing Python packages")

    print_status("Setting up Google API Key...")
    google_api_key = ""
    try:
        from google.colab import userdata
        google_api_key = userdata.get('GOOGLE_API_KEY')
        if google_api_key:
            print_success("Successfully read GOOGLE_API_KEY from Colab Secrets.")
        else:
            print_status("GOOGLE_API_KEY not found in Colab Secrets.")
    except ImportError:
        print_status("Could not import google.colab.userdata (possibly older Colab version). Will prompt for manual input.")
    except Exception as e:
        print_status(f"Error reading key from Colab Secrets: {e}. Will prompt for manual input.")

    if not google_api_key:
        print_status("Please enter your Google Gemini API Key manually:")
        google_api_key = input()
        if google_api_key:
            print_success("API Key received manually.")
        else:
            print_error("No API Key provided. Application might not work correctly.")

    os.environ['GOOGLE_API_KEY'] = google_api_key
    os.environ['APP_TEMP_AUDIO_STORAGE_DIR'] = temp_audio_storage_dir_drive
    os.environ['APP_GENERATED_REPORTS_DIR'] = generated_reports_dir_drive

    print_success(f"Environment variables set.")
    print_status(f"  - GOOGLE_API_KEY: {'Set (length: ' + str(len(google_api_key)) + ')' if google_api_key else 'Not set'}")
    print_status(f"  - APP_TEMP_AUDIO_STORAGE_DIR: {os.environ['APP_TEMP_AUDIO_STORAGE_DIR']}")
    print_status(f"  - APP_GENERATED_REPORTS_DIR: {os.environ['APP_GENERATED_REPORTS_DIR']}")

    print_status("Preparing to launch FastAPI application...")
    app_file_path = os.path.join(project_root_colab, "src", "app.py")
    if not os.path.exists(app_file_path):
        print_error(f"Application main file 'src/app.py' not found in: {project_root_colab}")

    def run_uvicorn():
        print_status("Starting Uvicorn server...")
        run_command(f"uvicorn src.app:app --host 0.0.0.0 --port 8000 --workers 1", "Launch Uvicorn", check=False)

    uvicorn_thread = threading.Thread(target=run_uvicorn)
    uvicorn_thread.daemon = True
    uvicorn_thread.start()
    print_status("Uvicorn server should be starting in a background thread.")

    print_status("Setting up public URL...")
    time.sleep(5)

    public_url = ""
    try:
        print_status("Attempting to create tunnel with ngrok...")
        run_command("pip install pyngrok", "Install/Update pyngrok")
        from pyngrok import ngrok, conf
        try:
            ngrok_auth_token = userdata.get('NGROK_AUTHTOKEN')
            if ngrok_auth_token:
                print_status("Read NGROK_AUTHTOKEN from Colab Secrets.")
                conf.get_default().auth_token = ngrok_auth_token
            else:
                print_status("NGROK_AUTHTOKEN not found in Colab Secrets. Consider setting it for more stable ngrok usage if you have an account.")
        except Exception:
            print_status("Could not read NGROK_AUTHTOKEN from Colab Secrets (possibly older Colab or not set).")

        public_url = ngrok.connect(8000)
        print_success(f"Ngrok tunnel established!")
    except Exception as e_ngrok:
        print_status(f"Ngrok setup failed: {e_ngrok}")
        print_status("Attempting fallback with localtunnel...")
        try:
            run_command("npm install -g localtunnel", "Install localtunnel")
            localtunnel_process = subprocess.Popen(
                f"lt --port 8000",
                shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            time.sleep(10)
            stdout, stderr = localtunnel_process.stdout.read(), localtunnel_process.stderr.read()

            url_match = re.search(r"your url is: (https?://[^\s]+)", stdout)
            if url_match:
                public_url = url_match.group(1)
                print_success(f"Localtunnel tunnel established!")
            else:
                print_error(f"Could not extract URL from localtunnel output.\nstdout:\n{stdout}\nstderr:\n{stderr}")
                public_url = "Tunnel creation failed. Check error messages above."
        except Exception as e_lt:
            print_error(f"Localtunnel setup failed: {e_lt}")
            public_url = "Both Ngrok and Localtunnel setup failed."

    print("\n" + "="*50)
    print_success(f"🚀 Application should be up and running!")
    print(f"🔗 Public URL: {public_url}")
    print(f"📁 Your data will be stored in Google Drive at: {google_drive_project_root}")
    print(f"🕒 Keep this Colab cell running to use the application.")
    print(f"💡 If you encounter issues, check the output messages in this cell.")
    print("="*50 + "\n")

    if public_url and "http" in public_url:
      display(HTML(f"<p>Click this link to open the application: <a href='{public_url}' target='_blank'>{public_url}</a></p>"))
    else:
      display(HTML(f"<p style='color:red;'>Could not generate public URL. Please check logs.</p>"))
    ```

3.  **Update GitHub Repository URL (if necessary):**
    *   **Crucial**: If you are running from a **forked** version of this project, find the `github_repo_url` variable in the pasted script and change its value to your fork's GitHub URL. The default is the main project's URL.
        ```python
        github_repo_url = "YOUR_FORKED_REPOSITORY_URL_HERE"
        ```

4.  **Run the Cell:**
    *   Click the play button (▶️) to the left of the cell.
    *   On the first run, Colab will ask for permission to access your Google Drive. Allow it.
    *   The script will perform all setup steps automatically.

5.  **Wait for Application to Start:**
    *   The cell's output will show progress.
    *   Once successfully started, you will see a public URL (usually ending in `.ngrok.io` or `loca.lt`) at the end of the output.

6.  **Open the Application:**
    *   Click the public URL to open the application in a new browser tab.

**Data Storage:**

*   All audio files processed (temporarily stored) and reports generated via the Colab script will be saved in a folder named `AI_Paper_Colab_Data` within your Google Drive.
    *   Temporary audio files: `My Drive/AI_Paper_Colab_Data/temp_audio/`
    *   Generated reports: `My Drive/AI_Paper_Colab_Data/generated_reports/`

**Important Notes:**

*   You need to keep the Colab cell **running** for the application to remain active. If you close the Colab notebook or the runtime disconnects, the application will stop.
*   If `GOOGLE_API_KEY` is not set in Colab Secrets, the script will prompt you to paste your API key in an input field within the cell.
*   If the `ngrok` service encounters issues, the script will attempt to use `localtunnel` as a fallback.

The "Using the Application" section below remains relevant for interacting with the web UI once it's running.

## Using the Application

(This section describes interacting with the web UI once the server is running, either locally or via Colab)

1.  **API Key (if not set via environment variable or launcher):**
    *   If the application indicates that the API key is not set or is invalid (e.g., if `GOOGLE_API_KEY` environment variable was not set before launch), you can use the "API 金鑰設定" (API Key Settings) section on the web page to enter your Google Gemini API Key temporarily for the session. (Note: "API 金鑰設定" is the Chinese UI text, it would be "API Key Settings" or similar if UI was also translated).

2.  **Provide Audio Source:**
    *   **YouTube URL:** Select "YouTube 網址" (YouTube URL), paste the video URL, and click "提交來源並繼續" (Submit Source and Continue).
    *   **Upload Audio File:** Select "上傳音訊檔案" (Upload Audio File), click "選擇音訊檔案..." (Choose Audio File...), choose your file, and then click "提交來源並繼續".

3.  **Configure Analysis:**
    *   Once the audio source is processed (downloaded or saved), the "設定分析選項" (Configure Analysis Options) section will appear.
    *   **Choose AI Model:** Select the desired Gemini model from the dropdown.
    *   **Output Content:** Choose your preferred output format (e.g., summary only, summary and transcript).
    *   **Extra Download Formats:** Select if you want `.md` or `.txt` files in addition to the web view and HTML download.
    *   **Advanced Prompts (Optional):** You can customize the prompts used for generation.

4.  **Start Analysis:**
    *   Click the "開始分析" (Start Analysis) button.

5.  **View Results:**
    *   The task will be added to the "即時任務佇列" (Real-time Task Queue).
    *   Once completed, the "分析結果" (Analysis Result) section will display the report.
    *   You can download the report in various formats using the provided links.
```

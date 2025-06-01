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

當打包、部署或在 Google Drive 中為 Colab 啟動腳本設定專案時，請確保主專案資料夾（例如 Colab 啟動腳本中提及的 `AI_paper/main/`）具有以下結構：

```
your-project-root/  (例如 AI_paper/main/)
├── src/
│   ├── app.py
│   ├── static/
│   │   ├── main.js
│   │   └── style.css
│   └── templates/
│       └── index.html
├── requirements.txt
├── README.md
├── your_colab_launcher.ipynb  # 或 .py 啟動腳本
├── temp_audio/                # 由 app.py 自動創建
└── generated_reports/         # 由 app.py 自動創建
```

**注意：**
*   `temp_audio/` 和 `generated_reports/` 目錄將由 `src/app.py` 在其目前工作目錄中創建（例如 `AI_paper/main/temp_audio/`）。
*   `your_colab_launcher.ipynb` 是使用者擁有的用於啟動應用程式的 Colab 筆記本或 Python 腳本的佔位符。

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

## 使用 Colab 啟動腳本在 Google Colab 中執行

本應用程式設計為可與您開發的 Colab 啟動腳本相容。以下是它們通常如何協同工作：

1.  **在 Google Drive 中設定專案：**
    *   確保您的專案檔案依照「部署的檔案結構」部分所述的方式排列在 Google Drive 中。例如，您可能會有 `MyDrive/AI_paper/main/`，其中包含 `src/`、`requirements.txt` 等。
    *   您的 Colab 啟動腳本（例如 `your_colab_launcher.ipynb` 或 `.py` 檔案）通常會位於 `MyDrive/AI_paper/` 或 `MyDrive/AI_paper/main/`。

2.  **Colab 啟動腳本的職責：**
    *   您的啟動腳本應處理：
        *   掛載 Google Drive。
        *   將目前目錄變更到專案根目錄（例如 `AI_paper/main/`）。這對於 `uvicorn` 和 `app.py` 正確找到檔案至關重要。
        *   從 `requirements.txt` 安裝依賴套件（例如 `!pip install -r requirements.txt`）。
        *   設定 `GOOGLE_API_KEY`（最好是透過提示使用者或使用 Colab Secrets 功能，名稱為 `GOOGLE_API_KEY`）。
        *   使用類似 `!uvicorn src.app:app --host 0.0.0.0 --port 8000` 的指令啟動 Uvicorn 伺服器。此指令的工作目錄必須是專案根目錄（例如 `AI_paper/main/`）。
        *   在 Colab 輸出中提供一個可點擊的代理應用程式 URL 連結（例如，來自 `google.colab.output.serve_kernel_port_as_window` 或類似功能）。
        *   顯示伺服器日誌。
        *   管理伺服器關閉並提供執行報告。

3.  **啟動腳本和應用程式的關鍵依賴：**
    *   **`GOOGLE_API_KEY`**：`src/app.py` 應用程式將尋找此環境變數。請確保您的啟動腳本正確設定了它（建議使用 Colab Secrets：密鑰名稱為 `GOOGLE_API_KEY`）。
    *   **`requirements.txt`**：確保您的啟動腳本從專案根目錄執行 `pip install -r requirements.txt`。

4.  **協同工作方式：**
    *   檔案結構（包含 `src/app.py`）是 `uvicorn src.app:app` 從專案根目錄啟動時期望的。
    *   `src/app.py` 中 `static` 和 `templates` 目錄的路徑是相對於 `src/app.py` 自身位置（即 `src/static` 和 `src/templates`）定義的，因此應用程式可以正確找到它們。
    *   `temp_audio/` 和 `generated_reports/` 目錄將由 `src/app.py` 在 Uvicorn 啟動的目錄（即專案根目錄，例如 `AI_paper/main/temp_audio/`）內創建。

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

## Running in Google Colab with the Launcher Script

The application is designed to be compatible with a Colab launcher script like the one you've developed. Here's how it generally works together:

1.  **Project Setup in Google Drive:**
    *   Ensure your project files are arranged in Google Drive according to the "File Structure for Deployment" section. For example, you might have `MyDrive/AI_paper/main/`, with `src/`, `requirements.txt` etc. inside `main/`.
    *   Your Colab launcher script (e.g., `your_colab_launcher.ipynb` or a `.py` file) would typically reside in `MyDrive/AI_paper/` or `MyDrive/AI_paper/main/`.

2.  **Colab Launcher Script Responsibilities:**
    *   Your launcher script should handle:
        *   Mounting Google Drive.
        *   Changing the current directory to the project root (e.g., `AI_paper/main/`). This is crucial for `uvicorn` and `app.py` to find files correctly.
        *   Installing dependencies from `requirements.txt` (e.g., `!pip install -r requirements.txt`).
        *   Setting the `GOOGLE_API_KEY` (ideally by prompting the user or using Colab Secrets with the name `GOOGLE_API_KEY`).
        *   Starting the Uvicorn server using a command similar to `!uvicorn src.app:app --host 0.0.0.0 --port 8000`. The working directory for this command must be the project root (e.g., `AI_paper/main/`).
        *   Providing a clickable link to the proxied application URL (e.g., from `google.colab.output.serve_kernel_port_as_window` or similar) in the Colab output.
        *   Displaying server logs.
        *   Managing server shutdown and providing execution reports.

3.  **Key Dependencies for the Launcher and App:**
    *   **`GOOGLE_API_KEY`**: The `src/app.py` application will look for this environment variable. Ensure your launcher script sets it up correctly (Colab Secrets is recommended: `GOOGLE_API_KEY` as the secret name).
    *   **`requirements.txt`**: Ensure your launcher script runs `pip install -r requirements.txt` from the project root directory.

4.  **How it Works Together:**
    *   The file structure (with `src/app.py`) is what `uvicorn src.app:app` expects when launched from the project root.
    *   The paths to `static` and `templates` directories within `src/app.py` are defined relative to `src/app.py`'s own location (`src/static` and `src/templates`), so they will be found correctly by the application.
    *   The `temp_audio/` and `generated_reports/` directories will be created by `src/app.py` inside the directory from which Uvicorn is launched (i.e., the project root, e.g., `AI_paper/main/temp_audio/`).

The "Using the Application" section below remains relevant for interacting with the web interface once it's running.

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

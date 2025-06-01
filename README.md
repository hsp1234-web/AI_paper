```markdown
# AI Paper Audio Analysis Tool

This application allows you to analyze audio files (from YouTube links or direct uploads) using Google Gemini AI models to generate summaries and transcripts.

## Prerequisites

*   Python 3.7+ installed on your system.
*   Access to a terminal or command prompt.

## Setup

1.  **Download and Extract:**
    *   Download the project ZIP file from GitHub.
    *   Extract the contents to a folder on your computer.

2.  **Navigate to Project Directory:**
    *   Open your terminal or command prompt.
    *   Change to the directory where you extracted the files:
        ```bash
        cd path/to/your/extracted/folder
        ```

3.  **Install Dependencies:**
    *   Install the required Python packages using pip and the `requirements.txt` file:
        ```bash
        pip install -r requirements.txt
        ```

## Running the Application

1.  **Set Google API Key (Recommended: Environment Variable):**
    *   This application requires a Google Gemini API Key. You can obtain one from [Google AI Studio](https://aistudio.google.com/app/apikey).
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

2.  **Start the Server:**
    *   Run the application using the following command in your terminal:
        ```bash
        python app.py
        ```
    *   Alternatively, you can use uvicorn directly:
        ```bash
        uvicorn app:app --host 0.0.0.0 --port 8000
        ```
    *   You should see output indicating the server is running, typically on `http://0.0.0.0:8000`.

3.  **Access in Browser:**
    *   Open your web browser and go to `http://localhost:8000`.
    *   If you are running this on a remote server or a platform like Google Colab that provides a public URL, use that URL instead.

## Using the Application

1.  **API Key (if not set via environment variable):**
    *   If the application indicates that the API key is not set or is invalid, you can use the "API 金鑰設定" (API Key Settings) section on the web page to enter your Google Gemini API Key temporarily.

2.  **Provide Audio Source:**
    *   **YouTube URL:** Select "YouTube 網址", paste the video URL, and click "提交來源並繼續" (Submit Source and Continue).
    *   **Upload Audio File:** Select "上傳音訊檔案", click "選擇音訊檔案...", choose your file, and then click "提交來源並繼續".

3.  **Configure Analysis:**
    *   Once the audio source is processed, the "設定分析選項" (Configure Analysis Options) section will appear.
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

## File Structure for Deployment

When packaging or deploying, ensure the following structure:

```
your-project-folder/
├── app.py
├── requirements.txt
├── README.md
├── static/
│   ├── main.js
│   └── style.css
├── templates/
│   └── index.html
├── temp_audio/          # Created automatically for temporary audio files
└── generated_reports/   # Created automatically for report files
```

**Note:** The `temp_audio` and `generated_reports` directories will be created automatically by the application if they don't exist.
```

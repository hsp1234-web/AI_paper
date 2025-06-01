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
    *   If the application indicates that the API key is not set or is invalid (e.g., if `GOOGLE_API_KEY` environment variable was not set before launch), you can use the "API 金鑰設定" (API Key Settings) section on the web page to enter your Google Gemini API Key temporarily for the session.

2.  **Provide Audio Source:**
    *   **YouTube URL:** Select "YouTube 網址", paste the video URL, and click "提交來源並繼續" (Submit Source and Continue).
    *   **Upload Audio File:** Select "上傳音訊檔案", click "選擇音訊檔案...", choose your file, and then click "提交來源並繼續".

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

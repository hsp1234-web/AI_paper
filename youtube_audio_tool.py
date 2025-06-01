
# -*- coding: utf-8 -*-
# ==============================================================================
# AI_paper 專案: YouTube 音訊下載工具模組
# ==============================================================================
# 此模組提供 UI 元件和邏輯，用於從 YouTube 下載原生音訊檔案
# 至 Colab 本地臨時儲存空間。
# ==============================================================================

import os
import re
import ipywidgets as widgets
from IPython.display import display, HTML, clear_output
from datetime import datetime

# pytubefix 的匯入將在此模組被實際使用時由執行環境處理
# 執行環境 (例如 Colab 的主執行儲存格) 需要確保 pytubefix 已安裝
from pytubefix import YouTube
from pytubefix.exceptions import RegexMatchError, VideoUnavailable, PytubeFixError

# --- 暗色系主題顏色 (可由主應用程式傳入或在此預設) ---
# 為了模組獨立性，這裡定義一份，但理想情況是從全局配置讀取
DARK_THEME_BACKGROUND = "#202124"
DARK_THEME_TEXT_PRIMARY = "#e8eaed"
DARK_THEME_TEXT_SECONDARY = "#bdc1c6"
DARK_THEME_ACCENT_BLUE = "#89b4f8"
DARK_THEME_ACCENT_GREEN = "#81c995"
DARK_THEME_ACCENT_YELLOW = "#fdd663"
DARK_THEME_ACCENT_RED = "#f28b82"
DARK_THEME_BORDER_COLOR = "#5f6368"
DARK_THEME_INPUT_BACKGROUND = "#3c4043"

# --- 組態設定 ---
LOCAL_AUDIO_DOWNLOAD_DIR = '/content/ai_paper_local_audio_downloads' # Colab 本地路徑

# --- 全域變數/狀態 (用於進度條回呼的簡化處理) ---
_total_size_bytes = 0
_bytes_downloaded = 0
_last_progress_update_time = 0 # 控制進度條更新頻率

# --- UI 元件實例 (在 create_ui 函式中初始化) ---
# 這些會在 create_youtube_download_ui 函式中被正確初始化並返回
youtube_url_input_widget = None
download_button_widget = None
status_output_widget = None
progress_output_widget = None
result_output_widget = None

# --- 輔助函式 ---
def _style_print(message, area, msg_type="info", clear_area=False):
    '''將帶樣式的訊息印到指定的輸出區域。'''
    if clear_area and area:
        with area:
            clear_output(wait=True)

    color_map = {
        "info": DARK_THEME_ACCENT_BLUE, "success": DARK_THEME_ACCENT_GREEN,
        "warning": DARK_THEME_ACCENT_YELLOW, "error": DARK_THEME_ACCENT_RED,
        "progress_text": DARK_THEME_TEXT_SECONDARY, "path": DARK_THEME_ACCENT_GREEN
    }
    text_color = color_map.get(msg_type, DARK_THEME_TEXT_PRIMARY)
    timestamp = datetime.now().strftime("%H:%M:%S")

    if area:
        with area:
            display(HTML(
                f"<p style='color:{text_color}; margin:2px 0; font-family: "Noto Sans TC", "Google Sans", sans-serif; font-size:0.9em; word-break:break-word;'>"
                f"<strong style='color:{DARK_THEME_TEXT_SECONDARY};'>[{timestamp}]</strong> {message}</p>"
            ))

def _display_progress_bar(percentage, file_size_str, downloaded_str):
    '''在 progress_output_widget 中顯示進度條。'''
    if not progress_output_widget:
        return
    bar_length = 30
    filled_length = int(bar_length * percentage // 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length) # 使用不同的填充字元
    progress_html = (
        f"<div style='font-family: "Menlo", "DejaVu Sans Mono", monospace; font-size:0.85em; color:{DARK_THEME_TEXT_SECONDARY}; background-color:{DARK_THEME_INPUT_BACKGROUND}; padding:8px; border-radius:4px; border: 1px solid {DARK_THEME_BORDER_COLOR}'>"
        f"下載進度: |{bar}| {percentage:>6.2f}%<br>"
        f"檔案大小: {downloaded_str:>10s} / {file_size_str:>10s}"
        f"</div>"
    )
    with progress_output_widget:
        clear_output(wait=True)
        display(HTML(progress_html))

def _clear_all_download_outputs():
    '''清除所有下載相關的輸出區域。'''
    outputs_to_clear = [status_output_widget, progress_output_widget, result_output_widget]
    for output_area in outputs_to_clear:
        if output_area:
            with output_area:
                clear_output(wait=True)

def _sanitize_filename(title, max_length=80): # 稍微縮短最大長度以更安全
    '''清理字串以作為安全的檔案名稱。'''
    if not title:
        title = "untitled_audio"
    title = str(title)
    title = re.sub(r'[\/*?:"<>|]', "_", title)
    title = title.replace(" ", "_")
    title = re.sub(r"_+", "_", title)
    title = title.strip('_')
    
    # 處理副檔名和長度
    base, ext = os.path.splitext(title)
    if len(base) > max_length:
        base = base[:max_length]
    
    # 確保副檔名合理 (例如, 避免過長的副檔名)
    if ext and len(ext) > 10: # 限制副檔名長度
        ext = ext[:10]
        
    return base + ext if ext else base

# --- pytubefix 下載進度回呼 ---
def _on_progress_callback(stream, chunk, bytes_remaining):
    '''pytubefix 下載進度回呼函式。'''
    global _total_size_bytes, _bytes_downloaded, _last_progress_update_time
    
    current_time = datetime.now().timestamp()
    if _total_size_bytes == 0: # 針對此串流的首次呼叫
        _total_size_bytes = stream.filesize
        _bytes_downloaded = 0
        _last_progress_update_time = 0 # 確保第一次立即更新

    _bytes_downloaded = _total_size_bytes - bytes_remaining
    percentage = (_bytes_downloaded / _total_size_bytes) * 100 if _total_size_bytes > 0 else 0
    
    # 控制更新頻率，例如每0.5秒或進度變化超過一定幅度
    if current_time - _last_progress_update_time > 0.5 or percentage == 100:
        file_size_str = f"{_total_size_bytes / (1024 * 1024):.2f} MB" if _total_size_bytes > 0 else "未知"
        downloaded_str = f"{_bytes_downloaded / (1024 * 1024):.2f} MB" if _total_size_bytes > 0 else f"{_bytes_downloaded / 1024:.1f} KB"
        _display_progress_bar(percentage, file_size_str, downloaded_str)
        _last_progress_update_time = current_time

# --- 核心下載邏輯 ---
def _download_youtube_audio_local_action(youtube_url):
    '''處理 YouTube 音訊下載的核心函式。'''
    global _total_size_bytes, _bytes_downloaded # 重設進度條狀態變數

    _clear_all_download_outputs()
    _style_print(f"開始處理網址: {youtube_url}", area=status_output_widget, msg_type="info")

    if not youtube_url or not youtube_url.strip():
        _style_print("錯誤: YouTube 網址不能為空。", area=status_output_widget, msg_type="error")
        return

    _total_size_bytes = 0 # 重設進度
    _bytes_downloaded = 0 # 重設進度

    try:
        yt = YouTube(youtube_url, on_progress_callback=_on_progress_callback)
        _style_print(f"取得影片標題: {yt.title}", area=status_output_widget, msg_type="info")

        # 篩選原生音訊串流，優先選擇 m4a (AAC) 或 webm (Opus)
        # pytubefix 的 get_audio_only() 通常會選到 mp4/m4a
        audio_stream = yt.streams.get_audio_only()
        
        if not audio_stream: # 如果 get_audio_only() 沒找到，嘗試更明確的篩選
            audio_stream = yt.streams.filter(only_audio=True, file_extension='m4a').order_by('abr').desc().first()
            if not audio_stream:
                 audio_stream = yt.streams.filter(only_audio=True, file_extension='webm').order_by('abr').desc().first()

        if not audio_stream:
            _style_print("錯誤: 找不到可用的原生音訊串流。", area=status_output_widget, msg_type="error")
            if progress_output_widget: # 清除可能已顯示的"下載中"
                with progress_output_widget: clear_output()
            return

        _style_print(f"找到音訊串流: {audio_stream.mime_type}, 位元率約 {audio_stream.abr}", area=status_output_widget, msg_type="info")
        
        # 準備下載路徑和檔名
        os.makedirs(LOCAL_AUDIO_DOWNLOAD_DIR, exist_ok=True)
        base_filename = _sanitize_filename(yt.title)
        # 副檔名從串流中獲取，通常是 'mp4' (對應 m4a 的 AAC 音訊) 或 'webm'
        file_extension = audio_stream.subtype 
        final_filename = f"{base_filename}.{file_extension}"
        download_path = os.path.join(LOCAL_AUDIO_DOWNLOAD_DIR, final_filename)

        _style_print(f"準備下載至: {download_path}", area=status_output_widget, msg_type="info")
        if progress_output_widget: # 顯示"下載中"
             _display_progress_bar(0, "計算中...", "0 MB")


        # 執行下載
        actual_downloaded_path = audio_stream.download(output_path=LOCAL_AUDIO_DOWNLOAD_DIR, filename=final_filename)
        
        # 確保進度條顯示100%
        if _total_size_bytes > 0 : # 避免除以零
             _display_progress_bar(100, f"{_total_size_bytes / (1024 * 1024):.2f} MB", f"{_total_size_bytes / (1024 * 1024):.2f} MB")
        else: # 如果檔案大小未知，也顯示完成
            if progress_output_widget:
                with progress_output_widget: clear_output() # 清除進度條，因為沒有準確大小
                _style_print("下載完成 (檔案大小未知)", area=progress_output_widget, msg_type="success")


        _style_print(f"音訊下載成功!", area=status_output_widget, msg_type="success")
        _style_print(f"檔案儲存於 Colab 本地: {actual_downloaded_path}", area=result_output_widget, msg_type="path")

    except RegexMatchError:
        _style_print("錯誤: YouTube 網址格式不正確。", area=status_output_widget, msg_type="error")
    except VideoUnavailable:
        _style_print("錯誤: 該影片無法取得 (可能受版權保護或地區限制)。", area=status_output_widget, msg_type="error")
    except PytubeFixError as e_pytube:
        _style_print(f"錯誤: pytubefix 下載時發生問題: {e_pytube}", area=status_output_widget, msg_type="error")
    except Exception as e:
        _style_print(f"下載過程中發生未預期錯誤: {e}", area=status_output_widget, msg_type="error")
    finally:
        if download_button_widget: # 重新啟用按鈕
             download_button_widget.disabled = False
             download_button_widget.description = "下載音訊"


# --- 按鈕點擊事件處理函式 ---
def _on_download_button_clicked(b):
    '''下載按鈕的點擊事件處理。'''
    if download_button_widget:
        download_button_widget.disabled = True
        download_button_widget.description = "處理中..."
    
    url = youtube_url_input_widget.value if youtube_url_input_widget else ""
    _download_youtube_audio_local_action(url)

# --- UI 建構函式 ---
def create_youtube_download_ui():
    '''
    創建並返回 YouTube 音訊下載功能的 UI 元件。
    返回一個包含所有 UI 元件的 ipywidgets.VBox。
    '''
    global youtube_url_input_widget, download_button_widget, status_output_widget, progress_output_widget, result_output_widget

    # 初始化 UI 元件
    youtube_url_input_widget = widgets.Text(
        value='',
        placeholder='貼上 YouTube 影片網址...',
        description='', # 描述由外部 HTML 提供
        style={'description_width': 'initial'},
        layout=widgets.Layout(width='100%', margin='0 0 10px 0') # 響應式寬度
    )

    download_button_widget = widgets.Button(
        description="下載音訊",
        button_style='info',
        tooltip='從輸入的 YouTube 網址下載原生音訊',
        icon='download',
        layout=widgets.Layout(width='auto', margin='5px 0 10px 0')
    )

    status_output_widget = widgets.Output(layout={'padding': '5px', 'margin_top': '5px', 'width': '100%'})
    progress_output_widget = widgets.Output(layout={'margin_top': '5px', 'width': '100%'})
    result_output_widget = widgets.Output(layout={'margin_top': '10px', 'width': '100%'})

    # 綁定事件
    download_button_widget.on_click(_on_download_button_clicked)

    # 使用 HTML 營造深色模式的整體外觀
    ui_title_html = HTML(
        f"<div style='background-color: {DARK_THEME_BACKGROUND}; color: {DARK_THEME_TEXT_PRIMARY}; padding: 15px; border-radius: 8px; font-family: "Noto Sans TC", "Google Sans", sans-serif;'>"
        f"<h3 style='color: {DARK_THEME_ACCENT_BLUE}; border-bottom: 1px solid {DARK_THEME_BORDER_COLOR}; padding-bottom: 8px; margin-top: 0;'>YouTube 音訊下載至本地</h3>"
        f"<p style='color: {DARK_THEME_TEXT_SECONDARY}; font-size: 0.9em; margin-bottom:15px;'>輸入 YouTube 網址以下載原生音訊。檔案將暫存於 Colab 本地空間。</p>"
        f"</div>"
    )
    
    # 組織 UI 佈局
    # 使用 VBox 確保在不同裝置上的響應式佈局
    input_section = widgets.VBox([
        widgets.HTML(value=f"<label for='{id(youtube_url_input_widget)}' style='display:block; margin-bottom:5px; font-size:0.9em; color:{DARK_THEME_TEXT_SECONDARY};'>YouTube 影片網址:</label>"), # 手動 label
        youtube_url_input_widget,
        download_button_widget
    ], layout=widgets.Layout(width='100%', align_items='stretch', padding='0 0 10px 0'))

    # 整體 UI 容器
    ui_container = widgets.VBox([
        ui_title_html,
        input_section,
        status_output_widget,
        progress_output_widget,
        result_output_widget
    ], layout=widgets.Layout(width='100%')) # 確保VBox填滿可用寬度

    # 初始訊息
    if status_output_widget :
        with status_output_widget:
            clear_output() # 清除可能殘留的舊訊息
            _style_print("音訊下載工具已準備就緒。", area=status_output_widget, msg_type="info")

    return ui_container

# 可選: 如果想直接測試此模組 (通常不會在產生 .py 後這樣做)
# if __name__ == '__main__':
#     # 這段程式碼在被匯入時不會執行
#     # 可以在開發此模組時取消註解以獨立測試 UI
#     ui = create_youtube_download_ui()
#     display(ui)
#     # 需要手動確保 pytubefix 已安裝才能測試

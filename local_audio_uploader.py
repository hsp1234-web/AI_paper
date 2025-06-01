
# -*- coding: utf-8 -*-
# ==============================================================================
# AI_paper 專案: 本地音訊檔案上傳工具模組
# ==============================================================================
# 此模組提供 UI 元件和邏輯，用於從使用者本機上傳音訊檔案
# 至 Colab 本地臨時儲存空間。
# ==============================================================================

import os
import ipywidgets as widgets
from IPython.display import display, HTML, clear_output
from datetime import datetime
import io # 用於處理上傳檔案的位元組流

# --- 暗色系主題顏色 (與其他模組一致) ---
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
# Colab 本地儲存上傳檔案的路徑
LOCAL_UPLOAD_STORAGE_DIR = '/content/ai_paper_local_audio_uploads'

# --- UI 元件實例 (在 create_ui 函式中初始化) ---
file_upload_widget = None
process_upload_button_widget = None
upload_status_output_widget = None
uploaded_file_info_widget = None

# --- 輔助函式 ---
def _style_print_uploader(message, area, msg_type="info", clear_area=False):
    '''將帶樣式的訊息印到指定的輸出區域'''
    if clear_area and area:
        with area:
            clear_output(wait=True)

    color_map = {
        "info": DARK_THEME_ACCENT_BLUE, "success": DARK_THEME_ACCENT_GREEN,
        "warning": DARK_THEME_ACCENT_YELLOW, "error": DARK_THEME_ACCENT_RED,
        "path": DARK_THEME_ACCENT_GREEN
    }
    text_color = color_map.get(msg_type, DARK_THEME_TEXT_PRIMARY)
    timestamp = datetime.now().strftime("%H:%M:%S")

    if area:
        with area:
            display(HTML(
                f"<p style='color:{text_color}; margin:2px 0; font-family: "Noto Sans TC", "Google Sans", sans-serif; font-size:0.9em; word-break:break-word;'>"
                f"<strong style='color:{DARK_THEME_TEXT_SECONDARY};'>[{timestamp}]</strong> {message}</p>"
            ))

def _clear_all_uploader_outputs():
    '''清除所有上傳相關的輸出區域'''
    outputs_to_clear = [upload_status_output_widget, uploaded_file_info_widget]
    for output_area in outputs_to_clear:
        if output_area:
            with output_area:
                clear_output(wait=True)

def _format_bytes(size):
    # 將位元組轉換為更易讀的格式 (KB, MB)
    if size < 1024:
        return f"{size} Bytes"
    elif size < 1024**2:
        return f"{size/1024:.2f} KB"
    else:
        return f"{size/(1024**2):.2f} MB"

# --- 核心上傳與儲存邏輯 ---
def _save_uploaded_file_action():
    '''處理並儲存已選擇的檔案'''
    global file_upload_widget 

    if not file_upload_widget or not file_upload_widget.value:
        _style_print_uploader("錯誤: 請先選擇一個音訊檔案", area=upload_status_output_widget, msg_type="error")
        return None

    uploaded_file_data_dict = file_upload_widget.value
    if not isinstance(uploaded_file_data_dict, dict) or not uploaded_file_data_dict:
        _style_print_uploader("錯誤: 檔案上傳資料格式不正確或為空", area=upload_status_output_widget, msg_type="error")
        return None

    original_filename = list(uploaded_file_data_dict.keys())[0]
    file_data = uploaded_file_data_dict[original_filename]
    file_content_bytes = file_data['content']
    file_metadata = file_data['metadata']

    _clear_all_uploader_outputs()
    _style_print_uploader(f"開始處理上傳檔案: {original_filename}", area=upload_status_output_widget, msg_type="info")

    try:
        os.makedirs(LOCAL_UPLOAD_STORAGE_DIR, exist_ok=True)
        safe_filename = os.path.basename(original_filename) 
        save_path = os.path.join(LOCAL_UPLOAD_STORAGE_DIR, safe_filename)

        with open(save_path, 'wb') as f:
            f.write(file_content_bytes)

        file_size_str = _format_bytes(file_metadata.get('size', len(file_content_bytes)))
        
        info_html = (
            f"<div style='color:{DARK_THEME_TEXT_PRIMARY}; background-color:{DARK_THEME_INPUT_BACKGROUND}; padding:10px; border-radius:4px; border:1px solid {DARK_THEME_BORDER_COLOR}; font-size:0.9em;'>"
            f"<strong style='color:{DARK_THEME_ACCENT_GREEN};'>檔案成功儲存至 Colab 本地:</strong><br>"
            f"<span style='color:{DARK_THEME_TEXT_SECONDARY};'>原始檔名:</span> {original_filename}<br>"
            f"<span style='color:{DARK_THEME_TEXT_SECONDARY};'>儲存路徑:</span> <code style='color:{DARK_THEME_ACCENT_BLUE};'>{save_path}</code><br>"
            f"<span style='color:{DARK_THEME_TEXT_SECONDARY};'>檔案大小:</span> {file_size_str}<br>"
            f"<span style='color:{DARK_THEME_TEXT_SECONDARY};'>檔案類型:</span> {file_metadata.get('type', 'N/A')}"
            f"</div>"
        )
        if uploaded_file_info_widget:
            with uploaded_file_info_widget:
                clear_output(wait=True)
                display(HTML(info_html))
        
        _style_print_uploader(f"檔案 '{original_filename}' 已成功處理並儲存", area=upload_status_output_widget, msg_type="success")
        
        if file_upload_widget:
            file_upload_widget.value.clear() 
            file_upload_widget._counter = 0 

        return save_path

    except Exception as e:
        _style_print_uploader(f"儲存上傳檔案 '{original_filename}' 時發生錯誤: {e}", area=upload_status_output_widget, msg_type="error")
        if uploaded_file_info_widget:
            with uploaded_file_info_widget: clear_output()
        return None
    finally:
        if process_upload_button_widget: 
            process_upload_button_widget.disabled = False
            process_upload_button_widget.description = "處理上傳檔案"

# --- 按鈕點擊事件處理函式 ---
def _on_process_upload_button_clicked(b):
    '''處理上傳檔案按鈕的點擊事件'''
    if process_upload_button_widget:
        process_upload_button_widget.disabled = True
        process_upload_button_widget.description = "處理中..."
    
    _save_uploaded_file_action()


# --- UI 建構函式 ---
def create_local_audio_upload_ui():
    '''
    創建並返回本地音訊檔案上傳功能的 UI 元件.
    返回一個包含所有 UI 元件的 ipywidgets.VBox.
    '''
    global file_upload_widget, process_upload_button_widget, upload_status_output_widget, uploaded_file_info_widget

    file_upload_widget = widgets.FileUpload(
        accept='audio/*', 
        multiple=False,  
        description='選擇音訊檔案',
        button_style='', 
        style={'description_width': 'initial'},
        layout=widgets.Layout(width='auto', margin='0 0 10px 0')
    )

    process_upload_button_widget = widgets.Button(
        description="處理上傳檔案",
        button_style='success', 
        tooltip='處理已選擇的音訊檔案並儲存到 Colab 本地',
        icon='upload',
        layout=widgets.Layout(width='auto', margin='5px 0 10px 0')
    )

    upload_status_output_widget = widgets.Output(layout={'padding': '5px', 'margin_top': '5px', 'width': '100%'})
    uploaded_file_info_widget = widgets.Output(layout={'margin_top': '10px', 'width': '100%'})

    process_upload_button_widget.on_click(_on_process_upload_button_clicked)

    ui_title_html = HTML(
        f"<div style='background-color: {DARK_THEME_BACKGROUND}; color: {DARK_THEME_TEXT_PRIMARY}; padding: 15px; border-radius: 8px; font-family: "Noto Sans TC", "Google Sans", sans-serif;'>"
        f"<h3 style='color: {DARK_THEME_ACCENT_BLUE}; border-bottom: 1px solid {DARK_THEME_BORDER_COLOR}; padding-bottom: 8px; margin-top: 0;'>本地音訊檔案上傳</h3>"
        f"<p style='color: {DARK_THEME_TEXT_SECONDARY}; font-size: 0.9em; margin-bottom:15px;'>從您的電腦選擇一個音訊檔案上傳至 Colab 本地暫存空間.</p>"
        f"</div>"
    )
    
    input_section = widgets.VBox([
        file_upload_widget,
        process_upload_button_widget
    ], layout=widgets.Layout(width='100%', align_items='flex-start', padding='0 0 10px 0'))

    ui_container = widgets.VBox([
        ui_title_html,
        input_section,
        upload_status_output_widget,
        uploaded_file_info_widget
    ], layout=widgets.Layout(width='100%'))

    if upload_status_output_widget:
        with upload_status_output_widget:
            clear_output() # 清除舊訊息
            _style_print_uploader("檔案上傳工具已準備就緒", area=upload_status_output_widget, msg_type="info")

    return ui_container

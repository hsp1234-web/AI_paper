
// static/main.js - v2.4 (進階模型列表、422修正、預設提示詞 - 優化版)
console.log('AI_paper UI Initialized (v2.4 - Optimized)');

document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
    const body = document.body;
    const themeToggleButton = document.getElementById('theme-toggle-btn');
    const currentYearSpan = document.getElementById('current-year');
    const fontDecreaseBtn = document.getElementById('font-decrease-btn');
    const fontDefaultBtn = document.getElementById('font-default-btn');
    const fontIncreaseBtn = document.getElementById('font-increase-btn');
    const quickNavLinks = document.querySelectorAll('.quick-nav-link');
    const sourceTypeRadios = document.querySelectorAll('input[name="source_type"]');
    const youtubeInputArea = document.getElementById('youtube-input-area');
    const uploadInputArea = document.getElementById('upload-input-area');
    const youtubeUrlInput = document.getElementById('youtube-url');
    const audioFileInput = document.getElementById('audio-file-input');
    const fileInputLabel = document.querySelector('.file-input-label');
    const fileUploadInfo = document.getElementById('file-upload-info');
    const submitSourceBtn = document.getElementById('submit-source-btn');
    const apiKeySection = document.getElementById('api-key-section');
    const apiKeyStatusMessage = document.getElementById('api-key-status-message');
    const apiKeyInput = document.getElementById('api-key-input');
    const submitApiKeyBtn = document.getElementById('submit-api-key-btn');
    const howToSetApiKeyBtn = document.getElementById('how-to-set-api-key-btn');
    const apiKeyInstructionsModal = document.getElementById('api-key-instructions-modal');
    const closeApiKeyModalBtn = apiKeyInstructionsModal ? apiKeyInstructionsModal.querySelector('.close-button') : null;
    const configSection = document.getElementById('config-section');
    const aiModelSelect = document.getElementById('ai-model-select');
    const modelInfoDisplay = document.getElementById('model-info-display'); // 用於顯示模型詳細介紹
    const customSummaryPromptInput = document.getElementById('custom-summary-prompt');
    const customTranscriptPromptInput = document.getElementById('custom-transcript-prompt');
    const startAnalysisBtn = document.getElementById('start-analysis-btn');
    const taskQueueSection = document.getElementById('task-queue-section');
    const taskQueueContainer = document.getElementById('task-queue-container');
    const statusSection = document.getElementById('status-section');
    const statusLog = document.getElementById('status-log');
    const resultSection = document.getElementById('result-section');
    const currentResultTaskNameSpan = document.getElementById('current-result-task-name');
    const reportOutputArea = document.getElementById('report-output-area');
    const downloadLinksDiv = document.getElementById('download-links');

    let currentSelectedAudioPath = null;
    let currentSourceType = 'youtube';
    let activePollingIntervalId = null;
    const POLLING_INTERVAL = 5000;
    let allModelsDataCache = []; // 用於快取從 API 獲取的完整模型資料

    const DEFAULT_SUMMARY_PROMPT = "請根據音訊內容，生成一份簡潔、專業的繁體中文重點摘要。摘要應包含一個總體主旨的開頭段落，以及數個帶有粗體子標題的重點條目，每個條目下使用無序列表列出關鍵細節。請勿在摘要中包含時間戳記。範例如下：\n\n**重點1子標題**\n- 細節1\n- 細節2";
    const DEFAULT_TRANSCRIPT_PROMPT = "請將音訊內容轉換為逐字稿。如果內容包含多位發言者，請嘗試區分（例如：發言者A, 發言者B）。對於專有名詞、品牌名稱、人名等，請盡可能以「中文 (English)」的格式呈現。請確保標點符號的準確性，並以自然的段落分隔。";

    // --- 統一的 logStatus 輔助函式 (將 \n 轉為 <br> 以便在 HTML 中顯示多行錯誤) ---
    function logStatus(message, type = 'info', options = {}) {
        const { targetElement = statusLog, append = true, clearExisting = false } = options;
        if (!targetElement) { return; }
        const timestamp = new Date().toLocaleTimeString('zh-TW', { hour12: false });
        const p = document.createElement('p');
        let iconClass = 'fas fa-info-circle';
        let colorVar = 'var(--accent-color-info)';
        switch (type) {
            case 'error': iconClass = 'fas fa-times-circle'; colorVar = 'var(--accent-color-red)'; break;
            case 'success': iconClass = 'fas fa-check-circle'; colorVar = 'var(--accent-color-green)'; break;
            case 'warning': iconClass = 'fas fa-exclamation-triangle'; colorVar = 'var(--accent-color-yellow)'; break;
        }
        // 將 \n 替換為 <br>，以正確顯示多行訊息
        const formattedMessage = message.replace(/\n/g, '<br>');
        p.innerHTML = `<i class="${iconClass}" style="margin-right: 8px; color:${colorVar};"></i><span style="color:var(--text-color-tertiary);">[${timestamp}]</span> ${formattedMessage}`;
        p.style.color = colorVar;
        if (clearExisting || (!append && targetElement !== statusLog) ) {
            targetElement.innerHTML = '';
        }
        targetElement.appendChild(p);
        if (append && targetElement === statusLog) {
            targetElement.scrollTop = targetElement.scrollHeight;
        }
    }

    // --- 其他輔助函式 ---
    function _showSection(sectionElement, displayType = 'block') { if (sectionElement) sectionElement.style.display = displayType; }
    function _hideSection(sectionElement) { if (sectionElement) sectionElement.style.display = 'none'; }
    function _enableButton(button, text, iconClass = null) { if (!button) return; button.disabled = false; let newHTML = text; if (iconClass) newHTML = `<i class="${iconClass}"></i> ${text}`; button.innerHTML = newHTML;}
    function _disableButton(button, text, iconClass = "fas fa-spinner fa-spin") { if (!button) return; button.disabled = true; button.innerHTML = `<i class="${iconClass}"></i> ${text}`; }

    // 主題管理
    const applyTheme = (theme) => {
        body.classList.remove('light-mode', 'dark-mode');
        body.classList.add(theme);
        localStorage.setItem('theme', theme);
        setRgbColorVariables();
    };

    const setRgbColorVariables = () => {
        const style = getComputedStyle(document.body);
        const primaryColor = style.getPropertyValue('--primary-color').trim();
        const secondaryColor = style.getPropertyValue('--secondary-color').trim();
        const accentColorBlue = style.getPropertyValue('--accent-color-blue').trim();

        document.documentElement.style.setProperty('--primary-color-rgb', hexToRgb(primaryColor));
        document.documentElement.style.setProperty('--secondary-color-rgb', hexToRgb(secondaryColor));
        document.documentElement.style.setProperty('--accent-color-blue-rgb', hexToRgb(accentColorBlue));
    };

    const hexToRgb = (hex) => {
        if (!hex || hex.trim() === '') return ''; // Handle empty or invalid hex
        // Remove '#' if present
        const cleanHex = hex.startsWith('#') ? hex.slice(1) : hex;

        // Pad if shorthand hex (e.g., #abc -> #aabbcc)
        const fullHex = cleanHex.length === 3 ? cleanHex.split('').map(char => char + char).join('') : cleanHex;

        // Check if the hex is valid after cleaning and padding
        if (!/^[0-9a-fA-F]{6}$/.test(fullHex)) {
            console.warn(`Invalid hex color for conversion: ${hex}`);
            return '';
        }

        const r = parseInt(fullHex.slice(0, 2), 16);
        const g = parseInt(fullHex.slice(2, 4), 16);
        const b = parseInt(fullHex.slice(4, 6), 16);
        return `${r}, ${g}, ${b}`;
    };

    // 字體大小管理
    const applyFontSize = (sizeKey) => {
        const root = document.documentElement;
        switch (sizeKey) {
            case 'small':
                root.style.setProperty('--base-font-size', '14px');
                root.style.setProperty('--heading-font-size-multiplier', '1.1');
                break;
            case 'default':
                root.style.setProperty('--base-font-size', '16px');
                root.style.setProperty('--heading-font-size-multiplier', '1.2');
                break;
            case 'large':
                root.style.setProperty('--base-font-size', '18px');
                root.style.setProperty('--heading-font-size-multiplier', '1.3');
                break;
        }
        localStorage.setItem('fontSize', sizeKey);
    };

    // 其他初始化和事件監聽器
    if (currentYearSpan) {
        currentYearSpan.textContent = new Date().getFullYear();
    }

    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', () => {
            const currentTheme = localStorage.getItem('theme') || 'dark-mode';
            applyTheme(currentTheme === 'dark-mode' ? 'light-mode' : 'dark-mode');
        });
    }

    if (fontDecreaseBtn) fontDecreaseBtn.addEventListener('click', () => applyFontSize('small'));
    if (fontDefaultBtn) fontDefaultBtn.addEventListener('click', () => applyFontSize('default'));
    if (fontIncreaseBtn) fontIncreaseBtn.addEventListener('click', () => applyFontSize('large'));

    quickNavLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('data-target');
            const targetElement = document.getElementById(targetId);
            if (targetElement) {
                targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    sourceTypeRadios.forEach(radio => {
        radio.addEventListener('change', (event) => {
            currentSourceType = event.target.value;
            if (currentSourceType === 'youtube') {
                _showSection(youtubeInputArea);
                _hideSection(uploadInputArea);
                fileUploadInfo.textContent = ''; // 清空檔案上傳資訊
            } else { // upload
                _hideSection(youtubeInputArea);
                _showSection(uploadInputArea);
                youtubeUrlInput.value = ''; // 清空 YouTube URL
            }
            // 重置已選音訊路徑，因為切換了來源類型
            currentSelectedAudioPath = null;
            // 清空所有狀態日誌，因為狀態可能已經無效
            if (statusLog) statusLog.innerHTML = '';
            logStatus("已切換音訊來源類型，請重新處理。","info");
            _disableButton(startAnalysisBtn, '請先處理音訊來源', 'fas fa-hand-pointer');
            // 清空結果區
            reportOutputArea.innerHTML = '';
            downloadLinksDiv.innerHTML = '';
            _hideSection(resultSection);
        });
    });

    if (audioFileInput) {
        audioFileInput.addEventListener('change', () => {
            if (audioFileInput.files.length > 0) {
                const file = audioFileInput.files[0];
                fileInputLabel.textContent = file.name;
                fileUploadInfo.textContent = `檔案: ${file.name} (大小: ${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
                _enableButton(submitSourceBtn, '上傳音訊檔案', 'fas fa-upload');
                logStatus(`準備上傳檔案: ${file.name}`, 'info');
            } else {
                fileInputLabel.textContent = '選擇音訊檔案';
                fileUploadInfo.textContent = '';
                _disableButton(submitSourceBtn, '請選擇檔案', 'fas fa-file-upload');
                currentSelectedAudioPath = null;
            }
            _disableButton(startAnalysisBtn, '請先處理音訊來源', 'fas fa-hand-pointer');
        });
    }

    if (submitSourceBtn) {
        submitSourceBtn.addEventListener('click', async () => {
            logStatus('正在處理音訊來源...', 'info');
            _disableButton(submitSourceBtn, '處理中...');
            _disableButton(startAnalysisBtn, '請稍候...', 'fas fa-spinner fa-spin');

            try {
                let response;
                let data;
                if (currentSourceType === 'youtube') {
                    const url = youtubeUrlInput.value.trim();
                    if (!url) {
                        logStatus('請輸入 YouTube 網址。', 'warning');
                        throw new Error('No YouTube URL provided.');
                    }
                    if (!url.startsWith('http')) {
                        logStatus('無效的 YouTube 網址。請輸入完整的 URL (http/https 開頭)。', 'error');
                        throw new Error('Invalid YouTube URL format.');
                    }
                    console.debug("[SourceSubmit] 提交 YouTube URL:", url);
                    response = await fetch('/api/process_youtube_url', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url: url })
                    });
                    data = await response.json();
                } else { // upload
                    const file = audioFileInput.files[0];
                    if (!file) {
                        logStatus('請選擇一個音訊檔案。', 'warning');
                        throw new Error('No audio file selected.');
                    }
                    const formData = new FormData();
                    formData.append('audio_file', file);
                    console.debug("[SourceSubmit] 提交音訊檔案:", file.name);
                    response = await fetch('/api/upload_audio_file', {
                        method: 'POST',
                        body: formData
                    });
                    data = await response.json();
                }

                if (!response.ok) {
                    console.error(`[SourceSubmit] API 請求失敗。狀態: ${response.status}`, "完整回應:", data);
                    let errorMsg = `音訊來源處理失敗 (狀態: ${response.status})`;
                    if (data && data.detail) {
                        if (typeof data.detail === 'string') {
                            errorMsg += `: ${data.detail}`;
                        } else if (Array.isArray(data.detail)) {
                            // Pydantic validation errors
                            errorMsg += ":\n" + data.detail.map(err => {
                                const loc = err.loc ? err.loc.join(' -> ') : '未知位置';
                                return `欄位 '${loc}': ${err.msg}`;
                            }).join(';\n');
                        } else {
                            errorMsg += `: ${JSON.stringify(data.detail)}`;
                        }
                    }
                    throw new Error(errorMsg);
                }

                currentSelectedAudioPath = data.processed_audio_path;
                logStatus(`音訊來源處理成功: ${data.message}`, 'success');
                _showSection(configSection); // 顯示設定區塊
                if (configSection) configSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                _enableButton(startAnalysisBtn, '開始分析', 'fas fa-magic'); // 處理成功後啟用分析按鈕
            } catch (error) {
                console.error("[SourceSubmit] 處理音訊來源時發生捕捉到的錯誤:", error);
                logStatus(`處理音訊來源失敗: ${error.message}`, 'error', {clearExisting: false});
                _disableButton(startAnalysisBtn, '請先處理音訊來源', 'fas fa-hand-pointer');
            } finally {
                _enableButton(submitSourceBtn, currentSourceType === 'youtube' ? '處理 YouTube 網址' : '上傳音訊檔案', currentSourceType === 'youtube' ? 'fas fa-download' : 'fas fa-upload');
            }
        });
    }

    // API 金鑰管理
    async function checkApiKeyStatus() {
        logStatus('正在檢查 API 金鑰狀態...', 'info', {clearExisting: true});
        try {
            const response = await fetch('/api/check_api_key_status');
            if (!response.ok) {
                // 即使是非 2xx 狀態，也嘗試解析 JSON 獲取詳細資訊
                const errorData = await response.json().catch(() => ({}));
                console.error("[APIKeyStatus] 檢查 API 金鑰狀態失敗。狀態:", response.status, "回應:", errorData);
                throw new Error(errorData.message || `API 狀態檢查失敗 (狀態: ${response.status})`);
            }
            const data = await response.json();
            apiKeyStatusMessage.textContent = data.message;
            if (data.status === 'set_and_valid') {
                logStatus('API 金鑰狀態：已設定且有效。', 'success');
                apiKeyStatusMessage.style.color = 'var(--accent-color-green)';
                _hideSection(apiKeySection); // 有效則隱藏設定區
                loadAiModels(); // 金鑰有效後載入模型
            } else if (data.status === 'set_but_invalid') {
                logStatus('API 金鑰狀態：已設定但無效。請重新設定。', 'warning');
                apiKeyStatusMessage.style.color = 'var(--accent-color-yellow)';
                _showSection(apiKeySection); // 無效則顯示設定區
            } else { // not_set
                logStatus('API 金鑰狀態：尚未設定。請設定 API 金鑰。', 'warning');
                apiKeyStatusMessage.style.color = 'var(--text-color-secondary)';
                _showSection(apiKeySection); // 未設定則顯示設定區
            }
            console.debug("[APIKeyStatus] API 金鑰狀態:", data);
        } catch (error) {
            console.error("[APIKeyStatus] 檢查 API 金鑰時發生錯誤:", error);
            logStatus(`檢查 API 金鑰狀態失敗: ${error.message}`, 'error', {clearExisting: true});
            apiKeyStatusMessage.textContent = `檢查失敗: ${error.message}. 請嘗試重新載入頁面或檢查後端。`;
            apiKeyStatusMessage.style.color = 'var(--accent-color-red)';
            _showSection(apiKeySection); // 出錯也顯示設定區
        }
    }

    if (submitApiKeyBtn) {
        submitApiKeyBtn.addEventListener('click', async () => {
            const apiKey = apiKeyInput.value.trim();
            if (!apiKey) {
                logStatus('請輸入您的 Google API 金鑰。', 'warning');
                return;
            }
            logStatus('正在提交 API 金鑰並驗證...', 'info');
            _disableButton(submitApiKeyBtn, '驗證中...');

            try {
                const response = await fetch('/api/set_api_key', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ api_key: apiKey })
                });
                const data = await response.json();
                if (!response.ok) {
                    console.error("[APIKeySubmit] 提交 API 金鑰失敗。狀態:", response.status, "回應:", data);
                    let errorMsg = data.detail || `提交失敗 (狀態: ${response.status})`;
                    throw new Error(errorMsg);
                }
                logStatus(data.message, 'success');
                apiKeyStatusMessage.textContent = data.message;
                apiKeyStatusMessage.style.color = 'var(--accent-color-green)';
                _hideSection(apiKeySection); // 設定成功後隱藏
                loadAiModels(); // 設定成功後載入模型
            } catch (error) {
                console.error("[APIKeySubmit] 提交 API 金鑰時發生捕捉到的錯誤:", error);
                logStatus(`設定 API 金鑰失敗: ${error.message}`, 'error');
                apiKeyStatusMessage.textContent = `設定失敗: ${error.message}`;
                apiKeyStatusMessage.style.color = 'var(--accent-color-red)';
                _showSection(apiKeySection); // 失敗後繼續顯示設定區
            } finally {
                _enableButton(submitApiKeyBtn, '設定 API 金鑰', 'fas fa-key');
            }
        });
    }

    if (howToSetApiKeyBtn) {
        howToSetApiKeyBtn.addEventListener('click', () => {
            _showSection(apiKeyInstructionsModal);
            apiKeyInstructionsModal.focus(); // 聚焦模態視窗
        });
    }

    if (closeApiKeyModalBtn) {
        closeApiKeyModalBtn.addEventListener('click', () => {
            _hideSection(apiKeyInstructionsModal);
        });
    }

    // 當點擊模態視窗外部時關閉
    if (apiKeyInstructionsModal) {
        apiKeyInstructionsModal.addEventListener('click', (event) => {
            if (event.target === apiKeyInstructionsModal) {
                _hideSection(apiKeyInstructionsModal);
            }
        });
    }

    // --- Load AI Models (更新以處理新的豐富模型資料) ---
    async function loadAiModels() {
        logStatus('正在獲取 AI 模型列表...', 'info', {clearExisting: false});
        console.debug("[Models] 開始載入 AI 模型列表...");
        try {
            const response = await fetch('/api/get_models');
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({detail: `獲取模型列表 API 失敗 (狀態: ${response.status})`}));
                throw new Error(errorData.detail || `獲取模型列表 API 失敗 (狀態: ${response.status})`);
            }
            const models = await response.json();
            allModelsDataCache = models; // 快取完整模型資料

            if (aiModelSelect) {
                aiModelSelect.innerHTML = '<option value="">-- 請選擇 AI 模型 --</option>';
                // 檢查是否返回了錯誤模型 ID
                if (models && models.length > 0 && models[0].id === "error-api-key-or-network"){
                    aiModelSelect.innerHTML = `<option value="">${models[0].dropdown_display_name || 'API金鑰或網路問題'}</option>`;
                    displaySingleModelDetails(models[0]); // 顯示錯誤模型的詳細訊息
                    _showSection(modelInfoDisplay);
                    logStatus(models[0].dropdown_display_name || '無法載入模型：API金鑰或網路問題', 'error');
                    _disableButton(startAnalysisBtn, '請先解決模型問題', 'fas fa-exclamation-circle');
                    return; // 不再繼續填充
                }

                models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id; // API Name
                    option.textContent = model.dropdown_display_name || model.id.replace("models/", ""); // 用於下拉選單顯示的名稱
                    aiModelSelect.appendChild(option);
                });

                // 新增：模型選擇變更時，顯示詳細介紹
                aiModelSelect.addEventListener('change', (event) => {
                    const selectedModelId = event.target.value;
                    if (selectedModelId && modelInfoDisplay) {
                        const selectedModelData = allModelsDataCache.find(m => m.id === selectedModelId);
                        if (selectedModelData) {
                            displaySingleModelDetails(selectedModelData);
                            _showSection(modelInfoDisplay);
                        } else {
                            modelInfoDisplay.innerHTML = "<p>找不到所選模型的詳細資訊。</p>";
                            _showSection(modelInfoDisplay); // 仍然顯示，但提示找不到
                        }
                    } else if (modelInfoDisplay) {
                        _hideSection(modelInfoDisplay); // 如果選擇 "--請選擇--"
                    }
                });
                // 預設選中第一個模型並觸發顯示 (如果列表不為空且非錯誤)
                if (models.length > 0 && aiModelSelect.options.length > 1) { // 確保有實際的模型選項 (不包含預設的 "--請選擇--")
                    aiModelSelect.value = models[0].id;
                    aiModelSelect.dispatchEvent(new Event('change')); // 手動觸發 change 事件
                }
            }
            logStatus('AI 模型列表載入成功。', 'success', {clearExisting: false});
            console.debug("[Models] AI 模型列表載入成功:", models);
            // 只有當模型載入成功且有選中音訊路徑時，才啟用分析按鈕
            if (currentSelectedAudioPath && aiModelSelect.value && aiModelSelect.value !== "error-api-key-or-network") {
                _enableButton(startAnalysisBtn, '開始分析', 'fas fa-magic');
            } else {
                 _disableButton(startAnalysisBtn, '請先處理音訊來源', 'fas fa-hand-pointer');
            }

        } catch (error) {
            console.error("[Models] 載入 AI 模型時發生錯誤:", error);
            logStatus(`載入 AI 模型時發生錯誤: ${error.message}`, 'error', {clearExisting: false});
            if (aiModelSelect) aiModelSelect.innerHTML = '<option value="">模型載入失敗</option>';
            _hideSection(modelInfoDisplay);
            _disableButton(startAnalysisBtn, '模型載入失敗', 'fas fa-exclamation-circle');
        }
    }

    // 新增：顯示單一模型詳細介紹的函式
    function displaySingleModelDetails(modelData) {
        if (!modelInfoDisplay || !modelData) return;
        let html = `
            <p><strong>中文名稱：</strong> ${modelData.chinese_display_name || modelData.dropdown_display_name || modelData.id.replace("models/", "")}
                <span style="font-weight:normal; color:var(--text-color-secondary);">${modelData.chinese_summary_parenthesized || ''}</span></p>`;
        if (modelData.chinese_input_output) {
            html += `<p><strong>輸入/輸出能力：</strong> ${modelData.chinese_input_output}</p>`;
        }
        if (modelData.chinese_suitable_for) {
            html += `<p><strong>適合用途：</strong> ${modelData.chinese_suitable_for}</p>`;
        }
        if (modelData.original_description_from_api) {
            html += `<p style="font-size:0.85em; color:var(--text-color-tertiary); margin-top:8px;">
                                <strong>API 原始描述：</strong> ${modelData.original_description_from_api}
                            </p>`;
        }
        html += `<p style="font-size:0.8em; color:var(--text-color-tertiary); margin-top:10px;">模型 ID: ${modelData.id}</p>`;
        modelInfoDisplay.innerHTML = html;
    }

    // --- Task Queue Management ---
    // 任務佇列狀態顯示
    function updateTaskQueueDisplay(tasks) {
        if (!taskQueueContainer) return;
        taskQueueContainer.innerHTML = ''; // 清空現有列表

        if (tasks.length === 0) {
            taskQueueContainer.innerHTML = '<p class="status-message">目前沒有進行中的任務。</p>';
            _hideSection(taskQueueSection);
            return;
        }

        _showSection(taskQueueSection);

        tasks.forEach(task => {
            const taskElement = document.createElement('div');
            taskElement.classList.add('task-item', 'card');
            if (task.status === 'completed') {
                taskElement.classList.add('task-completed');
            } else if (task.status === 'failed') {
                taskElement.classList.add('task-failed');
            } else {
                taskElement.classList.add('task-processing');
            }

            let statusIcon = '';
            let statusText = '';
            let statusClass = '';

            switch (task.status) {
                case 'queued':
                    statusIcon = '<i class="fas fa-hourglass-start"></i>';
                    statusText = '佇列中';
                    statusClass = 'status-queued';
                    break;
                case 'processing':
                    statusIcon = '<i class="fas fa-spinner fa-spin"></i>';
                    statusText = '處理中';
                    statusClass = 'status-processing';
                    break;
                case 'completed':
                    statusIcon = '<i class="fas fa-check-circle"></i>';
                    statusText = '完成';
                    statusClass = 'status-completed';
                    break;
                case 'failed':
                    statusIcon = '<i class="fas fa-times-circle"></i>';
                    statusText = '失敗';
                    statusClass = 'status-failed';
                    break;
                default:
                    statusIcon = '<i class="fas fa-question-circle"></i>';
                    statusText = '未知狀態';
                    statusClass = 'status-unknown';
            }

            const submitTime = task.submit_time ? new Date(task.submit_time).toLocaleString('zh-TW', { hour12: false }) : 'N/A';
            const completionTime = task.completion_time ? new Date(task.completion_time).toLocaleString('zh-TW', { hour12: false }) : 'N/A';
            const startTime = task.start_time ? new Date(task.start_time).toLocaleString('zh-TW', { hour12: false }) : 'N/A';
            const taskIdShort = task.task_id.substring(0, 8);

            taskElement.innerHTML = `
                <div class="task-header">
                    <span class="task-title">任務 ID: ${taskIdShort} - ${task.source_name}</span>
                    <span class="task-status ${statusClass}">${statusIcon} ${statusText}</span>
                </div>
                <div class="task-details">
                    <p><strong>模型:</strong> ${task.model_id}</p>
                    <p><strong>提交時間:</strong> ${submitTime}</p>
                    <p><strong>開始時間:</strong> ${startTime}</p>
                    <p><strong>完成時間:</strong> ${completionTime}</p>
                    ${task.status === 'failed' && task.error_message ? `<p class="error-message"><strong>錯誤:</strong> ${task.error_message}</p>` : ''}
                    <div class="task-actions">
                        ${task.status === 'completed' ? `<button class="view-report-btn button-secondary" data-task-id="${task.task_id}"><i class="fas fa-eye"></i> 查看報告</button>` : ''}
                    </div>
                </div>
            `;
            taskQueueContainer.appendChild(taskElement);
        });
        attachViewReportListeners(); // 重新綁定事件監聽器
    }

    async function fetchTaskQueue() {
        try {
            const response = await fetch('/api/tasks');
            if (!response.ok) {
                throw new Error(`獲取任務佇列失敗 (狀態: ${response.status})`);
            }
            const tasks = await response.json();
            updateTaskQueueDisplay(tasks);

            // 如果所有任務都已完成或失敗，則停止輪詢
            const anyProcessingOrQueued = tasks.some(task => task.status === 'processing' || task.status === 'queued');
            if (!anyProcessingOrQueued && activePollingIntervalId) {
                clearInterval(activePollingIntervalId);
                activePollingIntervalId = null;
                console.debug("[Polling] 所有任務完成，輪詢已停止。");
                logStatus("所有任務已處理完成。", "success", {clearExisting: false});
            }
        } catch (error) {
            console.error("獲取任務佇列時發生錯誤:", error);
            logStatus(`獲取任務佇列失敗: ${error.message}`, 'error', {clearExisting: false});
            if (activePollingIntervalId) {
                clearInterval(activePollingIntervalId);
                activePollingIntervalId = null;
                console.debug("[Polling] 輪詢因錯誤停止。");
            }
        }
    }

    // 重新綁定查看報告按鈕的事件監聽器
    function attachViewReportListeners() {
        document.querySelectorAll('.view-report-btn').forEach(button => {
            // 避免重複綁定
            if (button.dataset.listenerAttached) return;
            button.dataset.listenerAttached = 'true';

            button.addEventListener('click', async (event) => {
                const taskId = event.currentTarget.dataset.taskId;
                logStatus(`正在載入任務 ${taskId.substring(0,8)} 的報告...`, 'info', {clearExisting: true});
                _disableButton(event.currentTarget, '載入中...', 'fas fa-sync-alt fa-spin');
                try {
                    const response = await fetch(`/api/tasks/${taskId}`);
                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({}));
                        throw new Error(errorData.detail || `載入報告失敗 (狀態: ${response.status})`);
                    }
                    const taskData = await response.json();

                    if (taskData.status === 'completed' && taskData.result_preview_html) {
                        currentResultTaskNameSpan.textContent = taskData.source_name;
                        reportOutputArea.innerHTML = taskData.result_preview_html;
                        downloadLinksDiv.innerHTML = ''; // 清空舊的下載連結

                        if (taskData.download_links) {
                            for (const format in taskData.download_links) {
                                const link = document.createElement('a');
                                link.href = taskData.download_links[format];
                                link.textContent = `下載 ${format.toUpperCase()} 報告`;
                                link.classList.add('button', 'button-secondary', 'download-link');
                                link.target = '_blank'; // 在新視窗打開
                                downloadLinksDiv.appendChild(link);
                            }
                        }
                        _showSection(resultSection);
                        resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        logStatus(`任務 ${taskId.substring(0,8)} 報告載入成功。`, 'success');
                    } else if (taskData.status === 'failed') {
                        logStatus(`任務 ${taskId.substring(0,8)} 失敗: ${taskData.error_message || '未知錯誤'}`, 'error');
                        _hideSection(resultSection);
                    } else {
                        logStatus(`任務 ${taskId.substring(0,8)} 尚未完成或結果不可用。`, 'warning');
                        _hideSection(resultSection);
                    }
                } catch (error) {
                    console.error("載入任務報告時發生錯誤:", error);
                    logStatus(`載入報告失敗: ${error.message}`, 'error');
                } finally {
                    _enableButton(event.currentTarget, '查看報告', 'fas fa-eye');
                }
            });
        });
    }


    // --- Start Analysis (startAnalysisBtn 點擊事件 - 包含修正) ---
    if (startAnalysisBtn) {
        startAnalysisBtn.addEventListener('click', async () => {
            console.debug("[AnalysisStart] 開始分析按鈕點擊。");
            if (!currentSelectedAudioPath) {
                logStatus('錯誤: 請先處理音訊來源 (上傳或下載 YouTube 音訊)。', 'error');
                return;
            }
            const selectedModel = aiModelSelect.value;
            const selectedMainOutputRadio = document.querySelector('input[name="main_output"]:checked');

            if (!selectedMainOutputRadio) {
                logStatus('錯誤: 請選擇主要的報告輸出類型 (如重點摘要或逐字稿)。', 'error');
                return;
            }
            if (!selectedModel || selectedModel === "" || selectedModel === "error-api-key-or-network") {
                logStatus('錯誤: 請選擇一個有效的 AI 模型，或解決 API 金鑰/網路問題。', 'error');
                return;
            }

            const selectedMainOutput = selectedMainOutputRadio.value;
            const selectedExtraFormats = Array.from(document.querySelectorAll('input[name="extra_format"]:checked')).map(cb => cb.value);
            const outputOptionsList = [selectedMainOutput, ...selectedExtraFormats];

            // ****** 修正 custom_prompts 的準備方式 - 只有當內容與預設值不同時才傳送 ******
            let customPromptsPayload = {}; // 初始化為空物件
            const summaryP_trimmed = customSummaryPromptInput.value.trim();
            const transcriptP_trimmed = customTranscriptPromptInput.value.trim();

            if (summaryP_trimmed !== DEFAULT_SUMMARY_PROMPT) {
                customPromptsPayload.summary_prompt = summaryP_trimmed;
            }
            if (transcriptP_trimmed !== DEFAULT_TRANSCRIPT_PROMPT) {
                customPromptsPayload.transcript_prompt = transcriptP_trimmed;
            }

            // 如果 customPromptsPayload 是空物件，表示沒有自訂提示詞，則將其設為 null
            if (Object.keys(customPromptsPayload).length === 0) {
                customPromptsPayload = null;
            }
            // **************************************************************************

            const requestBody = {
                source_type: currentSourceType,
                source_path: currentSelectedAudioPath,
                model_id: selectedModel,
                output_options: outputOptionsList,
                custom_prompts: customPromptsPayload
            };

            _showSection(taskQueueSection);
            if (taskQueueSection) taskQueueSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            logStatus('提交 AI 分析任務...', 'info');
            _disableButton(startAnalysisBtn, '提交中...');
            console.debug("[AnalysisStart] 提交請求內容:", JSON.stringify(requestBody, null, 2));

            try {
                const response = await fetch('/api/generate_report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestBody)
                });
                const result = await response.json();

                if (!response.ok) {
                    console.error(`[AnalysisStart] API 請求失敗。狀態: ${response.status}`, "完整回應:", result);
                    let readableError = `請求失敗 (狀態 ${response.status})`;
                    if (result.detail) {
                        if (Array.isArray(result.detail)) {
                            readableError = result.detail.map(err => {
                                const loc = err.loc ? err.loc.join(' -> ') : '位置未知';
                                return `欄位 '${loc}': ${err.msg} (類型: ${err.type || '未知'})`;
                            }).join('; \n'); // 使用換行符，logStatus 會處理
                        } else if (typeof result.detail === 'string') {
                            readableError = result.detail;
                        } else {
                            try { readableError = JSON.stringify(result.detail, null, 2); } // 嘗試格式化JSON
                            catch (e) { readableError = "無法解析的複雜錯誤詳情物件"; }
                        }
                    }
                    throw new Error(readableError);
                }
                logStatus(`任務 ${result.task_id} 已成功提交: ${result.message}`, 'success');
                console.info(`[AnalysisStart] 任務 ${result.task_id} 已提交。`);
                if (!activePollingIntervalId) {
                    fetchTaskQueue(); // 立即更新一次任務列表
                    activePollingIntervalId = setInterval(fetchTaskQueue, POLLING_INTERVAL);
                    console.debug("[Polling] 輪詢已啟動。");
                } else {
                    fetchTaskQueue(); // 如果已在輪詢，也立即更新一次
                }

            } catch (error) {
                console.error("[AnalysisStart] 提交 AI 分析任務時發生捕捉到的錯誤:", error);
                logStatus(`提交 AI 分析任務失敗: ${error.message.replace(/\n/g, '<br>')}`, 'error'); // 將換行符轉為 <br> 以在 HTML 中顯示
            } finally {
                _enableButton(startAnalysisBtn, '開始分析', 'fas fa-magic');
            }
        });
    }

    // --- Initial Setup ---
    function initializeApp() {
        console.info("[AppInit] AI_paper 應用程式初始化開始 (v2.4 - 優化版)。");
        if(statusLog) statusLog.innerHTML = '';
        logStatus("AI_paper 應用程式準備中...", "info");

        // ****** 設定預設提示詞為 textarea 的 value ******
        if(customSummaryPromptInput && DEFAULT_SUMMARY_PROMPT) {
            customSummaryPromptInput.value = DEFAULT_SUMMARY_PROMPT;
        }
        if(customTranscriptPromptInput && DEFAULT_TRANSCRIPT_PROMPT) {
            customTranscriptPromptInput.value = DEFAULT_TRANSCRIPT_PROMPT;
        }
        // *************************************************

        applyTheme(localStorage.getItem('theme') || 'dark-mode'); // 應用上次選擇的主題或預設主題
        applyFontSize(localStorage.getItem('fontSize') || 'default'); // 應用上次選擇的字體大小或預設大小

        checkApiKeyStatus(); // 這會處理 API 金鑰並決定是否顯示設定區，以及觸發 loadAiModels
        _hideSection(configSection);
        _hideSection(taskQueueSection);
        _hideSection(resultSection);
        _showSection(statusSection);

        // 如果 URL 中有 task_id 參數，則嘗試載入該任務的結果
        const urlParams = new URLSearchParams(window.location.search);
        const taskIdFromUrl = urlParams.get('task_id');
        if (taskIdFromUrl) {
            console.info(`[AppInit] 從 URL 載入任務 ID: ${taskIdFromUrl}`);
            // 這裡需要確保 fetchTaskQueue 和 attachViewReportListeners 在此之前已經定義
            // 並確保 reportOutputArea, downloadLinksDiv 等 DOM 元素已準備好
            // 由於任務資訊可能需要從後端獲取，此處可以先呼叫 fetchTaskQueue 一次，然後在更新完畢後檢查並載入
            // 一個更穩健的做法是，當 fetchTaskQueue 完成後，觸發一個事件，然後監聽此事件來載入特定任務。
            // 為了這個一次性腳本的簡單性，我們直接呼叫。
            setTimeout(() => { // 給 DOM 和其他初始化一點時間
                // 模擬點擊查看報告按鈕，如果該任務存在
                const fakeButton = document.createElement('button');
                fakeButton.dataset.taskId = taskIdFromUrl;
                // 需要一個臨時的父元素來模擬事件觸發，或者直接呼叫載入報告的內部函數
                // 這裡我們直接呼叫 fetchTaskStatusAndDisplayResult (如果有的話)
                fetchTaskStatusAndDisplayResult(taskIdFromUrl); // 假設有一個這樣的函數
            }, 500); // 延遲執行，確保 DOM 和函式已準備好

        }
        // 假設 fetchTaskStatusAndDisplayResult 是一個用於載入特定任務報告的函數
        async function fetchTaskStatusAndDisplayResult(taskId) {
            logStatus(`正在從 URL 載入任務 ${taskId.substring(0,8)} 的報告...`, 'info', {clearExisting: true});
            try {
                const response = await fetch(`/api/tasks/${taskId}`);
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.detail || `載入報告失敗 (狀態: ${response.status})`);
                }
                const taskData = await response.json();

                if (taskData.status === 'completed' && taskData.result_preview_html) {
                    currentResultTaskNameSpan.textContent = taskData.source_name;
                    reportOutputArea.innerHTML = taskData.result_preview_html;
                    downloadLinksDiv.innerHTML = ''; // 清空舊的下載連結

                    if (taskData.download_links) {
                        for (const format in taskData.download_links) {
                            const link = document.createElement('a');
                            link.href = taskData.download_links[format];
                            link.textContent = `下載 ${format.toUpperCase()} 報告`;
                            link.classList.add('button', 'button-secondary', 'download-link');
                            link.target = '_blank'; // 在新視窗打開
                            downloadLinksDiv.appendChild(link);
                        }
                    }
                    _showSection(resultSection);
                    resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    logStatus(`任務 ${taskId.substring(0,8)} 報告載入成功。`, 'success');
                } else if (taskData.status === 'failed') {
                    logStatus(`任務 ${taskId.substring(0,8)} 失敗: ${taskData.error_message || '未知錯誤'}`, 'error');
                    _hideSection(resultSection);
                } else {
                    logStatus(`任務 ${taskId.substring(0,8)} 尚未完成或結果不可用。`, 'warning');
                    _hideSection(resultSection);
                }
            } catch (error) {
                console.error("從 URL 載入任務報告時發生錯誤:", error);
                logStatus(`從 URL 載入報告失敗: ${error.message}`, 'error');
            }
        }
        fetchTaskQueue(); // 啟動時立即獲取一次任務列表
        activePollingIntervalId = setInterval(fetchTaskQueue, POLLING_INTERVAL); // 啟動輪詢

        console.info("[AppInit] AI_paper 應用程式初始化完成。");
        logStatus("AI_paper 應用程式已就緒。", "success");
    }

    initializeApp();
});

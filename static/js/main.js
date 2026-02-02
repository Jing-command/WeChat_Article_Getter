// WebSocket连接
let ws = null;
let isDownloading = false;
let isPaused = false;
let sessionId = null;

// DOM元素
const urlInput = document.getElementById('urlInput');
const activationKeyInput = document.getElementById('activationKeyInput');
const keyStatus = document.getElementById('keyStatus');
const credentialsInput = document.getElementById('credentialsInput');
const startBtn = document.getElementById('startBtn');
const pauseBtn = document.getElementById('pauseBtn');
const clearBtn = document.getElementById('clearBtn');
const singleMode = document.getElementById('singleMode');
const batchMode = document.getElementById('batchMode');
const dateMode = document.getElementById('dateMode');
const countInput = document.getElementById('countInput');
const countHint = document.getElementById('countHint');
const startDate = document.getElementById('startDate');
const endDate = document.getElementById('endDate');
const pathInput = document.getElementById('pathInput');
const logOutput = document.getElementById('logOutput');
const statusText = document.getElementById('statusText');

// 初始化
function init() {
    sessionId = getSessionId();
    connectWebSocket();
    setupEventListeners();
    updateCountHint();
}

// 获取或生成会话ID
function getSessionId() {
    let sid = localStorage.getItem('wechat_downloader_session');
    if (!sid) {
        sid = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
        localStorage.setItem('wechat_downloader_session', sid);
    }
    return sid;
}

// 连接WebSocket
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws?session_id=${encodeURIComponent(sessionId)}`);
    
    ws.onopen = () => {
        console.log('WebSocket连接已建立');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'log') {
            appendLog(data.message);
        } else if (data.type === 'download_complete') {
            handleDownloadComplete(data.key_used, data.zip_file);
        }
    };
    
    ws.onclose = () => {
        console.log('WebSocket连接已断开，5秒后重连...');
        setTimeout(connectWebSocket, 5000);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket错误:', error);
    };
}

// 设置事件监听
function setupEventListeners() {
    // 开始下载按钮
    startBtn.addEventListener('click', handleStartDownload);
    
    // 暂停按钮
    pauseBtn.addEventListener('click', handlePauseResume);

    // 清理按钮
    clearBtn.addEventListener('click', handleClearDownloads);
    
    // 下载模式复选框
    singleMode.addEventListener('change', handleSingleModeChange);
    batchMode.addEventListener('change', handleBatchModeChange);
    dateMode.addEventListener('change', handleDateModeChange);
    
    // 数量输入框
    countInput.addEventListener('input', updateCountHint);
    
    // 激活码输入框 - 实时验证
    activationKeyInput.addEventListener('input', debounce(verifyActivationKey, 500));
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 验证激活码
async function verifyActivationKey() {
    const key = activationKeyInput.value.trim();
    
    if (!key) {
        keyStatus.textContent = '';
        return;
    }
    
    // 显示验证中
    keyStatus.innerHTML = '<span style="color: #888;">验证中...</span>';
    
    try {
        const response = await fetch('/api/verify_key', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ activation_key: key })
        });
        
        const result = await response.json();
        
        if (result.valid) {
            keyStatus.innerHTML = `<span style="color: #10b981; font-weight: bold;">✓ ${result.message}</span>`;
        } else {
            keyStatus.innerHTML = `<span style="color: #ef4444; font-weight: bold;">✗ ${result.message}</span>`;
        }
    } catch (error) {
        keyStatus.innerHTML = '<span style="color: #ef4444;">验证失败</span>';
    }
}

// 处理单篇下载模式切换
function handleSingleModeChange() {
    if (singleMode.checked) {
        batchMode.checked = false;
        countInput.disabled = true;
        dateMode.checked = false;
        startDate.disabled = true;
        endDate.disabled = true;
    } else {
        batchMode.checked = true;
        countInput.disabled = false;
    }
}

// 处理批量下载模式切换
function handleBatchModeChange() {
    if (batchMode.checked) {
        singleMode.checked = false;
        if (!dateMode.checked) {
            countInput.disabled = false;
        }
    } else {
        singleMode.checked = true;
        countInput.disabled = true;
        dateMode.checked = false;
        startDate.disabled = true;
        endDate.disabled = true;
    }
}

// 处理日期模式切换
function handleDateModeChange() {
    if (dateMode.checked) {
        batchMode.checked = true;
        singleMode.checked = false;
        countInput.disabled = true;
        startDate.disabled = false;
        endDate.disabled = false;
    } else {
        if (batchMode.checked) {
            countInput.disabled = false;
        }
        startDate.disabled = true;
        endDate.disabled = true;
    }
}

// 更新数量提示
function updateCountHint() {
    const count = countInput.value || 10;
    countHint.textContent = `(将下载最近的${count}篇文章)`;
}

// 开始下载
async function handleStartDownload() {
    const url = urlInput.value.trim();
    if (!url) {
        alert('请输入公众号名称或文章链接');
        return;
    }
    
    const activationKey = activationKeyInput.value.trim();
    if (!activationKey) {
        alert('请输入激活码');
        return;
    }
    
    // 验证激活码格式
    if (!activationKey.match(/^[SB]-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}$/)) {
        alert('激活码格式不正确\n正确格式：S-XXXX-XXXX-XXXX-XXXX 或 B-XXXX-XXXX-XXXX-XXXX');
        return;
    }
    
    // 验证激活码类型与下载模式匹配
    const isBatchMode = batchMode.checked || dateMode.checked;
    const keyType = activationKey.charAt(0);
    
    if (isBatchMode && keyType !== 'B') {
        alert('批量下载（包括日期范围下载）需要使用 B- 开头的激活码');
        return;
    }
    
    if (!isBatchMode && keyType !== 'S') {
        alert('单次下载需要使用 S- 开头的激活码');
        return;
    }
    
    const credentials = credentialsInput.value.trim();
    if (!credentials) {
        alert('请输入登录凭证（Token 和 Cookies）');
        return;
    }
    
    const downloadPath = pathInput.value.trim();
    if (!downloadPath) {
        alert('请设置下载路径');
        return;
    }
    
    // 验证数量
    if (batchMode.checked && !dateMode.checked) {
        const count = parseInt(countInput.value);
        if (isNaN(count) || count <= 0) {
            alert('请输入有效的文章数量（正整数）');
            return;
        }
    }
    
    // 验证日期
    if (dateMode.checked) {
        const start = startDate.value;
        const end = endDate.value;
        if (!start || !end) {
            alert('请输入开始日期和结束日期');
            return;
        }
        if (start > end) {
            alert('开始日期不能晚于结束日期');
            return;
        }
    }
    
    const requestData = {
        session_id: sessionId,
        url: url,
        activation_key: activationKey,
        credentials: credentials,
        single_mode: singleMode.checked,
        batch_mode: batchMode.checked,
        date_mode: dateMode.checked,
        count: parseInt(countInput.value) || 10,
        start_date: startDate.value || null,
        end_date: endDate.value || null,
        download_path: downloadPath
    };
    
    startBtn.disabled = true;
    pauseBtn.disabled = false;
    clearBtn.disabled = true;
    isDownloading = true;
    updateStatus('● 下载中...');
    
    // 禁用下载按钮
    const downloadZipBtn = document.getElementById('downloadZipBtn');
    if (downloadZipBtn) {
        downloadZipBtn.disabled = true;
        downloadZipBtn.title = '下载完成之后才能下载压缩包';
    }
    
    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        
        if (!result.success) {
            alert('启动下载失败: ' + result.message);
            handleDownloadComplete();
        }
    } catch (error) {
        alert('下载请求失败: ' + error.message);
        handleDownloadComplete();
    }
}

// 暂停/恢复
async function handlePauseResume() {
    if (isPaused) {
        // 恢复
        pauseBtn.disabled = true;
        pauseBtn.textContent = '恢复中...';
        
        try {
            const response = await fetch('/api/resume', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ session_id: sessionId })
            });
            
            const result = await response.json();
            
            if (result.success) {
                isPaused = false;
                pauseBtn.textContent = '⏸ 暂停';
                clearBtn.disabled = true;
                updateStatus('● 下载中...');
            } else {
                alert('恢复失败: ' + result.message);
            }
        } catch (error) {
            alert('恢复请求失败: ' + error.message);
        } finally {
            pauseBtn.disabled = false;
        }
    } else {
        // 暂停
        try {
            const response = await fetch('/api/pause', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ session_id: sessionId })
            });
            
            const result = await response.json();
            
            if (result.success) {
                isPaused = true;
                pauseBtn.textContent = '▶ 恢复';
                clearBtn.disabled = false;
                updateStatus('⏸ 已暂停');
            } else {
                alert('暂停失败: ' + result.message);
            }
        } catch (error) {
            alert('暂停请求失败: ' + error.message);
        }
    }
}

// 清理已下载并重置
async function handleClearDownloads() {
    if (!isPaused) {
        alert('请先暂停下载');
        return;
    }

    const confirmDelete = confirm('确定要删除已下载的文件并重置任务吗？\n\n此操作不可恢复。');
    if (!confirmDelete) return;

    clearBtn.disabled = true;

    try {
        const response = await fetch('/api/clear_downloads', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ session_id: sessionId })
        });
        const result = await response.json();

        if (result.success) {
            appendLog('[SUCCESS] 已清理已下载文件，任务已重置');
            handleDownloadComplete(false, null);
        } else {
            alert('清理失败: ' + result.message);
            clearBtn.disabled = false;
        }
    } catch (error) {
        alert('清理请求失败: ' + error.message);
        clearBtn.disabled = false;
    }
}

// 下载完成
function handleDownloadComplete(keyUsed, zipFile) {
    isDownloading = false;
    isPaused = false;
    startBtn.disabled = false;
    pauseBtn.disabled = true;
    clearBtn.disabled = true;
    pauseBtn.textContent = '⏸ 暂停';
    updateStatus('● 就绪');
    
    // 如果有ZIP文件，显示下载按钮
    if (zipFile) {
        showDownloadButton(zipFile);
    }
    
    // 如果激活码已使用，弹出提示
    if (keyUsed) {
        setTimeout(() => {
            const message = zipFile 
                ? '✅ 下载完成！文件已打包，请点击下载按钮保存到本地。\n\n⚠️  当前激活码已失效，如需继续下载请更换新的激活码。'
                : '✅ 下载完成！\n\n⚠️  当前激活码已失效，如需继续下载请更换新的激活码。';
            alert(message);
            // 清空激活码输入框，提示用户输入新激活码
            activationKeyInput.value = '';
            activationKeyInput.focus();
        }, 500);
    }
}

// 显示下载按钮
function showDownloadButton(zipFile) {
    // 获取已存在的下载按钮
    const downloadBtn = document.getElementById('downloadZipBtn');
    if (downloadBtn) {
        // 启用按钮并更新提示
        downloadBtn.disabled = false;
        downloadBtn.title = '点击下载压缩包到本地';
        downloadBtn.onclick = () => {
            window.location.href = `/api/download_file/${zipFile}`;
            appendLog('[INFO] 开始下载文件...');
        };
    }
    
    // 添加日志提示
    appendLog('[SUCCESS] 💾 点击"下载文件到本地"按钮保存文件');
}

// 添加日志
function appendLog(message) {
    const line = document.createElement('div');
    line.className = 'log-line';
    
    // 根据消息类型设置样式
    if (message.includes('[SUCCESS]') || message.includes('完成')) {
        line.classList.add('success');
    } else if (message.includes('[ERROR]') || message.includes('[FATAL]')) {
        line.classList.add('error');
    } else if (message.includes('[WARN]')) {
        line.classList.add('warning');
    } else if (message.includes('[INFO]') || message.includes('[TASK]')) {
        line.classList.add('info');
    }
    
    line.textContent = message;
    logOutput.appendChild(line);
    
    // 自动滚动到底部
    logOutput.scrollTop = logOutput.scrollHeight;
}

// 更新状态
function updateStatus(status) {
    statusText.textContent = status;
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);

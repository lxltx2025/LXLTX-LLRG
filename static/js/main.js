/**
 * 综述生成系统 v2.3 - 前端脚本
 * 修复 TypeError 和引用统计问题
 */

// ==================== 全局错误捕获 ====================
window.onerror = function(message, source, lineno, colno, error) {
    console.warn('全局错误捕获:', message, source, lineno, colno);
    // 不阻止页面继续运行
    return false;
};

window.addEventListener('unhandledrejection', function(event) {
    console.warn('未处理的Promise拒绝:', event.reason);
});

// ==================== 全局状态 ====================
const AppState = {
    socket: null,
    currentModel: null,
    currentStep: 1,
    completedSteps: new Set(),
    reviewFiles: new Map(),
    litFiles: new Map(),
    currentParadigm: '',
    currentFramework: '',
    currentContent: '',
    selectedExportFormat: 'docx',
    reviewTopic: '',
    citationFormat: 'gb',
    literatureList: [],
    poolStatus: {
        file_count: 0,
        processed_count: 0,
        citation_count: 0,
        is_processing: false,
        is_processed: false,
        has_error: false,
        error_message: null,
        can_generate: false
    },
    // 新增：引用统计
    citationStats: {
        totalRefs: 0,      // 用户上传的文献总数
        citedRefs: 0,      // 已引用的文献数（去重）
        citationCount: 0   // 引用次数（总计）
    }
};

// ==================== 安全工具函数 ====================

/**
 * 安全获取字符串的小写形式
 * @param {*} value - 任意值
 * @param {string} defaultValue - 默认值
 * @returns {string}
 */
function safeToLowerCase(value, defaultValue = '') {
    if (value === null || value === undefined) {
        return defaultValue;
    }
    if (typeof value === 'string') {
        return value.toLowerCase();
    }
    return String(value).toLowerCase();
}

/**
 * 安全获取字符串
 * @param {*} value - 任意值
 * @param {string} defaultValue - 默认值
 * @returns {string}
 */
function safeString(value, defaultValue = '') {
    if (value === null || value === undefined) {
        return defaultValue;
    }
    if (typeof value === 'string') {
        return value;
    }
    return String(value);
}

/**
 * 安全访问对象属性
 * @param {object} obj - 对象
 * @param {string} path - 属性路径，如 'a.b.c'
 * @param {*} defaultValue - 默认值
 * @returns {*}
 */
function safeGet(obj, path, defaultValue = undefined) {
    if (!obj || typeof obj !== 'object') {
        return defaultValue;
    }
    
    const keys = path.split('.');
    let result = obj;
    
    for (const key of keys) {
        if (result === null || result === undefined || typeof result !== 'object') {
            return defaultValue;
        }
        result = result[key];
    }
    
    return result !== undefined ? result : defaultValue;
}

/**
 * HTML转义
 */
function escapeHtml(text) {
    if (text === null || text === undefined) {
        return '';
    }
    const str = typeof text === 'string' ? text : String(text);
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/**
 * 格式化文件大小
 */
function formatFileSize(bytes) {
    if (typeof bytes !== 'number' || isNaN(bytes)) {
        return '0 B';
    }
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * Toast通知
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const icons = { info: 'ℹ️', success: '✅', error: '❌', warning: '⚠️' };
    const safeMessage = escapeHtml(safeString(message, ''));
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${safeMessage}</span>`;
    
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('removing');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 300);
    }, 3000);
}

/**
 * 按钮状态控制
 */
function enableButton(buttonId) {
    const btn = document.getElementById(buttonId);
    if (btn) btn.disabled = false;
}

function disableButton(buttonId) {
    const btn = document.getElementById(buttonId);
    if (btn) btn.disabled = true;
}

function setButtonLoading(buttonId, loading) {
    const btn = document.getElementById(buttonId);
    if (!btn) return;
    
    if (loading) {
        btn.classList.add('loading');
        btn.disabled = true;
    } else {
        btn.classList.remove('loading');
    }
}

/**
 * 内容追加
 */
function appendToElement(elementId, text) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const placeholder = element.querySelector('.placeholder-text');
    if (placeholder) placeholder.remove();

    const safeText = safeString(text, '');
    element.textContent += safeText;
    element.scrollTop = element.scrollHeight;
}

/**
 * 清空元素
 */
function clearElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '<p class="placeholder-text">等待内容生成...</p>';
    }
}

// ==================== 引用统计计算（核心修复） ====================

/**
 * 计算引用统计
 * @param {string} content - 综述内容
 * @param {number} maxValidIndex - 最大有效引用索引
 * @returns {object} - {citedRefs, citationCount, citedIndices}
 */
function calculateCitationStats(content, maxValidIndex) {
    const stats = {
        citedRefs: 0,
        citationCount: 0,
        citedIndices: []
    };
    
    // 安全检查
    const safeContent = safeString(content, '');
    const safeMaxIndex = typeof maxValidIndex === 'number' ? maxValidIndex : 0;
    
    if (!safeContent || safeMaxIndex <= 0) {
        return stats;
    }
    
    // 匹配所有 [数字] 格式的引用
    const citationPattern = /\[(\d+)\]/g;
    const matches = safeContent.match(citationPattern);
    
    if (!matches || matches.length === 0) {
        return stats;
    }
    
    // 统计引用
    const citedSet = new Set();
    let validCitationCount = 0;
    
    matches.forEach(match => {
        // 提取数字
        const numMatch = match.match(/\d+/);
        if (numMatch) {
            const index = parseInt(numMatch[0], 10);
            // 只统计有效范围内的引用
            if (index >= 1 && index <= safeMaxIndex) {
                citedSet.add(index);
                validCitationCount++;
            }
        }
    });
    
    stats.citedRefs = citedSet.size;
    stats.citationCount = validCitationCount;
    stats.citedIndices = Array.from(citedSet).sort((a, b) => a - b);
    
    return stats;
}

/**
 * 更新引用统计并保存到状态
 */
function updateAndSaveCitationStats() {
    const content = safeString(AppState.currentContent, '');
    const totalRefs = Array.isArray(AppState.literatureList) ? AppState.literatureList.length : 0;
    
    // 计算统计
    const stats = calculateCitationStats(content, totalRefs);
    
    // 保存到状态
    AppState.citationStats = {
        totalRefs: totalRefs,
        citedRefs: stats.citedRefs,
        citationCount: stats.citationCount
    };
    
    console.log('引用统计已更新:', AppState.citationStats);
    
    return stats;
}

/**
 * 更新引用统计UI显示
 */
function updateCitationStatsUI() {
    const statsContainer = document.getElementById('citation-stats');
    const totalRefsEl = document.getElementById('stat-total-refs');
    const citedRefsEl = document.getElementById('stat-cited-refs');
    const citationCountEl = document.getElementById('stat-citation-count');
    
    // 先计算最新统计
    const stats = updateAndSaveCitationStats();
    const totalRefs = AppState.citationStats.totalRefs;
    
    // 更新UI
    if (totalRefsEl) {
        totalRefsEl.textContent = totalRefs;
    }
    if (citedRefsEl) {
        citedRefsEl.textContent = stats.citedRefs;
    }
    if (citationCountEl) {
        citationCountEl.textContent = stats.citationCount;
    }
    
    // 显示/隐藏统计容器
    if (statsContainer) {
        const hasContent = !!AppState.currentContent;
        if (hasContent || totalRefs > 0) {
            statsContainer.style.display = 'block';
        } else {
            statsContainer.style.display = 'none';
        }
    }
    
    // 更新备注信息
    updateCitationNote(stats, totalRefs);
}

/**
 * 更新引用备注
 */
function updateCitationNote(stats, totalRefs) {
    const noteEl = document.getElementById('citation-note');
    if (!noteEl) return;
    
    if (!AppState.currentContent) {
        noteEl.textContent = '请先生成综述内容';
        noteEl.className = 'stats-note pending';
    } else if (stats.citationCount === 0) {
        noteEl.textContent = '本次生成内容未引用任何文献';
        noteEl.className = 'stats-note warning';
    } else {
        noteEl.textContent = `所有 ${stats.citationCount} 次引用均来自您上传的 ${totalRefs} 篇文献`;
        noteEl.className = 'stats-note success';
    }
}

// ==================== 文献列表渲染 ====================

function renderLiteratureList() {
    const citableList = document.getElementById('citable-list');
    const citableItems = document.getElementById('citable-items');
    
    if (!citableList || !citableItems) return;
    
    const list = AppState.literatureList;
    
    if (!Array.isArray(list) || list.length === 0) {
        citableList.style.display = 'none';
        return;
    }
    
    citableList.style.display = 'block';
    
    citableItems.innerHTML = list.map(lit => {
        const index = safeGet(lit, 'index', '?');
        const title = escapeHtml(safeGet(lit, 'title', '未知标题'));
        const authors = escapeHtml(safeGet(lit, 'authors', '未知作者'));
        const year = safeGet(lit, 'year', 'n.d.');
        
        return `
            <div class="citable-item">
                <span class="citable-index">${index}</span>
                <span class="citable-title">${title}</span>
                <span class="citable-meta">${authors} (${year})</span>
            </div>
        `;
    }).join('');
}

function renderLitFileList() {
    const container = document.getElementById('lit-file-list');
    if (!container) return;
    
    if (AppState.litFiles.size === 0) {
        container.innerHTML = '<p class="empty-text">暂未上传文献</p>';
        return;
    }
    
    let html = '';
    AppState.litFiles.forEach((file, id) => {
        const format = safeToLowerCase(safeGet(file, 'format', ''), 'unknown');
        const icon = format === 'pdf' ? '📕' : '📄';
        const filename = escapeHtml(safeGet(file, 'filename', '未知文件'));
        
        html += `
            <div class="lit-file-item" data-id="${escapeHtml(id)}">
                <div class="lit-file-info">
                    <span class="lit-file-icon">${icon}</span>
                    <span class="lit-file-name" title="${filename}">${filename}</span>
                </div>
                <button class="lit-file-remove" onclick="removeFile('literature', '${escapeHtml(id)}')" title="删除">✕</button>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function renderFileList(type) {
    if (type === 'literature') {
        renderLitFileList();
        return;
    }
    
    const container = document.getElementById('review-file-list');
    if (!container) return;

    if (AppState.reviewFiles.size === 0) {
        container.innerHTML = '<p class="empty-text">暂无文件</p>';
        return;
    }

    let html = '';
    AppState.reviewFiles.forEach((file, id) => {
        const format = safeToLowerCase(safeGet(file, 'format', ''), 'unknown');
        const icon = format === 'pdf' ? '📕' : '📄';
        const filename = escapeHtml(safeGet(file, 'filename', '未知文件'));
        const size = formatFileSize(safeGet(file, 'size', 0));
        const formatUpper = format.toUpperCase();
        
        html += `
            <div class="file-item" data-id="${escapeHtml(id)}" data-type="review">
                <div class="file-item-info">
                    <span class="file-icon">${icon}</span>
                    <div class="file-details">
                        <div class="file-name" title="${filename}">${filename}</div>
                        <div class="file-meta">${size} · ${formatUpper}</div>
                    </div>
                </div>
                <button class="file-remove" onclick="removeFile('review', '${escapeHtml(id)}')" title="删除">✕</button>
            </div>
        `;
    });

    container.innerHTML = html;
}

function renderReferencesOutput() {
    const output = document.getElementById('references-output');
    if (!output) return;
    
    const list = AppState.literatureList;
    
    if (!Array.isArray(list) || list.length === 0) {
        output.innerHTML = '<p class="placeholder-text">未上传参考文献</p>';
        return;
    }
    
    let html = `<div class="refs-header"><p>以下 ${list.length} 篇参考文献均来自您的上传：</p></div>`;
    
    html += list.map(lit => {
        const index = safeGet(lit, 'index', '?');
        const authors = escapeHtml(safeGet(lit, 'authors', '未知作者'));
        const year = safeGet(lit, 'year', 'n.d.');
        const title = escapeHtml(safeGet(lit, 'title', '未知标题'));
        
        return `
            <div class="ref-item">
                <span class="ref-index">[${index}]</span>
                ${authors} (${year}). ${title}.
            </div>
        `;
    }).join('');
    
    output.innerHTML = html;
}

// ==================== 文献池状态UI更新 ====================

function updateLiteratureStatusUI() {
    const status = AppState.poolStatus || {};
    const processStatus = document.getElementById('lit-process-status');
    const statusContent = document.getElementById('process-status-content');
    const progressEl = document.getElementById('process-progress');
    const citableList = document.getElementById('citable-list');
    const countBadge = document.getElementById('lit-count-badge');
    const citationNotice = document.getElementById('citation-notice');
    
    if (!processStatus) return;
    
    processStatus.classList.remove('processing', 'ready', 'error');
    
    const fileCount = safeGet(status, 'file_count', 0);
    const isProcessing = safeGet(status, 'is_processing', false);
    const hasError = safeGet(status, 'has_error', false);
    const isProcessed = safeGet(status, 'is_processed', false);
    const citationCount = safeGet(status, 'citation_count', 0);
    
    let icon = '📭';
    let text = '等待上传文献';
    
    if (fileCount === 0) {
        icon = '📭';
        text = '等待上传文献';
        if (citableList) citableList.style.display = 'none';
        if (progressEl) progressEl.style.display = 'none';
    } else if (isProcessing) {
        processStatus.classList.add('processing');
        icon = '⏳';
        text = '正在分析文献...';
        if (progressEl) progressEl.style.display = 'block';
    } else if (hasError) {
        processStatus.classList.add('error');
        icon = '❌';
        text = '分析失败，请重试';
        if (progressEl) progressEl.style.display = 'none';
    } else if (isProcessed && citationCount > 0) {
        processStatus.classList.add('ready');
        icon = '✅';
        text = `${citationCount}篇文献可引用`;
        if (citableList) citableList.style.display = 'block';
        if (progressEl) progressEl.style.display = 'none';
        renderLiteratureList();
    } else if (fileCount > 0 && !isProcessed) {
        icon = '📋';
        text = `${fileCount}个文件待分析`;
    }
    
    if (statusContent) {
        statusContent.innerHTML = `
            <span class="process-icon">${icon}</span>
            <span class="process-text">${text}</span>
        `;
    }
    
    if (countBadge) {
        countBadge.textContent = `${citationCount}篇`;
    }
    
    if (citationNotice) {
        if (citationCount > 0 && isProcessed) {
            citationNotice.style.display = 'block';
            const noticeCount = document.getElementById('notice-count');
            if (noticeCount) noticeCount.textContent = citationCount;
        } else {
            citationNotice.style.display = 'none';
        }
    }
}

// ==================== 按钮状态更新 ====================

function updateAllButtonStates() {
    const topicEl = document.getElementById('review-topic');
    const topic = topicEl ? safeString(topicEl.value, '').trim() : '';
    const hasTopic = topic.length >= 5;
    const hasParadigm = !!AppState.currentParadigm;
    const hasModel = !!AppState.currentModel;
    const pool = AppState.poolStatus || {};
    
    const fileCount = safeGet(pool, 'file_count', 0);
    const isProcessing = safeGet(pool, 'is_processing', false);
    const isProcessed = safeGet(pool, 'is_processed', false);
    const hasError = safeGet(pool, 'has_error', false);
    
    // 分析按钮
    const analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn && !analyzeBtn.classList.contains('loading')) {
        analyzeBtn.disabled = AppState.reviewFiles.size === 0 || !hasModel;
    }
    
    // 生成按钮
    const frameworkBtn = document.getElementById('generate-framework-btn');
    const contentBtn = document.getElementById('generate-content-btn');
    
    let canGenerate = hasModel && hasParadigm && hasTopic;
    
    if (fileCount > 0) {
        canGenerate = canGenerate && isProcessed && !isProcessing && !hasError;
    }
    
    if (frameworkBtn && !frameworkBtn.classList.contains('loading')) {
        frameworkBtn.disabled = !canGenerate;
    }
    if (contentBtn && !contentBtn.classList.contains('loading')) {
        contentBtn.disabled = !canGenerate;
    }
    
    updateActionStatus(hasModel, hasParadigm, hasTopic, pool, canGenerate);
}

function updateActionStatus(hasModel, hasParadigm, hasTopic, pool, canGenerate) {
    const actionStatus = document.getElementById('action-status');
    const statusIcon = document.getElementById('action-status-icon');
    const statusText = document.getElementById('action-status-text');
    
    if (!actionStatus || !statusIcon || !statusText) return;
    
    actionStatus.classList.remove('ready', 'warning', 'error');
    
    const fileCount = safeGet(pool, 'file_count', 0);
    const isProcessing = safeGet(pool, 'is_processing', false);
    const isProcessed = safeGet(pool, 'is_processed', false);
    const hasError = safeGet(pool, 'has_error', false);
    const citationCount = safeGet(pool, 'citation_count', 0);
    
    if (!hasModel) {
        statusIcon.textContent = '⚠️';
        statusText.textContent = '请先选择AI模型（步骤1）';
        actionStatus.classList.add('warning');
    } else if (!hasParadigm) {
        statusIcon.textContent = '⚠️';
        statusText.textContent = '请先完成写作范式分析（步骤2）';
        actionStatus.classList.add('warning');
    } else if (!hasTopic) {
        statusIcon.textContent = '✏️';
        statusText.textContent = '请输入综述主题（至少5个字符）';
        actionStatus.classList.add('warning');
    } else if (fileCount > 0 && isProcessing) {
        statusIcon.textContent = '⏳';
        statusText.textContent = '正在分析参考文献...';
        actionStatus.classList.add('warning');
    } else if (fileCount > 0 && hasError) {
        statusIcon.textContent = '❌';
        statusText.textContent = '文献分析失败，请重新上传';
        actionStatus.classList.add('error');
    } else if (fileCount > 0 && !isProcessed) {
        statusIcon.textContent = '📋';
        statusText.textContent = '等待参考文献分析完成';
        actionStatus.classList.add('warning');
    } else if (canGenerate) {
        statusIcon.textContent = '✅';
        if (citationCount > 0) {
            statusText.textContent = `准备就绪！可引用${citationCount}篇文献`;
        } else {
            statusText.textContent = '准备就绪！点击按钮开始生成';
        }
        actionStatus.classList.add('ready');
    }
}

// ==================== 进度条 ====================

function showProgress(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        container.style.display = 'block';
        const fill = container.querySelector('.progress-fill');
        const percentage = container.querySelector('.progress-percentage');
        const status = container.querySelector('.progress-status');
        if (fill) fill.style.width = '0%';
        if (percentage) percentage.textContent = '0%';
        if (status) status.textContent = '准备中...';
    }
}

function hideProgress(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        container.style.display = 'none';
    }
}

function hideAllProgress() {
    ['analyze-progress', 'generate-progress', 'process-progress'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
}

function updateProgress(data) {
    if (!data) return;
    
    const percentage = safeGet(data, 'percentage', 0);
    const message = safeString(safeGet(data, 'message', ''), '处理中...');
    
    const containers = document.querySelectorAll('.progress-container');
    containers.forEach(container => {
        if (container.style.display !== 'none') {
            const fill = container.querySelector('.progress-fill');
            const percentageEl = container.querySelector('.progress-percentage');
            const status = container.querySelector('.progress-status');
            
            if (fill) fill.style.width = `${percentage}%`;
            if (percentageEl) percentageEl.textContent = `${percentage}%`;
            if (status) status.textContent = message;
        }
    });
    
    const miniFill = document.getElementById('mini-progress-fill');
    if (miniFill) {
        miniFill.style.width = `${percentage}%`;
    }
}

// ==================== 文献池状态获取 ====================

async function fetchPoolStatus() {
    try {
        const response = await fetch('/api/literature-pool/status');
        const data = await response.json();
        
        if (data && data.success) {
            AppState.poolStatus = data;
            AppState.literatureList = Array.isArray(data.literature_list) ? data.literature_list : [];
            updateLiteratureStatusUI();
            renderLiteratureList();
            updateAllButtonStates();
        }
    } catch (error) {
        console.error('获取文献池状态失败:', error);
    }
}

// ==================== 输出标签页切换 ====================

function switchOutputTab(targetId) {
    if (!targetId) return;
    
    document.querySelectorAll('.output-tab').forEach(tab => {
        const tabTarget = safeGet(tab, 'dataset.target', '');
        tab.classList.toggle('active', tabTarget === targetId);
    });

    document.querySelectorAll('.output-pane').forEach(pane => {
        const paneId = pane.id || '';
        const isTarget = 
            (targetId === 'framework-output' && paneId === 'framework-pane') ||
            (targetId === 'content-output' && paneId === 'content-pane') ||
            (targetId === 'references-output' && paneId === 'references-pane');
        pane.classList.toggle('active', isTarget);
    });
}

// ==================== Socket.IO ====================

function initSocket() {
    try {
        AppState.socket = io();
    } catch (e) {
        console.error('Socket.IO初始化失败:', e);
        showToast('连接服务器失败', 'error');
        return;
    }
    
    const socket = AppState.socket;

    socket.on('connect', () => {
        console.log('已连接到服务器');
        fetchPoolStatus();
    });

    socket.on('disconnect', () => {
        showToast('与服务器断开连接', 'error');
    });

    socket.on('status', (data) => {
        const message = safeGet(data, 'message', '');
        if (message) showToast(message, 'info');
    });

    socket.on('error', (data) => {
        const message = safeGet(data, 'message', '发生错误');
        showToast(message, 'error');
        hideAllProgress();
        setButtonLoading('generate-framework-btn', false);
        setButtonLoading('generate-content-btn', false);
        setButtonLoading('refine-btn', false);
        setButtonLoading('analyze-btn', false);
        updateAllButtonStates();
    });

    socket.on('pool_status_update', (data) => {
        if (data) {
            AppState.poolStatus = data;
            updateLiteratureStatusUI();
            updateAllButtonStates();
        }
    });

    socket.on('progress_update', (data) => {
        updateProgress(data);
    });

    socket.on('step_update', (data) => {
        if (data) {
            AppState.currentStep = safeGet(data, 'current_step', 1);
            const completedSteps = safeGet(data, 'completed_steps', []);
            AppState.completedSteps = new Set(Array.isArray(completedSteps) ? completedSteps : []);
            updateStepIndicator();
        }
    });

    // 范式分析
    socket.on('paradigm_chunk', (data) => {
        const chunk = safeGet(data, 'chunk', '');
        appendToElement('paradigm-output', chunk);
    });

    socket.on('paradigm_complete', (data) => {
        AppState.currentParadigm = safeGet(data, 'paradigm', '');
        const resultEl = document.getElementById('paradigm-result');
        if (resultEl) resultEl.style.display = 'block';
        hideProgress('analyze-progress');
        setButtonLoading('analyze-btn', false);
        showToast(safeGet(data, 'message', '分析完成'), 'success');
        enableButton('step2-next');
        updateAllButtonStates();
    });

    // 文献处理完成
    socket.on('literature_processed', (data) => {
        if (data && data.success) {
            AppState.literatureList = Array.isArray(data.literature_list) ? data.literature_list : [];
            AppState.poolStatus = data.pool_status || AppState.poolStatus;
            renderLiteratureList();
            updateLiteratureStatusUI();
            showToast(safeGet(data, 'message', '处理完成'), 'success');
        }
        hideProgress('process-progress');
        updateAllButtonStates();
    });

    // 框架生成
    socket.on('framework_chunk', (data) => {
        const chunk = safeGet(data, 'chunk', '');
        appendToElement('framework-output', chunk);
    });

    socket.on('framework_complete', (data) => {
        AppState.currentFramework = safeGet(data, 'framework', '');
        hideProgress('generate-progress');
        setButtonLoading('generate-framework-btn', false);
        showToast(safeGet(data, 'message', '框架生成完成'), 'success');
        switchOutputTab('framework-output');
        
        const litList = safeGet(data, 'literature_list', null);
        if (Array.isArray(litList)) {
            AppState.literatureList = litList;
            renderLiteratureList();
        }
        
        const poolStatus = safeGet(data, 'pool_status', null);
        if (poolStatus) {
            AppState.poolStatus = poolStatus;
            updateLiteratureStatusUI();
        }
        
        updateAllButtonStates();
    });

    // 内容生成
    socket.on('section_chunk', (data) => {
        const chunk = safeGet(data, 'chunk', '');
        appendToElement('content-output', chunk);
    });

    socket.on('section_complete', (data) => {
        // 保存生成的内容
        AppState.currentContent = safeGet(data, 'content', '');
        
        hideProgress('generate-progress');
        setButtonLoading('generate-content-btn', false);
        showToast(safeGet(data, 'message', '内容生成完成'), 'success');
        switchOutputTab('content-output');
        enableButton('step3-next');
        
        const litList = safeGet(data, 'literature_list', null);
        if (Array.isArray(litList)) {
            AppState.literatureList = litList;
            renderLiteratureList();
            renderReferencesOutput();
        }
        
        const poolStatus = safeGet(data, 'pool_status', null);
        if (poolStatus) {
            AppState.poolStatus = poolStatus;
            updateLiteratureStatusUI();
        }
        
        // 立即计算并更新引用统计
        updateAndSaveCitationStats();
        updateCitationStatsUI();
        
        updateAllButtonStates();
    });

    // 内容优化
    socket.on('refine_chunk', (data) => {
        const chunk = safeGet(data, 'chunk', '');
        appendToElement('content-output', chunk);
    });

    socket.on('refine_complete', (data) => {
        AppState.currentContent = safeGet(data, 'content', '');
        hideProgress('generate-progress');
        setButtonLoading('refine-btn', false);
        showToast(safeGet(data, 'message', '优化完成'), 'success');
        
        const feedbackInput = document.getElementById('feedback-input');
        if (feedbackInput) feedbackInput.value = '';
        
        // 更新引用统计
        updateAndSaveCitationStats();
        updateCitationStatsUI();
        
        updateAllButtonStates();
    });
}

// ==================== 主题输入 ====================

function initTopicInput() {
    const topicInput = document.getElementById('review-topic');
    const charCount = document.getElementById('topic-char-count');
    
    if (topicInput) {
        topicInput.addEventListener('input', () => {
            const length = topicInput.value.length;
            if (charCount) charCount.textContent = length;
            updateAllButtonStates();
        });
        
        topicInput.addEventListener('blur', () => {
            const value = safeString(topicInput.value, '').trim();
            if (value) {
                saveTopic();
            }
        });
    }
}

window.setTopicExample = function(element) {
    if (!element) return;
    
    const topicInput = document.getElementById('review-topic');
    const charCount = document.getElementById('topic-char-count');
    
    if (topicInput) {
        const text = safeString(element.textContent, '');
        topicInput.value = text;
        if (charCount) charCount.textContent = text.length;
        updateAllButtonStates();
        saveTopic();
    }
};

async function saveTopic() {
    const topicInput = document.getElementById('review-topic');
    const topic = topicInput ? safeString(topicInput.value, '').trim() : '';
    const citationFormatEl = document.getElementById('citation-format');
    const citationFormat = citationFormatEl ? safeString(citationFormatEl.value, 'gb') : 'gb';
    
    if (!topic || topic.length < 5) return;
    
    try {
        await fetch('/api/review-topic', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic, citation_format: citationFormat })
        });
        
        AppState.reviewTopic = topic;
        AppState.citationFormat = citationFormat;
        updateTopicDisplay();
    } catch (error) {
        console.error('保存主题失败:', error);
    }
}

function updateTopicDisplay() {
    const previewTopic = document.getElementById('preview-topic');
    const exportTitle = document.getElementById('export-title');
    
    if (previewTopic && AppState.reviewTopic) {
        previewTopic.textContent = AppState.reviewTopic;
    }
    if (exportTitle && !exportTitle.value && AppState.reviewTopic) {
        exportTitle.placeholder = AppState.reviewTopic;
    }
}

// ==================== 文件处理 ====================

async function handleFileUpload(event, type = 'review') {
    if (!event || !event.target) return;
    
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const formData = new FormData();
    for (let file of files) {
        formData.append('files', file);
    }
    formData.append('type', type);

    try {
        showToast(`正在上传 ${files.length} 个文件...`, 'info');

        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data && data.success) {
            const fileMap = type === 'review' ? AppState.reviewFiles : AppState.litFiles;
            const uploadedFiles = Array.isArray(data.files) ? data.files : [];
            
            uploadedFiles.forEach(file => {
                if (file && file.id) {
                    fileMap.set(file.id, file);
                }
            });

            renderFileList(type);
            showToast(safeGet(data, 'message', '上传成功'), 'success');
            
            const errors = safeGet(data, 'errors', []);
            if (Array.isArray(errors) && errors.length > 0) {
                errors.forEach(err => showToast(safeString(err), 'warning'));
            }

            const poolStatus = safeGet(data, 'pool_status', null);
            if (poolStatus) {
                AppState.poolStatus = poolStatus;
                updateLiteratureStatusUI();
            }

            updateAllButtonStates();
            
            if (type === 'literature' && uploadedFiles.length > 0) {
                processLiterature();
            }
        } else {
            showToast(safeGet(data, 'error', '上传失败'), 'error');
        }
    } catch (error) {
        console.error('上传失败:', error);
        showToast('文件上传失败', 'error');
    }

    event.target.value = '';
}

async function processLiterature() {
    if (AppState.litFiles.size === 0) return;
    
    const progressEl = document.getElementById('process-progress');
    if (progressEl) progressEl.style.display = 'block';
    
    AppState.poolStatus.is_processing = true;
    updateLiteratureStatusUI();
    updateAllButtonStates();
    
    AppState.socket.emit('process_literature', {});
}

window.removeFile = async function(type, fileId) {
    if (!type || !fileId) return;
    
    try {
        const response = await fetch(`/api/files/${type}/${fileId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data && data.success) {
            const fileMap = type === 'review' ? AppState.reviewFiles : AppState.litFiles;
            fileMap.delete(fileId);
            renderFileList(type);
            
            const poolStatus = safeGet(data, 'pool_status', null);
            if (poolStatus) {
                AppState.poolStatus = poolStatus;
                AppState.literatureList = AppState.literatureList.filter(lit => 
                    safeGet(lit, 'id', '') !== fileId
                );
                updateLiteratureStatusUI();
                renderLiteratureList();
            }
            
            updateAllButtonStates();
        }
    } catch (error) {
        console.error('删除失败:', error);
        showToast('删除失败', 'error');
    }
};

async function clearFiles(type) {
    if (!confirm('确定要清空所有文件吗？')) return;

    try {
        const response = await fetch(`/api/files/${type}/clear`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data && data.success) {
            const fileMap = type === 'review' ? AppState.reviewFiles : AppState.litFiles;
            fileMap.clear();
            renderFileList(type);
            
            if (type === 'literature') {
                AppState.literatureList = [];
                renderLiteratureList();
            }
            
            const poolStatus = safeGet(data, 'pool_status', null);
            if (poolStatus) {
                AppState.poolStatus = poolStatus;
                updateLiteratureStatusUI();
            }
            
            updateAllButtonStates();
            showToast('已清空所有文件', 'success');
        }
    } catch (error) {
        console.error('清空失败:', error);
    }
}

// ==================== 拖拽上传 ====================

function initDragDrop() {
    const zones = ['review-upload-zone', 'lit-upload-area'];
    
    zones.forEach(zoneId => {
        const zone = document.getElementById(zoneId);
        if (!zone) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            zone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            zone.addEventListener(eventName, () => zone.classList.add('drag-over'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            zone.addEventListener(eventName, () => zone.classList.remove('drag-over'), false);
        });

        zone.addEventListener('drop', (e) => {
            const files = e.dataTransfer ? e.dataTransfer.files : null;
            if (!files) return;
            
            const type = zoneId.includes('review') ? 'review' : 'literature';
            
            const dt = new DataTransfer();
            for (let file of files) {
                const fileName = safeString(file.name, '');
                const lowerName = safeToLowerCase(fileName);
                if (lowerName.endsWith('.pdf') || lowerName.endsWith('.txt')) {
                    dt.items.add(file);
                }
            }
            
            if (dt.files.length > 0) {
                const inputId = type === 'review' ? 'review-files' : 'lit-files';
                const input = document.getElementById(inputId);
                if (input) {
                    input.files = dt.files;
                    handleFileUpload({ target: input }, type);
                }
            } else {
                showToast('请上传PDF或TXT格式的文件', 'warning');
            }
        }, false);
    });
}

// ==================== 模型管理 ====================

async function loadModels() {
    try {
        const response = await fetch('/api/models');
        const data = await response.json();

        if (data && data.success) {
            const models = Array.isArray(data.models) ? data.models : [];
            renderModelGrid(models);
            
            const current = safeGet(data, 'current', null);
            if (current) {
                AppState.currentModel = current;
                selectModelCard(current);
                updateModelStatus(current);
            }
        }
    } catch (error) {
        console.error('加载模型失败:', error);
        const container = document.getElementById('model-grid');
        if (container) {
            container.innerHTML = '<div class="loading-placeholder"><p>加载模型失败，请检查Ollama服务</p></div>';
        }
    }
}

function renderModelGrid(models) {
    const container = document.getElementById('model-grid');
    if (!container) return;

    if (!Array.isArray(models) || models.length === 0) {
        container.innerHTML = '<div class="loading-placeholder"><p>未找到可用模型</p></div>';
        return;
    }

    const descriptions = {
        '14B': '高质量输出，适合最终生成',
        '7B': '平衡性能，推荐日常使用',
        '1.5B': '快速响应，适合测试调试'
    };

    container.innerHTML = models.map(model => {
        const name = escapeHtml(safeGet(model, 'name', '未知模型'));
        const spec = safeGet(model, 'spec', 'unknown');
        const sizeGb = safeGet(model, 'size_gb', 0);
        const specLower = safeToLowerCase(spec).replace('.', '-');
        const desc = descriptions[spec] || '';
        
        return `
            <div class="model-card" data-model="${name}">
                <div class="model-card-header">
                    <span class="model-name">${name}</span>
                    <span class="model-spec spec-${specLower}">${spec}</span>
                </div>
                <div class="model-info">
                    <p>大小: ${sizeGb} GB</p>
                    <p>${desc}</p>
                </div>
            </div>
        `;
    }).join('');

    container.querySelectorAll('.model-card').forEach(card => {
        card.addEventListener('click', () => {
            const modelName = safeGet(card, 'dataset.model', '');
            if (modelName) selectModel(modelName);
        });
    });
}

async function selectModel(modelName) {
    if (!modelName) return;
    
    try {
        const response = await fetch('/api/models/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: modelName })
        });

        const data = await response.json();

        if (data && data.success) {
            AppState.currentModel = modelName;
            selectModelCard(modelName);
            updateModelStatus(modelName);
            enableButton('step1-next');
            showToast(safeGet(data, 'message', '模型已选择'), 'success');
            updateAllButtonStates();
        } else {
            showToast(safeGet(data, 'error', '选择失败'), 'error');
        }
    } catch (error) {
        console.error('选择模型失败:', error);
        showToast('选择模型失败', 'error');
    }
}

function selectModelCard(modelName) {
    document.querySelectorAll('.model-card').forEach(card => {
        const cardModel = safeGet(card, 'dataset.model', '');
        card.classList.toggle('selected', cardModel === modelName);
    });
}

function updateModelStatus(modelName) {
    const badge = document.getElementById('model-status');
    if (badge) {
        badge.textContent = safeString(modelName, '未选择');
        badge.classList.add('active');
    }
}

async function checkOllamaStatus() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();

        const statusEl = document.getElementById('ollama-status');
        if (!statusEl) return;
        
        const ollamaStatus = safeGet(data, 'ollama_status', 'offline');
        
        if (ollamaStatus === 'running') {
            statusEl.classList.add('online');
            statusEl.classList.remove('offline');
            const textEl = statusEl.querySelector('.text');
            if (textEl) textEl.textContent = 'Ollama 运行中';
        } else {
            statusEl.classList.add('offline');
            statusEl.classList.remove('online');
            const textEl = statusEl.querySelector('.text');
            if (textEl) textEl.textContent = 'Ollama 离线';
        }
    } catch (error) {
        console.error('检查状态失败:', error);
    }
}

async function loadCitationFormats() {
    try {
        const response = await fetch('/api/citation-formats');
        const data = await response.json();
        
        if (data && data.success) {
            const select = document.getElementById('citation-format');
            const formats = Array.isArray(data.formats) ? data.formats : [];
            
            if (select && formats.length > 0) {
                select.innerHTML = formats.map(fmt => {
                    const id = safeGet(fmt, 'id', '');
                    const name = escapeHtml(safeGet(fmt, 'name', ''));
                    return `<option value="${id}">${name}</option>`;
                }).join('');
            }
        }
    } catch (error) {
        console.error('加载引用格式失败:', error);
    }
}

// ==================== 核心功能 ====================

function analyzeParadigm() {
    if (!AppState.currentModel) {
        showToast('请先选择一个模型', 'error');
        return;
    }

    if (AppState.reviewFiles.size === 0) {
        showToast('请先上传综述文献', 'error');
        return;
    }

    clearElement('paradigm-output');
    const resultEl = document.getElementById('paradigm-result');
    if (resultEl) resultEl.style.display = 'none';
    
    showProgress('analyze-progress');
    setButtonLoading('analyze-btn', true);

    AppState.socket.emit('analyze_paradigm', {});
}

function generateFramework() {
    const topicInput = document.getElementById('review-topic');
    const topic = topicInput ? safeString(topicInput.value, '').trim() : '';
    
    if (!topic || topic.length < 5) {
        showToast('请先填写综述主题（至少5个字符）', 'error');
        if (topicInput) topicInput.focus();
        return;
    }
    
    if (!AppState.currentModel) {
        showToast('请先选择一个模型', 'error');
        return;
    }

    if (!AppState.currentParadigm) {
        showToast('请先完成写作范式分析', 'error');
        return;
    }

    const pool = AppState.poolStatus || {};
    const fileCount = safeGet(pool, 'file_count', 0);
    const isProcessing = safeGet(pool, 'is_processing', false);
    const hasError = safeGet(pool, 'has_error', false);
    const isProcessed = safeGet(pool, 'is_processed', false);
    
    if (fileCount > 0 && isProcessing) {
        showToast('正在分析参考文献，请稍候...', 'warning');
        return;
    }
    if (fileCount > 0 && hasError) {
        showToast('文献分析失败，请重新上传', 'error');
        return;
    }
    if (fileCount > 0 && !isProcessed) {
        showToast('请等待参考文献分析完成', 'warning');
        return;
    }

    saveTopic();
    clearElement('framework-output');
    showProgress('generate-progress');
    setButtonLoading('generate-framework-btn', true);

    AppState.socket.emit('generate_framework', {
        topic: topic,
        paradigm: AppState.currentParadigm
    });
}

function generateContent() {
    const topicInput = document.getElementById('review-topic');
    const topic = topicInput ? safeString(topicInput.value, '').trim() : '';
    
    if (!topic || topic.length < 5) {
        showToast('请先填写综述主题（至少5个字符）', 'error');
        if (topicInput) topicInput.focus();
        return;
    }
    
    if (!AppState.currentModel) {
        showToast('请先选择一个模型', 'error');
        return;
    }

    if (!AppState.currentParadigm) {
        showToast('请先完成写作范式分析', 'error');
        return;
    }

    const pool = AppState.poolStatus || {};
    const fileCount = safeGet(pool, 'file_count', 0);
    const isProcessing = safeGet(pool, 'is_processing', false);
    const hasError = safeGet(pool, 'has_error', false);
    const isProcessed = safeGet(pool, 'is_processed', false);
    
    if (fileCount > 0 && isProcessing) {
        showToast('正在分析参考文献，请稍候...', 'warning');
        return;
    }
    if (fileCount > 0 && hasError) {
        showToast('文献分析失败，请重新上传', 'error');
        return;
    }
    if (fileCount > 0 && !isProcessed) {
        showToast('请等待参考文献分析完成', 'warning');
        return;
    }

    const sectionSelect = document.getElementById('section-select');
    const section = sectionSelect ? safeString(sectionSelect.value, 'full') : 'full';

    saveTopic();
    clearElement('content-output');
    showProgress('generate-progress');
    switchOutputTab('content-output');
    setButtonLoading('generate-content-btn', true);

    AppState.socket.emit('generate_section', {
        section: section,
        topic: topic,
        paradigm: AppState.currentParadigm,
        framework: safeString(AppState.currentFramework, '')
    });
}

function refineContent() {
    const feedbackInput = document.getElementById('feedback-input');
    const feedback = feedbackInput ? safeString(feedbackInput.value, '').trim() : '';
    
    if (!feedback) {
        showToast('请输入修改意见', 'error');
        return;
    }

    if (!AppState.currentContent) {
        showToast('没有可优化的内容', 'error');
        return;
    }

    clearElement('content-output');
    showProgress('generate-progress');
    setButtonLoading('refine-btn', true);

    AppState.socket.emit('refine_content', {
        feedback: feedback,
        content: AppState.currentContent
    });
}

// ==================== Prompt管理 ====================

function copyParadigm() {
    const output = document.getElementById('paradigm-output');
    const content = output ? safeString(output.textContent, '') : '';
    const finalContent = content.trim() || AppState.currentParadigm;
    
    if (!finalContent) {
        showToast('没有可复制的内容', 'warning');
        return;
    }
    
    navigator.clipboard.writeText(finalContent).then(() => {
        showToast('已复制到剪贴板', 'success');
    }).catch(() => {
        showToast('复制失败', 'error');
    });
}

function toggleEditParadigm() {
    const output = document.getElementById('paradigm-output');
    if (!output) return;
    
    const isEditing = output.contentEditable === 'true';
    output.contentEditable = !isEditing;
    
    if (!isEditing) {
        output.focus();
        showToast('已进入编辑模式', 'info');
    } else {
        AppState.currentParadigm = safeString(output.textContent, '');
        showToast('编辑完成', 'success');
        updateAllButtonStates();
    }
}

async function saveParadigmToServer() {
    const output = document.getElementById('paradigm-output');
    const content = output ? safeString(output.textContent, '').trim() : '';
    const finalContent = content || AppState.currentParadigm;
    
    if (!finalContent) {
        showToast('没有可保存的内容', 'error');
        return;
    }

    const name = prompt('请输入Prompt名称:', '自定义Prompt');
    if (!name) return;

    try {
        const response = await fetch('/api/prompts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, content: finalContent })
        });

        const data = await response.json();
        if (data && data.success) {
            showToast('Prompt已保存', 'success');
        } else {
            showToast(safeGet(data, 'error', '保存失败'), 'error');
        }
    } catch (error) {
        console.error('保存失败:', error);
        showToast('保存失败', 'error');
    }
}

// ==================== 导出功能 ====================

function selectExportFormat(format) {
    if (!format) return;
    
    AppState.selectedExportFormat = format;
    
    document.querySelectorAll('.export-card').forEach(card => {
        const cardFormat = safeGet(card, 'dataset.format', '');
        card.classList.toggle('selected', cardFormat === format);
    });
    
    enableButton('export-btn');
}

function updateExportPreview() {
    const preview = document.getElementById('export-preview');
    const content = safeString(AppState.currentContent, '') || safeString(AppState.currentFramework, '');
    
    if (preview) {
        if (content) {
            const truncated = content.length > 1000 ? content.substring(0, 1000) + '...' : content;
            preview.textContent = truncated;
        } else {
            preview.innerHTML = '<p class="placeholder-text">暂无内容</p>';
        }
    }
    
    updateTopicDisplay();
    updateCitationStatsUI();
}

async function exportReview() {
    const content = safeString(AppState.currentContent, '') || safeString(AppState.currentFramework, '');
    
    if (!content) {
        showToast('没有可导出的内容', 'error');
        return;
    }

    const exportTitleEl = document.getElementById('export-title');
    const title = exportTitleEl ? 
        (safeString(exportTitleEl.value, '').trim() || AppState.reviewTopic || '综述') : 
        '综述';
    const format = AppState.selectedExportFormat || 'docx';

    try {
        showToast('正在导出...', 'info');

        const response = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, title, format })
        });

        const data = await response.json();

        if (data && data.success) {
            showToast(safeGet(data, 'message', '导出成功'), 'success');
            
            const filename = safeGet(data, 'filename', '');
            if (filename) {
                const link = document.createElement('a');
                link.href = `/api/exports/${filename}`;
                link.download = filename;
                link.click();
            }
        } else {
            showToast(safeGet(data, 'error', '导出失败'), 'error');
        }
    } catch (error) {
        console.error('导出失败:', error);
        showToast('导出失败', 'error');
    }
}

// ==================== 步骤导航 ====================

function canNavigateToStep(step) {
    if (step === 1) return true;
    if (step === 2) return AppState.completedSteps.has(1) || !!AppState.currentModel;
    if (step === 3) return AppState.completedSteps.has(2) || !!AppState.currentParadigm;
    if (step === 4) return AppState.completedSteps.has(3) || !!AppState.currentContent;
    return false;
}

function navigateToStep(step) {
    const currentCard = document.querySelector('.step-card.active');
    const nextCard = document.getElementById(`step-${step}`);
    
    if (!nextCard || currentCard === nextCard) return;

    currentCard.classList.add('slide-out');
    
    setTimeout(() => {
        currentCard.classList.remove('active', 'slide-out');
        nextCard.classList.add('active');
        
        AppState.currentStep = step;
        updateStepIndicator();
        
        if (step === 4) {
            updateExportPreview();
        }
        
        if (step === 3) {
            updateAllButtonStates();
            fetchPoolStatus();
        }
    }, 300);
}

function updateStepIndicator() {
    document.querySelectorAll('.step-item').forEach(item => {
        const stepAttr = safeGet(item, 'dataset.step', '0');
        const step = parseInt(stepAttr, 10);
        
        item.classList.remove('active', 'completed', 'disabled');
        
        if (step === AppState.currentStep) {
            item.classList.add('active');
        } else if (AppState.completedSteps.has(step)) {
            item.classList.add('completed');
        } else if (!canNavigateToStep(step)) {
            item.classList.add('disabled');
        }
    });

    document.querySelectorAll('.step-connector').forEach((connector, index) => {
        const prevStep = index + 1;
        connector.classList.toggle('active', AppState.completedSteps.has(prevStep));
    });
}

async function resetAll() {
    try {
        await fetch('/api/steps/reset', { method: 'POST' });
        await fetch('/api/files/review/clear', { method: 'DELETE' });
        await fetch('/api/files/literature/clear', { method: 'DELETE' });
    } catch (error) {
        console.error('重置失败:', error);
    }

    // 重置状态
    AppState.currentStep = 1;
    AppState.completedSteps.clear();
    AppState.reviewFiles.clear();
    AppState.litFiles.clear();
    AppState.currentParadigm = '';
    AppState.currentFramework = '';
    AppState.currentContent = '';
    AppState.reviewTopic = '';
    AppState.literatureList = [];
    AppState.poolStatus = {
        file_count: 0,
        processed_count: 0,
        citation_count: 0,
        is_processing: false,
        is_processed: false,
        has_error: false,
        error_message: null,
        can_generate: false
    };
    AppState.citationStats = {
        totalRefs: 0,
        citedRefs: 0,
        citationCount: 0
    };

    // 重置UI
    renderFileList('review');
    renderFileList('literature');
    clearElement('paradigm-output');
    clearElement('framework-output');
    clearElement('content-output');
    
    const paradigmResult = document.getElementById('paradigm-result');
    if (paradigmResult) paradigmResult.style.display = 'none';
    
    const topicInput = document.getElementById('review-topic');
    if (topicInput) topicInput.value = '';
    
    const charCount = document.getElementById('topic-char-count');
    if (charCount) charCount.textContent = '0';
    
    const citableList = document.getElementById('citable-list');
    if (citableList) citableList.style.display = 'none';
    
    const citationStats = document.getElementById('citation-stats');
    if (citationStats) citationStats.style.display = 'none';
    
    updateLiteratureStatusUI();
    
    document.querySelectorAll('.step-card').forEach(card => {
        card.classList.remove('active');
    });
    const step1 = document.getElementById('step-1');
    if (step1) step1.classList.add('active');
    
    updateStepIndicator();
    updateAllButtonStates();
    
    showToast('已重置所有内容', 'success');
}

// ==================== 事件监听器初始化 ====================

function initEventListeners() {
    // 步骤导航
    document.querySelectorAll('.step-item').forEach(item => {
        item.addEventListener('click', () => {
            const stepAttr = safeGet(item, 'dataset.step', '0');
            const step = parseInt(stepAttr, 10);
            if (canNavigateToStep(step)) {
                navigateToStep(step);
            }
        });
    });

    // 上一步/下一步按钮
    document.querySelectorAll('.btn-prev').forEach(btn => {
        btn.addEventListener('click', () => {
            const prevAttr = safeGet(btn, 'dataset.prev', '1');
            const prevStep = parseInt(prevAttr, 10);
            navigateToStep(prevStep);
        });
    });

    // 步骤1
    const step1Next = document.getElementById('step1-next');
    if (step1Next) {
        step1Next.addEventListener('click', () => {
            if (AppState.currentModel) {
                AppState.completedSteps.add(1);
                navigateToStep(2);
            }
        });
    }

    // 步骤2
    const reviewFiles = document.getElementById('review-files');
    if (reviewFiles) {
        reviewFiles.addEventListener('change', (e) => handleFileUpload(e, 'review'));
    }
    
    const clearReviewFiles = document.getElementById('clear-review-files');
    if (clearReviewFiles) {
        clearReviewFiles.addEventListener('click', () => clearFiles('review'));
    }
    
    const analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', analyzeParadigm);
    }
    
    const step2Next = document.getElementById('step2-next');
    if (step2Next) {
        step2Next.addEventListener('click', () => {
            if (AppState.currentParadigm) {
                navigateToStep(3);
            }
        });
    }

    // Prompt操作
    const copyParadigmBtn = document.getElementById('copy-paradigm');
    if (copyParadigmBtn) copyParadigmBtn.addEventListener('click', copyParadigm);
    
    const editParadigmBtn = document.getElementById('edit-paradigm');
    if (editParadigmBtn) editParadigmBtn.addEventListener('click', toggleEditParadigm);
    
    const saveParadigmBtn = document.getElementById('save-paradigm');
    if (saveParadigmBtn) saveParadigmBtn.addEventListener('click', saveParadigmToServer);

    // 步骤3 - 文献上传
    const litFiles = document.getElementById('lit-files');
    if (litFiles) {
        litFiles.addEventListener('change', (e) => handleFileUpload(e, 'literature'));
    }
    
    const clearLitBtn = document.getElementById('clear-lit-btn');
    if (clearLitBtn) {
        clearLitBtn.addEventListener('click', () => clearFiles('literature'));
    }
    
    // 步骤3 - 主题和格式
    const citationFormat = document.getElementById('citation-format');
    if (citationFormat) {
        citationFormat.addEventListener('change', saveTopic);
    }
    
    // 步骤3 - 核心生成按钮
    const frameworkBtn = document.getElementById('generate-framework-btn');
    if (frameworkBtn) {
        frameworkBtn.addEventListener('click', generateFramework);
    }
    
    const contentBtn = document.getElementById('generate-content-btn');
    if (contentBtn) {
        contentBtn.addEventListener('click', generateContent);
    }
    
    const refineBtn = document.getElementById('refine-btn');
    if (refineBtn) {
        refineBtn.addEventListener('click', refineContent);
    }
    
    const step3Next = document.getElementById('step3-next');
    if (step3Next) {
        step3Next.addEventListener('click', () => {
            if (AppState.currentContent) {
                navigateToStep(4);
                updateExportPreview();
            }
        });
    }

    // 输出标签切换
    document.querySelectorAll('.output-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const target = safeGet(tab, 'dataset.target', '');
            if (target) switchOutputTab(target);
        });
    });

    // 步骤4
    document.querySelectorAll('.export-card').forEach(card => {
        card.addEventListener('click', () => {
            const format = safeGet(card, 'dataset.format', '');
            if (format) selectExportFormat(format);
        });
    });
    
    const exportBtn = document.getElementById('export-btn');
    if (exportBtn) exportBtn.addEventListener('click', exportReview);
    
    const newReviewBtn = document.getElementById('new-review-btn');
    if (newReviewBtn) newReviewBtn.addEventListener('click', resetAll);

    // 重置
    const resetBtn = document.getElementById('reset-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            if (confirm('确定要重新开始吗？所有进度将被清除。')) {
                resetAll();
            }
        });
    }
}

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', () => {
    try {
        initSocket();
        initEventListeners();
        initDragDrop();
        initTopicInput();
        loadModels();
        loadCitationFormats();
        checkOllamaStatus();
        updateStepIndicator();
        updateAllButtonStates();
    } catch (error) {
        console.error('初始化失败:', error);
    }
});

// 定时检查Ollama状态
setInterval(checkOllamaStatus, 30000);
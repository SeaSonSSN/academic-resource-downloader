const API_BASE = '/api';

// DOM Elements
const searchInput = document.getElementById('searchInput');
const resourceType = document.getElementById('resourceType');
const searchBtn = document.getElementById('searchBtn');
const resultsSection = document.getElementById('resultsSection');
const loadingDiv = document.getElementById('loading');
const resultsDiv = document.getElementById('results');
const downloadsList = document.getElementById('downloadsList');

// State
let tasks = {};

// Event Listeners
searchBtn.addEventListener('click', handleSearch);
searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleSearch();
});

async function handleSearch() {
    const query = searchInput.value.trim();
    if (!query) return;

    // Show loading
    resultsSection.style.display = 'block';
    loadingDiv.style.display = 'block';
    resultsDiv.innerHTML = '';
    searchBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                resource_type: resourceType.value
            })
        });

        const data = await response.json();
        displayResults(data.results || []);
    } catch (error) {
        resultsDiv.innerHTML = `<div class="error">搜索失败: ${error.message}</div>`;
    } finally {
        loadingDiv.style.display = 'none';
        searchBtn.disabled = false;
    }
}

function displayResults(results) {
    if (results.length === 0) {
        resultsDiv.innerHTML = '<div class="empty-state">没有找到结果</div>';
        return;
    }

    resultsDiv.innerHTML = results.map(result => `
        <div class="result-item">
            <div class="result-title">${escapeHtml(result.title)}</div>
            <div class="result-meta">
                <span>👤 ${escapeHtml(result.author)}</span>
                <span>📅 ${result.year || '未知'}</span>
                <span>📁 ${result.format || 'pdf'}</span>
            </div>
            <button class="download-btn" onclick="startDownload(${JSON.stringify(result).replace(/"/g, '&quot;')})">
                下载
            </button>
        </div>
    `).join('');
}

async function startDownload(result) {
    const taskId = `task_${Date.now()}`;
    const downloadDir = `${getDownloadsPath()}`;

    // Add to downloads list
    const item = document.createElement('div');
    item.className = 'download-item';
    item.id = taskId;
    item.innerHTML = `
        <div class="download-info">
            <div class="download-title">${escapeHtml(result.title)}</div>
            <div class="download-status">等待中...</div>
            <div class="progress-bar"><div class="progress-fill" style="width: 0%"></div></div>
        </div>
    `;
    downloadsList.appendChild(item);

    tasks[taskId] = { result, status: 'pending', progress: 0 };

    try {
        const response = await fetch(`${API_BASE}/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                result: result,
                save_dir: downloadDir
            })
        });

        const data = await response.json();
        updateTask(taskId, data.task);
    } catch (error) {
        updateTask(taskId, { status: 'failed', error: error.message });
    }
}

function updateTask(taskId, task) {
    const item = document.getElementById(taskId);
    if (!item) return;

    const statusEl = item.querySelector('.download-status');
    const progressEl = item.querySelector('.progress-fill');

    tasks[taskId] = task;

    statusEl.textContent = getStatusText(task.status, task.progress * 100);
    progressEl.style.width = `${(task.progress || 0) * 100}%`;

    if (task.status === 'completed') {
        statusEl.textContent = `✓ 完成: ${task.path || ''}`;
        statusEl.style.color = '#28a745';
    } else if (task.status === 'failed') {
        statusEl.textContent = `✗ 失败: ${task.error || '未知错误'}`;
        statusEl.style.color = '#dc3545';
    }
}

function getStatusText(status, progress) {
    switch (status) {
        case 'pending': return '等待中...';
        case 'downloading': return `下载中: ${Math.round(progress)}%`;
        case 'completed': return '完成';
        case 'failed': return '失败';
        default: return status;
    }
}

function getDownloadsPath() {
    // Use home directory Downloads folder
    const home = navigator.userAgent.includes('Windows') ? 'C:/Users/' + (navigator.userAgent.includes('Chrome') ? 'User' : 'User') : '/home';
    return home + '/Downloads';
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Poll for task updates
setInterval(async () => {
    for (const taskId of Object.keys(tasks)) {
        try {
            const response = await fetch(`${API_BASE}/tasks/${taskId}`);
            if (response.ok) {
                const data = await response.json();
                updateTask(taskId, data.task);
            }
        } catch (e) {
            // Ignore polling errors
        }
    }
}, 2000);
let manageCurrentPage = 1;
const managePerPage = 15;
let deleteBookId = null;

const defaultCoverUrl = 'https://via.placeholder.com/200x300?text=No+Cover';

document.addEventListener('DOMContentLoaded', function() {
    loadManageBooks(1);

    document.getElementById('manageSearchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchManageBooks();
        }
    });

    document.getElementById('editModal').addEventListener('click', function(e) {
        if (e.target === this) closeEditModal();
    });

    document.getElementById('deleteModal').addEventListener('click', function(e) {
        if (e.target === this) closeDeleteModal();
    });

    document.getElementById('addBookModal').addEventListener('click', function(e) {
        if (e.target === this) closeAddBookModal();
    });

    document.getElementById('batchImportModal').addEventListener('click', function(e) {
        if (e.target === this) closeBatchImportModal();
    });
});

async function loadManageBooks(page = 1) {
    manageCurrentPage = page;
    const searchValue = document.getElementById('manageSearchInput').value;
    const sortMode = document.getElementById('manageSortMode').value;
    const tbody = document.getElementById('manageTableBody');

    tbody.innerHTML = '<tr><td colspan="8" class="table-loading">加载中...</td></tr>';

    try {
        let url = `/api/books?page=${page}&per_page=${managePerPage}&sort_mode=${sortMode}`;
        if (searchValue) {
            url += `&search=${encodeURIComponent(searchValue)}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            renderManageTable(data.data.books);
            renderManagePagination(data.data.total_pages, page);
        } else {
            tbody.innerHTML = `<tr><td colspan="8" class="table-loading">加载失败: ${data.error}</td></tr>`;
        }
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="8" class="table-loading">加载失败: ${error.message}</td></tr>`;
    }
}

function searchManageBooks() {
    loadManageBooks(1);
}

function renderManageTable(books) {
    const tbody = document.getElementById('manageTableBody');

    if (books.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="table-loading">暂无图书数据</td></tr>';
        return;
    }

    tbody.innerHTML = books.map(book => `
        <tr>
            <td>${book.book_id}</td>
            <td>
                ${book.cover_image
                    ? `<img src="${book.cover_image}" alt="" class="manage-cover-thumb"
                           onerror="this.onerror=null; this.src='${defaultCoverUrl}';">`
                    : `<img src="${defaultCoverUrl}" alt="" class="manage-cover-thumb">`}
            </td>
            <td><div class="manage-book-title" title="${book.title}">${book.title}</div></td>
            <td><div class="manage-book-author" title="${book.authors && book.authors.length > 0 ? book.authors.join(', ') : ''}">${book.authors && book.authors.length > 0 ? book.authors.join(', ') : '未知'}</div></td>
            <td><div class="manage-book-publisher">${book.publisher || '-'}</div></td>
            <td>${book.rating ? `<span class="manage-rating-badge">⭐ ${book.rating}</span>` : '-'}</td>
            <td>
                <div class="manage-tags">
                    ${book.domain_tags && book.domain_tags.length > 0
                        ? book.domain_tags.slice(0, 3).map(tag => `<span class="tag">${tag}</span>`).join('')
                        : '<span style="color:var(--text-muted);font-size:12px;">-</span>'}
                </div>
            </td>
            <td>
                <div class="manage-actions">
                    <button class="btn-edit" onclick="openEditModal(${book.book_id})">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                        编辑
                    </button>
                    <button class="btn-del" onclick="openDeleteModal(${book.book_id}, '${book.title.replace(/'/g, "\\'")}')">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        删除
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

function renderManagePagination(totalPages, currentPage) {
    const pagination = document.getElementById('managePagination');

    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }

    let html = '';

    if (currentPage > 1) {
        html += `<button onclick="loadManageBooks(${currentPage - 1})">上一页</button>`;
    }

    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);

    if (startPage > 1) {
        html += `<button onclick="loadManageBooks(1)">1</button>`;
        if (startPage > 2) html += '<span>...</span>';
    }

    for (let i = startPage; i <= endPage; i++) {
        if (i === currentPage) {
            html += `<button class="active">${i}</button>`;
        } else {
            html += `<button onclick="loadManageBooks(${i})">${i}</button>`;
        }
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) html += '<span>...</span>';
        html += `<button onclick="loadManageBooks(${totalPages})">${totalPages}</button>`;
    }

    if (currentPage < totalPages) {
        html += `<button onclick="loadManageBooks(${currentPage + 1})">下一页</button>`;
    }

    pagination.innerHTML = html;
}

async function openEditModal(bookId) {
    try {
        const response = await fetch(`/api/books/${bookId}`);
        const data = await response.json();

        if (!data.success) {
            alert('加载图书信息失败: ' + data.error);
            return;
        }

        const book = data.data;
        document.getElementById('editBookId').value = book.book_id;
        document.getElementById('editTitle').value = book.title || '';
        document.getElementById('editAuthors').value = book.authors && book.authors.length > 0 ? book.authors.join(', ') : '';
        document.getElementById('editPublisher').value = book.publisher || '';
        document.getElementById('editPubDate').value = book.publication_date || '';
        document.getElementById('editRating').value = book.rating || '';
        document.getElementById('editDomainTags').value = book.domain_tags && book.domain_tags.length > 0 ? book.domain_tags.join(', ') : '';
        document.getElementById('editBookIntro').value = book.book_intro || '';

        document.getElementById('editModal').style.display = 'flex';
    } catch (error) {
        alert('加载图书信息失败: ' + error.message);
    }
}

function closeEditModal() {
    document.getElementById('editModal').style.display = 'none';
}

async function saveEditBook() {
    const bookId = document.getElementById('editBookId').value;
    const title = document.getElementById('editTitle').value.trim();
    const authorsStr = document.getElementById('editAuthors').value.trim();
    const publisher = document.getElementById('editPublisher').value.trim();
    const pubDate = document.getElementById('editPubDate').value;
    const rating = document.getElementById('editRating').value;
    const tagsStr = document.getElementById('editDomainTags').value.trim();
    const bookIntro = document.getElementById('editBookIntro').value.trim();

    if (!title) {
        alert('书名不能为空');
        return;
    }

    const updateData = { title };

    if (authorsStr) {
        updateData.authors = authorsStr.split(/[,，]/).map(a => a.trim()).filter(a => a);
    }
    if (publisher) updateData.publisher = publisher;
    if (pubDate) updateData.publication_date = pubDate;
    if (rating !== '') updateData.rating = parseFloat(rating);
    if (tagsStr) {
        updateData.domain_tags = tagsStr.split(/[,，]/).map(t => t.trim()).filter(t => t);
    }
    if (bookIntro) updateData.book_intro = bookIntro;

    try {
        const response = await fetch(`/api/books/${bookId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updateData)
        });
        const data = await response.json();

        if (data.success) {
            closeEditModal();
            loadManageBooks(manageCurrentPage);
        } else {
            alert('保存失败: ' + data.error);
        }
    } catch (error) {
        alert('保存失败: ' + error.message);
    }
}

function openDeleteModal(bookId, bookTitle) {
    deleteBookId = bookId;
    document.getElementById('deleteBookTitle').textContent = bookTitle;
    document.getElementById('deleteModal').style.display = 'flex';
}

function closeDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
    deleteBookId = null;
}

async function confirmDeleteBook() {
    if (!deleteBookId) return;

    try {
        const response = await fetch(`/api/books/${deleteBookId}`, {
            method: 'DELETE'
        });
        const data = await response.json();

        if (data.success) {
            closeDeleteModal();
            loadManageBooks(manageCurrentPage);
        } else {
            alert('删除失败: ' + data.error);
        }
    } catch (error) {
        alert('删除失败: ' + error.message);
    }
}

function openAddBookModal() {
    document.getElementById('addDoubanUrl').value = '';
    const statusEl = document.getElementById('addBookStatus');
    statusEl.style.display = 'none';
    statusEl.className = 'add-book-status-msg';
    document.getElementById('addBookSubmitBtn').disabled = false;
    document.getElementById('addBookSubmitBtn').textContent = '添加';
    document.getElementById('addBookModal').style.display = 'flex';
}

function closeAddBookModal() {
    document.getElementById('addBookModal').style.display = 'none';
}

function validateDoubanUrl(url) {
    const pattern = /^https?:\/\/book\.douban\.com\/subject\/\d+\/?/;
    return pattern.test(url.trim());
}

async function submitAddBook() {
    const urlInput = document.getElementById('addDoubanUrl');
    const statusDiv = document.getElementById('addBookStatus');
    const btn = document.getElementById('addBookSubmitBtn');

    const url = urlInput.value.trim();

    if (!url) {
        showAddStatus('error', '请输入豆瓣书籍详情页URL', statusDiv);
        return;
    }
    if (!validateDoubanUrl(url)) {
        showAddStatus('error', 'URL格式不正确，请输入有效的豆瓣书籍详情页地址', statusDiv);
        return;
    }

    btn.disabled = true;
    btn.textContent = '处理中...';
    showAddStatus('loading', '正在采集书籍信息...', statusDiv);

    try {
        const response = await fetch('/api/books/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ douban_url: url })
        });
        const data = await response.json();

        if (data.success) {
            showAddStatus('success', `《${data.data.title}》添加成功！`, statusDiv);
            setTimeout(() => {
                closeAddBookModal();
                loadManageBooks(1);
            }, 1200);
        } else {
            showAddStatus('error', data.error || '添加失败', statusDiv);
            btn.disabled = false;
            btn.textContent = '添加';
        }
    } catch (error) {
        showAddStatus('error', '网络错误: ' + error.message, statusDiv);
        btn.disabled = false;
        btn.textContent = '添加';
    }
}

function showAddStatus(type, message, targetDiv) {
    if (!targetDiv) return;
    targetDiv.style.display = 'block';
    const icons = { loading: '', success: '✅ ', error: '❌ ' };
    targetDiv.className = `add-book-status-msg status-${type}`;
    if (type === 'loading') {
        targetDiv.innerHTML = `<span class="reason-loading-dot"></span> ${message}`;
    } else {
        targetDiv.innerHTML = `${icons[type]}${message}`;
    }
}

let batchEventSource = null;

function openBatchImportModal() {
    document.getElementById('batchImportOptions').style.display = '';
    document.getElementById('batchProgressArea').style.display = 'none';
    document.getElementById('batchSummary').style.display = 'none';
    document.getElementById('batchStartBtn').style.display = '';
    document.getElementById('batchStartBtn').disabled = false;
    document.getElementById('batchCancelBtn').textContent = '取消';
    document.getElementById('batchLog').innerHTML = '';
    document.getElementById('batchImportModal').style.display = 'flex';
}

function closeBatchImportModal() {
    if (batchEventSource) {
        batchEventSource.close();
        batchEventSource = null;
    }
    document.getElementById('batchImportModal').style.display = 'none';
}

function startBatchImport() {
    const subcat = document.getElementById('batchSubcat').value;
    const pages = document.getElementById('batchPages').value;

    if (parseInt(pages) < 1 || parseInt(pages) > 5) {
        alert('页数请输入1-5之间的数字');
        return;
    }

    document.getElementById('batchImportOptions').style.display = 'none';
    document.getElementById('batchProgressArea').style.display = '';
    document.getElementById('batchSummary').style.display = 'none';
    document.getElementById('batchStartBtn').disabled = true;
    document.getElementById('batchLog').innerHTML = '';

    let params = `pages=${pages}`;
    if (subcat) params += `&subcat=${encodeURIComponent(subcat)}`;

    batchEventSource = new EventSource(`/api/books/batch-import?${params}`);

    batchEventSource.addEventListener('start', function(e) {
        document.getElementById('batchProgressText').textContent = '正在获取图书列表...';
    });

    batchEventSource.addEventListener('progress', function(e) {
        const data = JSON.parse(e.data);
        updateBatchProgress(data.current, data.total);
        appendBatchLog(data.title, data.status, data.message || '');
    });

    batchEventSource.addEventListener('complete', function(e) {
        const data = JSON.parse(e.data);
        batchEventSource.close();
        batchEventSource = null;
        showBatchSummary(data);
        document.getElementById('batchStartBtn').style.display = 'none';
        document.getElementById('batchCancelBtn').textContent = '关闭';
        loadManageBooks(1);
    });

    batchEventSource.onerror = function() {
        batchEventSource.close();
        batchEventSource = null;
        document.getElementById('batchProgressText').textContent = '连接中断';
        document.getElementById('batchStartBtn').disabled = false;
    };
}

function updateBatchProgress(current, total) {
    const pct = total > 0 ? Math.round((current / total) * 100) : 0;
    document.getElementById('batchProgressText').textContent = `正在导入...`;
    document.getElementById('batchProgressCount').textContent = `${current}/${total}`;
    document.getElementById('batchProgressBar').style.width = `${pct}%`;
}

function appendBatchLog(title, status, message) {
    const log = document.getElementById('batchLog');
    const icons = { success: '✅', duplicate: '⚠️', error: '❌' };
    const icon = icons[status] || '🔄';

    const item = document.createElement('div');
    item.className = `batch-log-item ${status}`;
    item.innerHTML = `<span class="batch-log-icon">${icon}</span><span class="batch-log-title">${title}</span>${message ? `<span class="batch-log-msg">${message}</span>` : ''}`;

    log.appendChild(item);
    log.scrollTop = log.scrollHeight;
}

function showBatchSummary(data) {
    document.getElementById('batchProgressArea').style.display = 'none';
    document.getElementById('batchSummary').style.display = '';

    document.getElementById('batchStatSuccess').textContent = data.success;
    document.getElementById('batchStatDuplicate').textContent = data.duplicate;
    document.getElementById('batchStatError').textContent = data.error;

    if (data.errors && data.errors.length > 0) {
        document.getElementById('batchErrorDetail').style.display = '';
        const list = document.getElementById('batchErrorList');
        list.innerHTML = data.errors.map(e =>
            `<div class="batch-error-item"><strong>${e.title || '未知'}</strong>: ${e.message}</div>`
        ).join('');
    } else {
        document.getElementById('batchErrorDetail').style.display = 'none';
    }
}

function toggleBatchErrors() {
    const list = document.getElementById('batchErrorList');
    const toggle = document.querySelector('.batch-error-toggle');
    if (list.style.display === 'none') {
        list.style.display = '';
        toggle.textContent = '收起失败详情 ▴';
    } else {
        list.style.display = 'none';
        toggle.textContent = '查看失败详情 ▾';
    }
}

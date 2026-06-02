let currentPage = 1;
let currentBookId = null;
let currentBeta = 0.25;
let currentBooksData = [];
let currentRecommendationsData = [];
const perPage = 20;
let sliderRafId = null;
let recommendDebounceTimer = null;

const defaultCoverUrl = 'https://via.placeholder.com/200x300?text=No+Cover';

const betaDescriptions = {
    0.10: '侧重相近领域，推荐结果偏向与原书领域高度相关的书籍',
    0.15: '适度拓展领域，推荐结果以相近领域为主，少量跨域探索',
    0.20: '兼顾相关与跨域，推荐结果在相近领域和跨领域间取得平衡',
    0.25: '推荐设置 — 平衡相关性与跨域发现，推荐结果兼顾领域相近与领域差异',
    0.30: '鼓励跨域探索，推荐结果中跨领域书籍占比增加',
    0.35: '积极跨域发现，推荐结果更侧重不同领域的书籍',
    0.40: '强调领域差异，推荐结果以完全不同领域的书籍为主',
    0.45: '大胆跨界探索，推荐结果几乎全部来自完全不同的领域'
};

document.addEventListener('DOMContentLoaded', function() {
    loadBooks();
    loadSidebarRecommendations();

    setTimeout(() => updateSliderTooltip(), 100);

    document.getElementById('searchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchBooks();
        }
    });

    document.getElementById('betaSlider').addEventListener('input', function() {
        currentBeta = parseInt(this.value) / 100;
        updateSliderDescription();

        if (sliderRafId) cancelAnimationFrame(sliderRafId);
        sliderRafId = requestAnimationFrame(() => {
            updateSliderTooltip();
            sliderRafId = null;
        });

        if (recommendDebounceTimer) clearTimeout(recommendDebounceTimer);
        recommendDebounceTimer = setTimeout(() => {
            if (currentBookId) {
                loadRecommendations(currentBookId);
            }
            recommendDebounceTimer = null;
        }, 300);
    });

    document.getElementById('bookDetailModal').addEventListener('click', function(e) {
        if (e.target === this) {
            closeBookDetail();
        }
    });

    window.addEventListener('resize', function() {
        if (document.getElementById('recommendPanel').style.display !== 'none') {
            if (sliderRafId) cancelAnimationFrame(sliderRafId);
            sliderRafId = requestAnimationFrame(() => {
                updateSliderTooltip();
                sliderRafId = null;
            });
        }
    });
});

function updateSliderDescription() {
    const descEl = document.getElementById('sliderDesc');
    const desc = betaDescriptions[currentBeta] || betaDescriptions[0.25];
    descEl.textContent = '💡 ' + desc;
}

function updateSliderTooltip() {
    const tooltip = document.getElementById('sliderTooltip');
    if (!tooltip) return;

    tooltip.textContent = currentBeta.toFixed(2);
}

async function loadBooks(page = 1) {
    currentPage = page;
    const searchValue = document.getElementById('searchInput').value;
    const booksGrid = document.getElementById('booksGrid');

    booksGrid.innerHTML = '<div class="loading">加载中...</div>';

    try {
        let url = `/api/books?page=${page}&per_page=${perPage}`;
        if (searchValue) {
            url += `&search=${encodeURIComponent(searchValue)}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            currentBooksData = data.data.books;
            renderBooks(currentBooksData);
            renderPagination(data.data.total_pages, page);
        } else {
            booksGrid.innerHTML = '<div class="loading">加载失败: ' + data.error + '</div>';
        }
    } catch (error) {
        booksGrid.innerHTML = '<div class="loading">加载失败: ' + error.message + '</div>';
    }
}

async function loadSidebarRecommendations() {
    const sidebar = document.getElementById('sidebarRecommendations');

    try {
        const response = await fetch('/api/books?per_page=8&sort_mode=rating');
        const data = await response.json();

        if (data.success && data.data.books.length > 0) {
            sidebar.innerHTML = data.data.books.map(book => `
                <div class="sidebar-book" onclick="openBookDetail(${book.book_id})">
                    <div class="sidebar-book-title" title="${book.title}">${book.title}</div>
                    <div class="sidebar-book-author">${book.authors && book.authors.length > 0 ? book.authors[0] : '未知作者'}</div>
                    ${book.rating ? `<span class="sidebar-book-rating">⭐ ${book.rating}</span>` : ''}
                </div>
            `).join('');
        } else {
            sidebar.innerHTML = '<div class="loading">暂无推荐</div>';
        }
    } catch (error) {
        sidebar.innerHTML = '<div class="loading">加载失败</div>';
    }
}

function renderBooks(books) {
    const booksGrid = document.getElementById('booksGrid');

    if (books.length === 0) {
        const searchValue = document.getElementById('searchInput').value;
        if (searchValue && searchValue.trim()) {
            booksGrid.innerHTML = `
                <div class="no-result-container">
                    <div class="no-result-icon">📚</div>
                    <div class="no-result-title">未找到"${searchValue}"相关书籍</div>
                    <div class="no-result-desc">您可以尝试其他关键词，或通过豆瓣链接添加新书</div>
                    <div class="add-book-section">
                        <input type="text" id="doubanUrlInput"
                               placeholder="请输入豆瓣书籍详情页URL，如 https://book.douban.com/subject/1234567/"
                               class="douban-url-input">
                        <button onclick="addNewBook()" class="add-book-btn" id="addBookBtn">
                            📖 添加新书
                        </button>
                    </div>
                    <div id="addBookStatus" class="add-book-status" style="display:none;"></div>
                </div>
            `;
        } else {
            booksGrid.innerHTML = '<div class="loading">暂无图书数据</div>';
        }
        return;
    }

    let sorted = [...books];
    if (currentBookId) {
        const idx = sorted.findIndex(b => b.book_id === currentBookId);
        if (idx > 0) {
            const [selected] = sorted.splice(idx, 1);
            sorted.unshift(selected);
        }
    }

    booksGrid.innerHTML = sorted.map(book => {
        const isSelected = book.book_id === currentBookId;
        return `
        <div class="book-card ${isSelected ? 'book-card-selected' : ''}" data-book-id="${book.book_id}" onclick="handleCardClick(event, ${book.book_id})">
            <div class="book-cover">
                ${book.cover_image
                    ? `<img src="${book.cover_image}" alt="${book.title}"
                           onerror="this.onerror=null; this.src='${defaultCoverUrl}'; this.alt='封面加载失败';">`
                    : `<img src="${defaultCoverUrl}" alt="暂无封面">`}
                <div class="book-cover-overlay">
                    <button class="cover-action-btn cover-detail-btn" onclick="event.stopPropagation(); openBookDetail(${book.book_id})">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        查看详情
                    </button>
                    <button class="cover-action-btn cover-recommend-btn" onclick="event.stopPropagation(); selectBook(${book.book_id})">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
                        跨域推荐
                    </button>
                </div>
                ${isSelected ? '<div class="book-selected-badge">✓ 已选中</div>' : ''}
            </div>
            <div class="book-info">
                <div class="book-title" title="${book.title}">${book.title}</div>
                <div class="book-author">${book.authors && book.authors.length > 0 ? book.authors.join(', ') : '未知作者'}</div>
                <div class="book-meta-row">
                    ${book.rating ? `<span class="book-rating">⭐ ${book.rating}</span>` : ''}
                    ${book.domain_tags && book.domain_tags.length > 0 ? `
                        <span class="book-tags">
                            ${book.domain_tags.slice(0, 3).map(tag => `<span class="tag">${tag}</span>`).join('')}
                        </span>
                    ` : ''}
                </div>
            </div>
            <div class="book-card-overlay">
                <button class="card-overlay-btn card-overlay-detail" onclick="event.stopPropagation(); openBookDetail(${book.book_id})">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                    详情
                </button>
                <button class="card-overlay-btn card-overlay-recommend" onclick="event.stopPropagation(); selectBook(${book.book_id})">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
                    推荐
                </button>
            </div>
        </div>
    `}).join('') + `
        <div class="add-book-inline-entry" onclick="toggleInlineAddBook()">
            <div class="add-book-inline-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></div>
            <div class="add-book-inline-text">没有找到想要的书籍？点击添加新书</div>
            <div class="add-book-inline-arrow"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg></div>
        </div>
        <div id="inlineAddBookPanel" class="inline-add-book-panel">
            <div class="add-book-section">
                <input type="text" id="inlineDoubanUrlInput"
                       placeholder="请输入豆瓣书籍详情页URL"
                       class="douban-url-input">
                <button onclick="addNewBookInline()" class="add-book-btn" id="inlineAddBookBtn">
                    📖 添加新书
                </button>
            </div>
            <div id="inlineAddBookStatus" class="add-book-status" style="display:none;"></div>
        </div>
    `;
}

function toggleInlineAddBook() {
    const panel = document.getElementById('inlineAddBookPanel');
    const entry = document.querySelector('.add-book-inline-entry');
    if (panel) {
        panel.classList.toggle('active');
    }
    if (entry) {
        entry.classList.toggle('entry-expanded');
    }
}

function renderPagination(totalPages, currentPage) {
    const pagination = document.getElementById('pagination');

    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }

    let html = '';

    if (currentPage > 1) {
        html += `<button onclick="loadBooks(${currentPage - 1})">上一页</button>`;
    }

    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);

    if (startPage > 1) {
        html += `<button onclick="loadBooks(1)">1</button>`;
        if (startPage > 2) html += '<span>...</span>';
    }

    for (let i = startPage; i <= endPage; i++) {
        if (i === currentPage) {
            html += `<button class="active">${i}</button>`;
        } else {
            html += `<button onclick="loadBooks(${i})">${i}</button>`;
        }
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) html += '<span>...</span>';
        html += `<button onclick="loadBooks(${totalPages})">${totalPages}</button>`;
    }

    if (currentPage < totalPages) {
        html += `<button onclick="loadBooks(${currentPage + 1})">下一页</button>`;
    }

    pagination.innerHTML = html;
}

async function selectBook(bookId) {
    currentBookId = bookId;

    renderBooks(currentBooksData);

    document.getElementById('defaultPanel').style.display = 'none';
    document.getElementById('recommendPanel').style.display = 'flex';
    document.getElementById('bubbleIntro').style.display = 'none';
    document.getElementById('booksGridTitle').style.display = 'block';

    document.getElementById('leftSection').classList.add('left-section-narrow');
    document.getElementById('rightSection').classList.add('right-section-wide');

    setTimeout(() => updateSliderTooltip(), 0);

    document.getElementById('crossDomainRecommendations').innerHTML = '<div class="loading">加载中...</div>';
    document.getElementById('domainDistribution').style.display = 'none';

    try {
        const response = await fetch(`/api/books/${bookId}`);
        const data = await response.json();

        if (data.success) {
            loadRecommendations(bookId);
        }
    } catch (error) {
        console.error(error);
    }
}

function handleCardClick(event, bookId) {
    if (currentBookId !== null) {
        selectBook(bookId);
    }
}

function deselectBook() {
    currentBookId = null;

    renderBooks(currentBooksData);

    document.getElementById('defaultPanel').style.display = 'block';
    document.getElementById('recommendPanel').style.display = 'none';
    document.getElementById('bubbleIntro').style.display = 'block';
    document.getElementById('booksGridTitle').style.display = 'none';

    document.getElementById('leftSection').classList.remove('left-section-narrow');
    document.getElementById('rightSection').classList.remove('right-section-wide');
}

async function loadRecommendations(bookId) {
    const crossDomainList = document.getElementById('crossDomainRecommendations');
    const domainDistEl = document.getElementById('domainDistribution');
    const recommendSortModeEl = document.getElementById('recommendSortMode');
    const recommendSortMode = recommendSortModeEl ? recommendSortModeEl.value : 'comprehensive';

    crossDomainList.innerHTML = '<div class="loading">加载中...</div>';
    domainDistEl.style.display = 'none';

    try {
        const response = await fetch(`/api/recommend/${bookId}?top_k=6&cross_domain=true&beta=${currentBeta}&sort_mode=${recommendSortMode}`);
        const data = await response.json();

        if (data.success && data.data.recommendations.length > 0) {
            const recommendations = data.data.recommendations;
            currentRecommendationsData = recommendations;
            const domainDist = data.data.domain_distribution || {};

            const domainEntries = Object.entries(domainDist);
            if (domainEntries.length > 0) {
                domainDistEl.innerHTML = '<span class="domain-dist-label">覆盖领域:</span> ' +
                    domainEntries.map(([domain, count]) =>
                        `<span class="domain-dist-tag">${domain}(${count})</span>`
                    ).join(' ');
                domainDistEl.style.display = 'block';
            }

            crossDomainList.innerHTML = recommendations.map(book => renderRecommendationItem(book)).join('');
        } else {
            crossDomainList.innerHTML = '<div class="loading">暂无跨域推荐</div>';
        }
    } catch (error) {
        console.error('加载跨域推荐失败:', error);
        crossDomainList.innerHTML = `<div class="loading">加载跨域推荐失败: ${error.message || '网络错误'}</div>`;
    }
}

function renderRecommendationItem(book) {
    const domainTags = book.domain_tags && book.domain_tags.length > 0
        ? book.domain_tags.map(tag => `<span class="rec-domain-tag">${tag}</span>`).join('')
        : '';
    const overlapInfo = book.overlap_count !== undefined
        ? `<span class="rec-overlap ${book.overlap_count === 0 ? 'rec-overlap-full' : 'rec-overlap-partial'}">${book.overlap_count === 0 ? '完全跨域' : '部分跨域'}</span>`
        : '';

    const recommendSortModeEl = document.getElementById('recommendSortMode');
    const sortMode = recommendSortModeEl ? recommendSortModeEl.value : 'comprehensive';
    const displayScore = sortMode === 'similarity'
        ? (book.similarity_score || book.final_score || 0)
        : (book.utility_score || book.final_score || 0);

    return `
        <div class="recommendation-item" onclick="openBookDetail(${book.book_id})">
            <div class="recommendation-cover">
                ${book.cover_image
                    ? `<img src="${book.cover_image}" alt="${book.title}"
                           onerror="this.onerror=null; this.src='${defaultCoverUrl}'; this.alt='封面加载失败';">`
                    : `<img src="${defaultCoverUrl}" alt="暂无封面">`}
            </div>
            <div class="recommendation-info">
                <div class="recommendation-title" title="${book.title}">${book.title}</div>
                <div class="recommendation-meta">
                    <span class="recommendation-score">推荐度: ${(displayScore * 100).toFixed(1)}%</span>
                    ${overlapInfo}
                </div>
                <div class="recommendation-domains">${domainTags}</div>
                <button class="reason-btn" onclick="event.stopPropagation(); toggleRecommendReason(${currentBookId}, ${book.book_id}, this)">
                    💡 推荐理由
                </button>
                <div class="recommendation-reason" id="reason-${book.book_id}" style="display: none;"></div>
            </div>
        </div>
    `;
}

async function toggleRecommendReason(sourceBookId, recommendedBookId, btnElement) {
    const reasonDiv = document.getElementById(`reason-${recommendedBookId}`);

    if (reasonDiv.style.display !== 'none') {
        reasonDiv.style.display = 'none';
        btnElement.textContent = '💡 推荐理由';
        btnElement.classList.remove('reason-btn-active');
        return;
    }

    if (reasonDiv.dataset.loaded === 'true') {
        reasonDiv.style.display = 'block';
        btnElement.textContent = '💡 收起理由';
        btnElement.classList.add('reason-btn-active');
        return;
    }

    reasonDiv.innerHTML = '<div class="reason-loading"><span class="reason-loading-dot"></span> AI正在生成推荐理由...</div>';
    reasonDiv.style.display = 'block';
    btnElement.textContent = '💡 收起理由';
    btnElement.classList.add('reason-btn-active');

    try {
        const similarityData = {
            semantic_similarity: 0,
            keyword_similarity: 0,
            overlap_count: 0,
            overlap_coefficient: 1,
            combined_similarity: 0
        };

        const recBook = currentRecommendationsData.find(b => b.book_id === recommendedBookId);
        if (recBook) {
            similarityData.semantic_similarity = recBook.semantic_similarity || 0;
            similarityData.keyword_similarity = recBook.keyword_similarity || 0;
            similarityData.overlap_count = recBook.overlap_count || 0;
            similarityData.overlap_coefficient = recBook.overlap_coefficient || 1;
            similarityData.combined_similarity = recBook.combined_similarity || 0;
        }

        const response = await fetch('/api/recommend-reason', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_book_id: sourceBookId,
                recommended_book_id: recommendedBookId,
                similarity_data: similarityData,
                beta: currentBeta
            })
        });

        const data = await response.json();

        if (data.success) {
            const fallbackBadge = data.data.is_fallback
                ? '<span class="reason-fallback-badge">模板生成</span>'
                : '<span class="reason-ai-badge">AI生成</span>';
            reasonDiv.innerHTML = `
                <div class="reason-header">${fallbackBadge} 推荐理由</div>
                <div class="reason-text">${data.data.reason}</div>
            `;
            reasonDiv.dataset.loaded = 'true';
        } else {
            reasonDiv.innerHTML = `<div class="reason-error">生成失败: ${data.error}</div>`;
        }
    } catch (error) {
        reasonDiv.innerHTML = `<div class="reason-error">网络错误: ${error.message}</div>`;
    }
}

async function openBookDetail(bookId) {
    const modal = document.getElementById('bookDetailModal');
    const content = document.getElementById('bookDetailContent');

    modal.style.display = 'flex';
    content.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const response = await fetch(`/api/books/${bookId}`);
        const data = await response.json();

        if (data.success) {
            const book = data.data;
            content.innerHTML = `
                <button class="detail-close-btn" onclick="closeBookDetail()">✕</button>
                <div class="detail-header">
                    <div class="detail-cover">
                        ${book.cover_image
                            ? `<img src="${book.cover_image}" alt="${book.title}"
                                   onerror="this.onerror=null; this.src='${defaultCoverUrl}'; this.alt='封面加载失败';">`
                            : `<img src="${defaultCoverUrl}" alt="暂无封面">`}
                    </div>
                    <div class="detail-main">
                        <div class="detail-title">${book.title}</div>
                        <div class="detail-author">${book.authors && book.authors.length > 0 ? book.authors.join(', ') : '未知作者'}</div>
                        <div class="detail-meta">
                            ${book.rating ? `<span class="detail-rating">⭐ ${book.rating}</span>` : ''}
                            ${book.publisher ? `<span class="detail-publisher">${book.publisher}</span>` : ''}
                            ${book.publication_date ? `<span class="detail-date">${book.publication_date}</span>` : ''}
                        </div>
                        ${book.domain_tags && book.domain_tags.length > 0 ? `
                            <div class="detail-tags">
                                ${book.domain_tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                            </div>
                        ` : ''}
                        <button class="detail-recommend-btn" onclick="closeBookDetail(); selectBook(${book.book_id})">🎯 查看跨域推荐</button>
                    </div>
                </div>
                ${book.book_intro ? `
                    <div class="detail-section">
                        <div class="detail-section-title">📖 内容简介</div>
                        <div class="detail-section-content">${book.book_intro}</div>
                    </div>
                ` : ''}
                ${book.author_intro ? `
                    <div class="detail-section">
                        <div class="detail-section-title">👤 作者简介</div>
                        <div class="detail-section-content">${book.author_intro}</div>
                    </div>
                ` : ''}
            `;
        } else {
            content.innerHTML = '<div class="loading">加载失败</div>';
        }
    } catch (error) {
        content.innerHTML = '<div class="loading">加载失败</div>';
    }
}

function closeBookDetail() {
    document.getElementById('bookDetailModal').style.display = 'none';
}

function searchBooks() {
    loadBooks(1);
}

function validateDoubanUrl(url) {
    const pattern = /^https?:\/\/book\.douban\.com\/subject\/\d+\/?/;
    return pattern.test(url.trim());
}

async function addNewBook() {
    const urlInput = document.getElementById('doubanUrlInput');
    const statusDiv = document.getElementById('addBookStatus');
    const btn = document.getElementById('addBookBtn');

    if (!urlInput || !statusDiv || !btn) return;

    const url = urlInput.value.trim();

    if (!url) {
        showAddBookStatus('error', '请输入豆瓣书籍详情页URL', statusDiv);
        return;
    }
    if (!validateDoubanUrl(url)) {
        showAddBookStatus('error', 'URL格式不正确，请输入有效的豆瓣书籍详情页地址', statusDiv);
        return;
    }

    btn.disabled = true;
    btn.textContent = '⏳ 处理中...';
    showAddBookStatus('loading', '正在采集书籍信息...', statusDiv);

    try {
        const response = await fetch('/api/books/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ douban_url: url })
        });
        const data = await response.json();

        if (data.success) {
            showAddBookStatus('success', `《${data.data.title}》添加成功！正在加载跨域推荐...`, statusDiv);
            document.getElementById('searchInput').value = '';
            selectBook(data.data.book_id);
        } else {
            showAddBookStatus('error', data.error || '添加失败', statusDiv);
            btn.disabled = false;
            btn.textContent = '📖 添加新书';
        }
    } catch (error) {
        showAddBookStatus('error', '网络错误: ' + error.message, statusDiv);
        btn.disabled = false;
        btn.textContent = '📖 添加新书';
    }
}

async function addNewBookInline() {
    const urlInput = document.getElementById('inlineDoubanUrlInput');
    const statusDiv = document.getElementById('inlineAddBookStatus');
    const btn = document.getElementById('inlineAddBookBtn');

    if (!urlInput || !statusDiv || !btn) return;

    const url = urlInput.value.trim();

    if (!url) {
        showAddBookStatus('error', '请输入豆瓣书籍详情页URL', statusDiv);
        return;
    }
    if (!validateDoubanUrl(url)) {
        showAddBookStatus('error', 'URL格式不正确，请输入有效的豆瓣书籍详情页地址', statusDiv);
        return;
    }

    btn.disabled = true;
    btn.textContent = '⏳ 处理中...';
    showAddBookStatus('loading', '正在采集书籍信息...', statusDiv);

    try {
        const response = await fetch('/api/books/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ douban_url: url })
        });
        const data = await response.json();

        if (data.success) {
            showAddBookStatus('success', `《${data.data.title}》添加成功！正在加载跨域推荐...`, statusDiv);
            selectBook(data.data.book_id);
        } else {
            showAddBookStatus('error', data.error || '添加失败', statusDiv);
            btn.disabled = false;
            btn.textContent = '📖 添加新书';
        }
    } catch (error) {
        showAddBookStatus('error', '网络错误: ' + error.message, statusDiv);
        btn.disabled = false;
        btn.textContent = '📖 添加新书';
    }
}

function showAddBookStatus(type, message, targetDiv) {
    if (!targetDiv) {
        targetDiv = document.getElementById('addBookStatus');
    }
    if (!targetDiv) return;
    targetDiv.style.display = 'block';
    const icons = { loading: '', success: '✅', error: '❌' };
    targetDiv.className = `add-book-status status-${type}`;
    if (type === 'loading') {
        targetDiv.innerHTML = `<span class="reason-loading-dot"></span> ${message}`;
    } else {
        targetDiv.innerHTML = `${icons[type]} ${message}`;
    }
}

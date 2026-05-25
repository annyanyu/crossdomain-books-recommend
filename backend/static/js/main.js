let currentPage = 1;
let currentBookId = null;
let currentBeta = 0.25;
let currentBooksData = [];
const perPage = 20;

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

    document.getElementById('searchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchBooks();
        }
    });

    document.getElementById('betaSlider').addEventListener('input', function() {
        currentBeta = parseInt(this.value) / 100;
        updateSliderDescription();
        if (currentBookId) {
            loadRecommendations(currentBookId);
        }
    });

    document.getElementById('bookDetailModal').addEventListener('click', function(e) {
        if (e.target === this) {
            closeBookDetail();
        }
    });

    window.addEventListener('resize', function() {
        if (document.getElementById('recommendPanel').style.display !== 'none') {
            updateSliderTooltip();
        }
    });
});

function updateSliderDescription() {
    const descEl = document.getElementById('sliderDesc');
    const desc = betaDescriptions[currentBeta] || betaDescriptions[0.25];
    descEl.textContent = '💡 ' + desc;
    updateSliderTooltip();
}

function updateSliderTooltip() {
    const slider = document.getElementById('betaSlider');
    const tooltip = document.getElementById('sliderTooltip');
    const min = parseFloat(slider.min);
    const max = parseFloat(slider.max);
    const val = parseFloat(slider.value);
    const percent = (val - min) / (max - min);
    const sliderWidth = slider.offsetWidth;
    const thumbHalf = 10;
    const left = percent * (sliderWidth - thumbHalf * 2) + thumbHalf;
    tooltip.textContent = currentBeta.toFixed(2);
    tooltip.style.left = left + 'px';
    tooltip.style.transform = 'translateX(-50%)';
}

async function loadBooks(page = 1) {
    currentPage = page;
    const searchValue = document.getElementById('searchInput').value;
    const sortMode = document.getElementById('sortMode').value;
    const booksGrid = document.getElementById('booksGrid');

    booksGrid.innerHTML = '<div class="loading">加载中...</div>';

    try {
        let url = `/api/books?page=${page}&per_page=${perPage}&sort_mode=${sortMode}`;
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
        booksGrid.innerHTML = '<div class="loading">暂无图书数据</div>';
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
                </div>
                ${book.domain_tags && book.domain_tags.length > 0 ? `
                    <div class="book-tags">
                        ${book.domain_tags.slice(0, 3).map(tag => `<span class="tag">${tag}</span>`).join('')}
                    </div>
                ` : ''}
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
    `}).join('');
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

    document.getElementById('leftSection').classList.add('left-section-narrow');
    document.getElementById('rightSection').classList.add('right-section-wide');

    document.getElementById('selectedBookCard').innerHTML = '<div class="loading">加载中...</div>';
    document.getElementById('crossDomainRecommendations').innerHTML = '<div class="loading">加载中...</div>';
    document.getElementById('domainDistribution').style.display = 'none';

    try {
        const response = await fetch(`/api/books/${bookId}`);
        const data = await response.json();

        if (data.success) {
            renderSelectedBookCard(data.data);
            loadRecommendations(bookId);
        } else {
            document.getElementById('selectedBookCard').innerHTML = '<div class="loading">加载失败</div>';
        }
    } catch (error) {
        document.getElementById('selectedBookCard').innerHTML = '<div class="loading">加载失败</div>';
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

    document.getElementById('leftSection').classList.remove('left-section-narrow');
    document.getElementById('rightSection').classList.remove('right-section-wide');
}

function renderSelectedBookCard(book) {
    const card = document.getElementById('selectedBookCard');
    card.innerHTML = `
        <div class="selected-book-cover">
            ${book.cover_image
                ? `<img src="${book.cover_image}" alt="${book.title}"
                       onerror="this.onerror=null; this.src='${defaultCoverUrl}'; this.alt='封面加载失败';">`
                : `<img src="${defaultCoverUrl}" alt="暂无封面">`}
        </div>
        <div class="selected-book-info">
            <div class="selected-book-title" title="${book.title}">${book.title}</div>
            <div class="selected-book-author">${book.authors && book.authors.length > 0 ? book.authors.join(', ') : '未知作者'}</div>
            <div class="selected-book-meta">
                ${book.rating ? `<span class="selected-book-rating">⭐ ${book.rating}</span>` : ''}
                ${book.publisher ? `<span class="selected-book-publisher">${book.publisher}</span>` : ''}
            </div>
            ${book.domain_tags && book.domain_tags.length > 0 ? `
                <div class="selected-book-tags">
                    ${book.domain_tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                </div>
            ` : ''}
        </div>
    `;
}

async function loadRecommendations(bookId) {
    const crossDomainList = document.getElementById('crossDomainRecommendations');
    const domainDistEl = document.getElementById('domainDistribution');

    crossDomainList.innerHTML = '<div class="loading">加载中...</div>';
    domainDistEl.style.display = 'none';

    try {
        const response = await fetch(`/api/recommend/${bookId}?top_k=6&cross_domain=true&beta=${currentBeta}`);
        const data = await response.json();

        if (data.success && data.data.recommendations.length > 0) {
            const recommendations = data.data.recommendations;
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
        crossDomainList.innerHTML = '<div class="loading">加载跨域推荐失败</div>';
    }
}

function renderRecommendationItem(book) {
    const domainTags = book.domain_tags && book.domain_tags.length > 0
        ? book.domain_tags.map(tag => `<span class="rec-domain-tag">${tag}</span>`).join('')
        : '';
    const overlapInfo = book.overlap_count !== undefined
        ? `<span class="rec-overlap ${book.overlap_count === 0 ? 'rec-overlap-full' : 'rec-overlap-partial'}">${book.overlap_count === 0 ? '完全跨域' : '部分跨域'}</span>`
        : '';

    const sortMode = document.getElementById('sortMode').value;
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
            </div>
        </div>
    `;
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

const defaultCoverUrl = 'https://via.placeholder.com/200x300?text=No+Cover';

const pieColors = [
    '#5b6abf',
    '#3b82f6',
    '#0891b2',
    '#0d9488',
    '#16a34a',
    '#65a30d',
    '#ca8a04',
    '#ea580c',
    '#dc2626',
    '#e11d48',
    '#c026d3',
    '#9333ea',
    '#7c3aed',
    '#4f46e5',
    '#0284c7',
    '#059669',
    '#4d7c0f',
    '#b45309',
    '#be123c',
    '#7e22ce',
];

document.addEventListener('DOMContentLoaded', function() {
    loadStats();
});

async function loadStats() {
    try {
        const response = await fetch('/api/stats/detail');
        const data = await response.json();

        if (data.success) {
            renderOverview(data.data);
            renderPieChart(data.data.domain_distribution, data.data.total_books);
            renderTopBooks(data.data.top_rated_books);
        } else {
            document.querySelectorAll('.chart-loading').forEach(el => {
                el.textContent = '加载失败: ' + data.error;
            });
        }
    } catch (error) {
        document.querySelectorAll('.chart-loading').forEach(el => {
            el.textContent = '加载失败: ' + error.message;
        });
    }
}

function renderOverview(data) {
    animateValue('totalBooks', data.total_books);
    document.getElementById('avgRating').textContent = data.avg_rating.toFixed(1);
    animateValue('totalDomains', data.total_domains);
    animateValue('recentBooks', data.recent_books);
}

function animateValue(elementId, target) {
    const el = document.getElementById(elementId);
    const duration = 800;
    const start = 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + (target - start) * eased);
        el.textContent = current;
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    requestAnimationFrame(update);
}

function renderPieChart(domainDistribution, totalBooks) {
    const entries = Object.entries(domainDistribution).sort((a, b) => b[1] - a[1]);

    if (entries.length === 0) {
        document.getElementById('pieLegend').innerHTML = '<div class="chart-loading">暂无领域数据</div>';
        return;
    }

    const svg = document.getElementById('pieChartSvg');
    const legendContainer = document.getElementById('pieLegend');
    const centerValue = document.getElementById('pieCenterValue');

    const radius = 74;
    const circumference = 2 * Math.PI * radius;

    let cumulativeOffset = 0;
    const segments = [];

    entries.forEach(([domain, count], index) => {
        const percentage = count / totalBooks;
        const dashLength = percentage * circumference;
        const color = pieColors[index % pieColors.length];

        segments.push({
            domain,
            count,
            percentage,
            dashLength,
            color,
            offset: cumulativeOffset,
        });

        cumulativeOffset += dashLength;
    });

    svg.innerHTML = segments.map((seg, i) => {
        return `<circle cx="100" cy="100" r="${radius}" class="pie-segment" 
            stroke="${seg.color}" 
            stroke-dasharray="${seg.dashLength} ${circumference - seg.dashLength}" 
            stroke-dashoffset="${-seg.offset}"
            data-domain="${seg.domain}" 
            data-count="${seg.count}" 
            data-percentage="${(seg.percentage * 100).toFixed(1)}"
            style="opacity: 0; transition: opacity 0.4s ease ${i * 0.06}s;">
        </circle>`;
    }).join('');

    setTimeout(() => {
        svg.querySelectorAll('.pie-segment').forEach(seg => {
            seg.style.opacity = '1';
        });
    }, 50);

    animateValue('pieCenterValue', totalBooks);

    legendContainer.innerHTML = segments.map((seg) => {
        const pct = (seg.percentage * 100).toFixed(1);
        return `
            <div class="legend-item" data-domain="${seg.domain}">
                <div class="legend-color" style="background: ${seg.color};"></div>
                <div class="legend-info">
                    <div class="legend-name" title="${seg.domain}">${seg.domain}</div>
                    <div class="legend-detail">${seg.count} 本 · ${pct}%</div>
                </div>
            </div>
        `;
    }).join('');

    const tooltip = document.getElementById('pieTooltip');

    svg.querySelectorAll('.pie-segment').forEach(seg => {
        seg.addEventListener('mouseenter', function(e) {
            const domain = this.getAttribute('data-domain');
            const count = this.getAttribute('data-count');
            const pct = this.getAttribute('data-percentage');
            tooltip.innerHTML = `<strong>${domain}</strong><br>${count} 本 · ${pct}%`;
            tooltip.style.display = 'block';
            positionTooltip(e);
        });

        seg.addEventListener('mousemove', function(e) {
            positionTooltip(e);
        });

        seg.addEventListener('mouseleave', function() {
            tooltip.style.display = 'none';
        });
    });

    function positionTooltip(e) {
        const x = e.clientX;
        const y = e.clientY;
        tooltip.style.left = x + 'px';
        tooltip.style.top = (y - 50) + 'px';
    }
}

function renderTopBooks(books) {
    const container = document.getElementById('topBooksScroll');

    if (!books || books.length === 0) {
        container.innerHTML = '<div class="chart-loading">暂无高评分图书</div>';
        return;
    }

    container.innerHTML = books.map(book => `
        <div class="top-book-card" onclick="window.location.href='/'">
            <div class="top-book-cover">
                ${book.cover_image
                    ? `<img src="${book.cover_image}" alt="${book.title}"
                           onerror="this.onerror=null; this.src='${defaultCoverUrl}';">`
                    : `<img src="${defaultCoverUrl}" alt="暂无封面">`}
            </div>
            <div class="top-book-info">
                <div class="top-book-title" title="${book.title}">${book.title}</div>
                <span class="top-book-rating">⭐ ${book.rating}</span>
                ${book.domain_tags ? `
                    <div class="top-book-tags">
                        ${book.domain_tags.split(/\s+/).slice(0, 2).map(tag => `<span class="tag">${tag}</span>`).join('')}
                    </div>
                ` : ''}
            </div>
        </div>
    `).join('');
}

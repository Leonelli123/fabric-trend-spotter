/* Fabric Trend Spotter - Dashboard JS v2 */

const CHART_COLORS = [
    '#6c63ff', '#ec4899', '#22c55e', '#eab308', '#f97316',
    '#3b82f6', '#8b5cf6', '#14b8a6', '#f43f5e', '#a855f7',
];

/* ==========================================
   CHARTS
   ========================================== */

function initCharts(fabricData, patternData, colorData, styleData) {
    const opts = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: { legend: { display: false } },
        scales: {
            y: { beginAtZero: true, grid: { color: 'rgba(42,46,63,0.5)' }, ticks: { color: '#8b8fa3' } },
            x: { grid: { display: false }, ticks: { color: '#8b8fa3', maxRotation: 45, font: { size: 10 } } },
        },
    };
    createBarChart('fabric-chart', fabricData, opts);
    createBarChart('pattern-chart', patternData, opts);
    createBarChart('color-chart', colorData, opts);
    if (styleData) createBarChart('style-chart', styleData, opts);
}

function createBarChart(id, data, options) {
    const canvas = document.getElementById(id);
    if (!canvas || !data.length) return null;
    const labels = data.slice(0, 10).map(d => cap(d.term));
    const scores = data.slice(0, 10).map(d => d.score);
    const colors = scores.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]);
    return new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{ data: scores, backgroundColor: colors.map(c => c + '40'), borderColor: colors, borderWidth: 2, borderRadius: 6 }],
        },
        options,
    });
}

function cap(s) { return s.replace(/\b\w/g, l => l.toUpperCase()); }

/* ==========================================
   SCRAPE
   ========================================== */

async function triggerScrape() {
    const btn = document.getElementById('scrape-btn');
    const banner = document.getElementById('status-banner');
    const statusText = document.getElementById('status-text');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Collecting Data...';
    banner.className = 'status-banner info';
    statusText.textContent = 'Loading baseline data, checking live sources & Google Trends, running forecasts... This may take a few minutes.';

    try {
        const resp = await fetch('/api/scrape', { method: 'POST' });
        const data = await resp.json();
        if (data.status === 'already_running') {
            statusText.textContent = 'A scrape is already in progress...';
            return;
        }
        pollStatus();
    } catch (err) {
        banner.className = 'status-banner error';
        statusText.textContent = 'Error: ' + err.message;
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">&#x21bb;</span> Refresh Data';
    }
}

async function pollStatus() {
    const btn = document.getElementById('scrape-btn');
    const banner = document.getElementById('status-banner');
    const statusText = document.getElementById('status-text');
    try {
        const resp = await fetch('/api/status');
        const data = await resp.json();
        if (data.running) { setTimeout(pollStatus, 3000); return; }
        if (data.error) {
            banner.className = 'status-banner error';
            statusText.textContent = 'Error: ' + data.error;
        } else if (data.last_result) {
            banner.className = 'status-banner success';
            const r = data.last_result;
            const parts = [`${r.total_listings} listings analyzed`];
            if (r.google_keywords > 0) parts.push(`${r.google_keywords} Google keywords`);
            if (r.live_listings > 0) parts.push(`${r.live_listings} live`);
            if (r.failed_sources && r.failed_sources.length > 0) {
                parts.push(`${r.failed_sources.join(', ')} unavailable`);
            }
            statusText.textContent = parts.join(' · ') + ' — Reloading...';
            setTimeout(() => window.location.reload(), 2500);
        } else {
            banner.className = 'status-banner success';
            statusText.textContent = 'Data refreshed! Reloading...';
            setTimeout(() => window.location.reload(), 1500);
        }
    } catch (err) { setTimeout(pollStatus, 5000); return; }
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">&#x21bb;</span> Refresh Data';
}

/* ==========================================
   NAVIGATION
   ========================================== */

function scrollToSection(id) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.querySelector(`.nav-link[href="#${id}"]`)?.classList.add('active');
}

/* ==========================================
   TABS
   ========================================== */

function switchTab(tabName) {
    document.querySelectorAll('.table-tabs .tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelector(`[data-tab="${tabName}"]`)?.classList.add('active');
    document.getElementById(`tab-${tabName}`)?.classList.add('active');
}

/* ==========================================
   EUROPEAN MARKETS
   ========================================== */

function switchEU(key) {
    document.querySelectorAll('.eu-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.eu-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`[data-eu="${key}"]`)?.classList.add('active');
    document.getElementById(`eu-${key}`)?.classList.add('active');
}

/* ==========================================
   SEGMENTS
   ========================================== */

function switchSegment(seg) {
    document.querySelectorAll('.segment-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.segment-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`[data-segment="${seg}"]`)?.classList.add('active');
    document.getElementById(`seg-${seg}`)?.classList.add('active');
}

/* ==========================================
   ACTION BOARD (unified - no role tabs needed)
   ========================================== */

/* ==========================================
   GALLERY FILTER
   ========================================== */

function filterGallery(category) {
    document.querySelectorAll('.gallery-filters .filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');

    document.querySelectorAll('.gallery-item').forEach(item => {
        if (category === 'all' || item.dataset.category === category) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}

/* ==========================================
   LISTINGS
   ========================================== */

async function loadListings(source) {
    const container = document.getElementById('listings-container');
    if (!container) return;
    let url = '/api/listings?limit=60';
    if (source && source !== 'all') url += '&source=' + source;

    try {
        const resp = await fetch(url);
        const listings = await resp.json();
        if (!listings.length) {
            container.innerHTML = '<div class="empty-state"><p>No listings yet. Run a scrape first.</p></div>';
            return;
        }
        container.innerHTML = listings.map(l => `
            <div class="listing-card">
                <div class="listing-source">${esc(l.source)}</div>
                <div class="listing-title">
                    ${l.url ? `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title)}</a>` : esc(l.title)}
                </div>
                <div class="listing-meta">
                    ${l.price ? `<span>$${l.price.toFixed(2)}</span>` : ''}
                    ${l.favorites ? `<span>${l.favorites} favs</span>` : ''}
                    ${l.reviews ? `<span>${l.reviews} reviews</span>` : ''}
                </div>
                <div class="listing-tags">
                    ${(JSON.parse(l.tags || '[]')).slice(0, 5).map(t => `<span class="listing-tag">${esc(t)}</span>`).join('')}
                </div>
            </div>
        `).join('');
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>Error: ${err.message}</p></div>`;
    }
}

function filterListings(source) {
    document.querySelectorAll('.listing-filters .filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    loadListings(source);
}

function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

/* Load listings on scroll to section */
const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
        if (e.isIntersecting && e.target.id === 'data') loadListings('all');
    });
}, { threshold: 0.1 });

document.addEventListener('DOMContentLoaded', () => {
    const dataSection = document.getElementById('data');
    if (dataSection) observer.observe(dataSection);
});

/* Fabric Trend Spotter - Dashboard JavaScript */

const CHART_COLORS = [
    '#6c63ff', '#ec4899', '#22c55e', '#eab308', '#f97316',
    '#3b82f6', '#8b5cf6', '#14b8a6', '#f43f5e', '#a855f7',
    '#06b6d4', '#84cc16', '#d946ef', '#0ea5e9', '#fb923c',
];

let fabricChart, patternChart, colorChart;

function initCharts(fabricData, patternData, colorData) {
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: { display: false },
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: { color: 'rgba(42, 46, 63, 0.5)' },
                ticks: { color: '#8b8fa3' },
            },
            x: {
                grid: { display: false },
                ticks: {
                    color: '#8b8fa3',
                    maxRotation: 45,
                    font: { size: 10 },
                },
            },
        },
    };

    fabricChart = createBarChart('fabric-chart', fabricData, chartOptions);
    patternChart = createBarChart('pattern-chart', patternData, chartOptions);
    colorChart = createBarChart('color-chart', colorData, chartOptions);
}

function createBarChart(canvasId, data, options) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const labels = data.slice(0, 10).map(d => capitalize(d.term));
    const scores = data.slice(0, 10).map(d => d.score);
    const colors = scores.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]);

    return new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                data: scores,
                backgroundColor: colors.map(c => c + '40'),
                borderColor: colors,
                borderWidth: 2,
                borderRadius: 6,
            }],
        },
        options: options,
    });
}

function capitalize(str) {
    return str.replace(/\b\w/g, l => l.toUpperCase());
}

/* Scrape trigger */
async function triggerScrape() {
    const btn = document.getElementById('scrape-btn');
    const banner = document.getElementById('status-banner');
    const statusText = document.getElementById('status-text');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Scraping...';

    banner.className = 'status-banner info';
    statusText.textContent = 'Scraping data from Etsy, Amazon, and Spoonflower... This may take a few minutes.';

    try {
        const resp = await fetch('/api/scrape', { method: 'POST' });
        const data = await resp.json();

        if (data.status === 'already_running') {
            statusText.textContent = 'A scrape is already in progress. Please wait...';
            return;
        }

        // Poll for completion
        pollStatus();
    } catch (err) {
        banner.className = 'status-banner error';
        statusText.textContent = 'Error starting scrape: ' + err.message;
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

        if (data.running) {
            setTimeout(pollStatus, 3000);
            return;
        }

        if (data.error) {
            banner.className = 'status-banner error';
            statusText.textContent = 'Scrape error: ' + data.error;
        } else {
            banner.className = 'status-banner success';
            statusText.textContent = 'Data refreshed successfully! Reloading...';
            setTimeout(() => window.location.reload(), 1500);
        }
    } catch (err) {
        setTimeout(pollStatus, 5000);
        return;
    }

    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">&#x21bb;</span> Refresh Data';
}

/* Tab switching */
function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));

    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');

    if (tabName === 'listings') {
        loadListings();
    }
}

/* Listings */
let listingsLoaded = false;

async function loadListings(source) {
    const container = document.getElementById('listings-container');
    if (!container) return;

    let url = '/api/listings?limit=60';
    if (source && source !== 'all') {
        url += '&source=' + source;
    }

    try {
        const resp = await fetch(url);
        const listings = await resp.json();

        if (!listings.length) {
            container.innerHTML = '<div class="empty-state"><p>No listings yet. Run a scrape first.</p></div>';
            return;
        }

        container.innerHTML = listings.map(l => `
            <div class="listing-card">
                <div class="listing-source">${l.source}</div>
                <div class="listing-title">
                    ${l.url ? `<a href="${l.url}" target="_blank" rel="noopener">${escapeHtml(l.title)}</a>` : escapeHtml(l.title)}
                </div>
                <div class="listing-meta">
                    ${l.price ? `<span>$${l.price.toFixed(2)}</span>` : ''}
                    ${l.favorites ? `<span>${l.favorites} favs</span>` : ''}
                    ${l.reviews ? `<span>${l.reviews} reviews</span>` : ''}
                    ${l.rating ? `<span>${l.rating} stars</span>` : ''}
                </div>
                <div class="listing-tags">
                    ${(JSON.parse(l.tags || '[]')).slice(0, 5).map(t =>
                        `<span class="listing-tag">${escapeHtml(t)}</span>`
                    ).join('')}
                </div>
            </div>
        `).join('');

        listingsLoaded = true;
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>Error loading listings: ${err.message}</p></div>`;
    }
}

function filterListings(source) {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    loadListings(source);
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/* Auto-refresh insights from API data */
async function refreshInsights() {
    try {
        const [fabrics, patterns, colors] = await Promise.all([
            fetch('/api/trends?category=fabric_type&limit=5').then(r => r.json()),
            fetch('/api/trends?category=pattern&limit=5').then(r => r.json()),
            fetch('/api/trends?category=color&limit=5').then(r => r.json()),
        ]);

        const container = document.getElementById('insights-container');
        if (!container) return;

        const allTrends = [...fabrics, ...patterns, ...colors];
        if (!allTrends.length) return;

        // Build insight cards from top trends
        const insights = [];

        const topOverall = allTrends.sort((a, b) => b.score - a.score)[0];
        if (topOverall) {
            insights.push({
                type: 'hot',
                title: `Hottest: ${capitalize(topOverall.term)}`,
                detail: `Score: ${topOverall.score} | ${topOverall.mention_count} listings`,
                action: `Strong demand for "${topOverall.term}" across marketplaces`,
            });
        }

        if (fabrics[0]) {
            insights.push({
                type: 'rising',
                title: `Top Fabric: ${capitalize(fabrics[0].term)}`,
                detail: `${fabrics[0].mention_count} listings | Score: ${fabrics[0].score}`,
                action: `"${capitalize(fabrics[0].term)}" is the most popular fabric type right now`,
            });
        }

        if (patterns[0]) {
            insights.push({
                type: 'opportunity',
                title: `Top Pattern: ${capitalize(patterns[0].term)}`,
                detail: `${patterns[0].mention_count} listings | Score: ${patterns[0].score}`,
                action: `"${capitalize(patterns[0].term)}" prints are in high demand`,
            });
        }

        if (colors[0]) {
            insights.push({
                type: 'price',
                title: `Trending Color: ${capitalize(colors[0].term)}`,
                detail: `${colors[0].mention_count} listings | Score: ${colors[0].score}`,
                action: `"${capitalize(colors[0].term)}" is the hottest color trend`,
            });
        }

        const iconMap = { hot: '&#128293;', rising: '&#128200;', opportunity: '&#128161;', price: '&#127912;' };

        container.innerHTML = insights.map(i => `
            <div class="insight-card ${i.type}">
                <div class="insight-icon">${iconMap[i.type]}</div>
                <div class="insight-title">${i.title}</div>
                <div class="insight-detail">${i.detail}</div>
                <div class="insight-action">${i.action}</div>
            </div>
        `).join('');
    } catch (err) {
        // Silently fail - insights are a nice-to-have
    }
}

// Refresh insights on page load
document.addEventListener('DOMContentLoaded', refreshInsights);

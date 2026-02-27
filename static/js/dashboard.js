/* Fabric Trend Spotter - Dashboard JS v4 */

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
    statusText.textContent = 'Loading baseline data, scraping EU shops & competitors, checking live sources & Google Trends, running forecasts... This may take a few minutes.';

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
            if (r.eu_shop_listings > 0) parts.push(`${r.eu_shop_listings} EU shops`);
            if (r.competitor_listings > 0) parts.push(`${r.competitor_listings} competitor`);
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
   ETSY / WHOLESALE TABS
   ========================================== */

function switchEU(key) {
    // Scope tab switching to the parent section so Etsy and Wholesale tabs are independent
    const targetContent = document.getElementById(`eu-${key}`);
    if (!targetContent) return;
    const section = targetContent.closest('section');
    if (section) {
        section.querySelectorAll('.eu-tab').forEach(t => t.classList.remove('active'));
        section.querySelectorAll('.eu-content').forEach(c => c.classList.remove('active'));
    }
    document.querySelector(`[data-eu="${key}"]`)?.classList.add('active');
    targetContent.classList.add('active');
}

/* ==========================================
   CHANNEL TOGGLE (B2B / B2C / BOTH)
   ========================================== */

function switchChannel(channel) {
    // Update toggle buttons
    document.querySelectorAll('.channel-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.channel-btn[data-channel="${channel}"]`)?.classList.add('active');

    // Show/hide sections based on data-channel attribute
    document.querySelectorAll('section[data-channel]').forEach(sec => {
        const ch = sec.getAttribute('data-channel');
        if (channel === 'all') {
            sec.style.display = '';
        } else if (ch === 'both') {
            sec.style.display = '';
        } else if (ch === channel) {
            sec.style.display = '';
        } else {
            sec.style.display = 'none';
        }
    });

    // Show/hide nav links
    document.querySelectorAll('.nav-link[data-nav-channel]').forEach(link => {
        const ch = link.getAttribute('data-nav-channel');
        if (channel === 'all') {
            link.style.display = '';
        } else if (ch === 'both') {
            link.style.display = '';
        } else if (ch === channel) {
            link.style.display = '';
        } else {
            link.style.display = 'none';
        }
    });

    // Store preference
    try { localStorage.setItem('fts_channel', channel); } catch(e) {}
}

// Restore channel preference on page load
document.addEventListener('DOMContentLoaded', function() {
    try {
        const saved = localStorage.getItem('fts_channel');
        if (saved && ['all', 'b2b', 'b2c'].includes(saved)) {
            switchChannel(saved);
        }
    } catch(e) {}
});

function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

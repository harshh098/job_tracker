// ─── Toast Notifications ───
function showToast(message, type = 'info', duration = 3500) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'fadeOut 0.3s ease forwards';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ─── API Helper ───
async function api(url, options = {}) {
  const controller = new AbortController();
  const timeoutId  = setTimeout(() => controller.abort(), 30000);

  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      signal: controller.signal,
      ...options
    });

    clearTimeout(timeoutId);

    let data;
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      try {
        data = await res.json();
      } catch (parseErr) {
        throw new Error(`Server returned invalid JSON (HTTP ${res.status})`);
      }
    } else {
      const text = await res.text();
      throw new Error(
        res.status === 404
          ? `API route not found: ${url}. Check your Flask backend.`
          : `Unexpected response (HTTP ${res.status}): ${text.slice(0, 120)}`
      );
    }

    if (!res.ok) {
      throw new Error(data?.error || data?.message || `Request failed (HTTP ${res.status})`);
    }

    return data;

  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') throw new Error('Request timed out after 30 seconds. The server may be busy.');
    if (err instanceof TypeError && err.message.includes('fetch')) throw new Error('Cannot reach the server. Make sure your Flask app is running.');
    throw err;
  }
}

// ─── Format Date ───
function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// ─── Format Datetime ───
function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// ══════════════════════════════════════════════════════════════
// ─── APPLY BUTTON HELPER — REMOVED ───
//
// CHANGED: applyJob() has been removed from the global scope.
//
// The Dashboard "Apply" button has been removed entirely per product
// decision — only the Delete button remains on Dashboard rows.
//
// The scraper page (scraper.html / jobs.html) still renders its own
// inline <a href="..." target="_blank"> Apply link per job card, which
// does not depend on this helper.
//
// If you need to re-introduce Apply elsewhere, add applyJob() back:
//
//   function applyJob(link) {
//     if (!link) { showToast('No application link available.', 'info'); return; }
//     const trimmed = link.trim();
//     try {
//       const parsed = new URL(trimmed);
//       if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
//         showToast('Invalid application link.', 'error'); return;
//       }
//     } catch (_) {}
//     window.open(trimmed, '_blank', 'noopener,noreferrer');
//   }
// ══════════════════════════════════════════════════════════════


// ══════════════════════════════════════════════════════════════
// ─── THEME SYSTEM ───
// Saves preference to localStorage and applies as class on <html>.
// Supports: 'dark' | 'light' | 'system'
// 'system' follows prefers-color-scheme media query.
// Applied before-paint via inline <script> in base.html to avoid FOUC.
// ══════════════════════════════════════════════════════════════

function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.className = prefersDark ? 'dark' : 'light';
  } else {
    root.className = theme;
  }
}

/**
 * Set and persist the user's theme preference.
 * @param {'dark'|'light'|'system'} theme
 */
function setTheme(theme) {
  localStorage.setItem('theme', theme);
  applyTheme(theme);
}

// React to system preference changes when theme is 'system'
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  const stored = localStorage.getItem('theme') || 'system';
  if (stored === 'system') applyTheme('system');
});

// Apply on every page load (complements the inline script in <head>)
(function() {
  const t = localStorage.getItem('theme') || 'system';
  applyTheme(t);
})();

// ══════════════════════════════════════════════════════════════
// ─── CUSTOM DROPDOWN SYSTEM ───
// ══════════════════════════════════════════════════════════════

function buildCustomDropdown(selectEl) {
  if (selectEl.dataset.upgraded) return;
  selectEl.dataset.upgraded = 'true';
  selectEl.style.display = 'none';

  const wrapper = document.createElement('div');
  wrapper.className = 'custom-select';
  wrapper.style.minWidth = selectEl.offsetWidth ? selectEl.offsetWidth + 'px' : '140px';

  const selected = document.createElement('div');
  selected.className = 'select-selected';

  const getLabel = () => {
    const opt = selectEl.options[selectEl.selectedIndex];
    return opt ? opt.text : '';
  };
  selected.textContent = getLabel();

  const optionsList = document.createElement('div');
  optionsList.className = 'select-options hidden';

  optionsList._reposition = () => {
    const rect = selected.getBoundingClientRect();
    optionsList.style.top   = (rect.bottom + 4) + 'px';
    optionsList.style.left  = rect.left + 'px';
    optionsList.style.width = rect.width + 'px';
  };

  const rebuildOptions = () => {
    optionsList.innerHTML = '';
    Array.from(selectEl.options).forEach((opt, i) => {
      const item = document.createElement('div');
      item.textContent = opt.text;
      item.dataset.value = opt.value;
      if (selectEl.selectedIndex === i) item.classList.add('selected');

      item.addEventListener('click', (e) => {
        e.stopPropagation();
        selectEl.selectedIndex = i;
        selectEl.value = opt.value;
        selectEl.dispatchEvent(new Event('change', { bubbles: true }));
        selected.textContent = opt.text;
        optionsList.querySelectorAll('div').forEach(d => d.classList.remove('selected'));
        item.classList.add('selected');
        closeDropdown(wrapper, optionsList);
      });

      optionsList.appendChild(item);
    });
  };
  rebuildOptions();

  selected.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = !optionsList.classList.contains('hidden');
    closeAllDropdowns();
    if (!isOpen) openDropdown(wrapper, optionsList);
  });

  const observer = new MutationObserver(() => {
    selected.textContent = getLabel();
    rebuildOptions();
  });
  observer.observe(selectEl, { childList: true, attributes: true, subtree: true });

  selectEl.addEventListener('change', () => {
    selected.textContent = getLabel();
    optionsList.querySelectorAll('div').forEach((d, i) => {
      d.classList.toggle('selected', i === selectEl.selectedIndex);
    });
  });

  wrapper.appendChild(selected);
  document.body.appendChild(optionsList);

  selectEl.parentNode.insertBefore(wrapper, selectEl.nextSibling);
}

function openDropdown(wrapper, optionsList) {
  wrapper.classList.add('open');
  if (typeof optionsList._reposition === 'function') optionsList._reposition();
  optionsList.classList.remove('hidden');
}

function closeDropdown(wrapper, optionsList) {
  wrapper.classList.remove('open');
  optionsList.classList.add('hidden');
  optionsList.style.top   = '';
  optionsList.style.left  = '';
  optionsList.style.width = '';
}

function closeAllDropdowns() {
  document.querySelectorAll('.custom-select.open').forEach(w => w.classList.remove('open'));
  document.querySelectorAll('.select-options:not(.hidden)').forEach(list => {
    list.classList.add('hidden');
    list.style.top   = '';
    list.style.left  = '';
    list.style.width = '';
  });
}

function upgradeAllSelects() {
  document.querySelectorAll('select:not([data-upgraded])').forEach(buildCustomDropdown);
}

document.addEventListener('click', () => closeAllDropdowns());

function repositionOpenDropdowns() {
  document.querySelectorAll('.select-options:not(.hidden)').forEach(list => {
    if (typeof list._reposition === 'function') list._reposition();
  });
}
window.addEventListener('scroll', repositionOpenDropdowns, { passive: true });
window.addEventListener('resize', repositionOpenDropdowns, { passive: true });

document.addEventListener('DOMContentLoaded', () => {
  upgradeAllSelects();

  if (typeof window.renderTable === 'function') {
    const _orig = window.renderTable;
    window.renderTable = function (...args) {
      _orig.apply(this, args);
      setTimeout(upgradeAllSelects, 0);
    };
  }
});

// ══════════════════════════════════════════════════════════════
// ─── TOPBAR BUTTON HANDLERS ───
// ══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {

  // Profile menu positioning — anchor to avatar on open
  const avatarBtn = document.getElementById('avatar-btn');
  const profileMenu = document.getElementById('profile-menu');
  if (avatarBtn && profileMenu) {
    avatarBtn.addEventListener('click', () => {
      if (!profileMenu.classList.contains('hidden')) return;
      const rect = avatarBtn.getBoundingClientRect();
      profileMenu.style.top   = (rect.bottom + 6) + 'px';
      profileMenu.style.right = (window.innerWidth - rect.right) + 'px';
      profileMenu.style.left  = 'auto';
    });
  }

  // Refresh button
  document.querySelectorAll('[data-action="refresh"], .icon-btn[title="Refresh"]').forEach(btn => {
    btn.addEventListener('click', () => {
      showToast('Refreshing…', 'info', 1500);
      window.location.reload();
    });
  });

  // Settings button
  document.querySelectorAll('[data-action="settings"], .icon-btn[title="Settings"]').forEach(btn => {
    btn.addEventListener('click', () => {
      const settingsPath = '/settings/';
      if (window.location.pathname !== settingsPath) window.location.href = settingsPath;
      else showToast('Already on settings', 'info');
    });
  });

  // Notifications button
  document.querySelectorAll('[data-action="notifications"], .icon-btn[title="Notifications"]').forEach(btn => {
    btn.addEventListener('click', () => {
      showToast('No new notifications', 'info', 2000);
      btn.querySelector('.notif-dot')?.remove();
    });
  });

  // Sidebar Toggle (mobile)
  const toggle  = document.querySelector('.sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (toggle && sidebar) {
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      sidebar.classList.toggle('open');
    });
    document.addEventListener('click', (e) => {
      if (!sidebar.contains(e.target) && !toggle.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    });
  }

  // Highlight current nav item
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(item => {
    const href = item.getAttribute('href');
    if (href && (path === href || (href !== '/' && path.startsWith(href)))) {
      item.classList.add('active');
    }
  });
});
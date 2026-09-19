// Difficulty badge rendering
// Usage: <span class="badge" data-difficulty="green|blue|black|dblack" data-label="true"></span>
const BADGE_CONFIG = {
  green:  { color: '#22C55E', label: 'Green Circle',  shape: (s) => `<circle cx="${s/2}" cy="${s/2}" r="${s/2 - 0.5}" fill="#22C55E"/>` },
  blue:   { color: '#3B82F6', label: 'Blue Square',   shape: (s) => `<rect x="0.5" y="0.5" width="${s-1}" height="${s-1}" fill="#3B82F6"/>` },
  black:  { color: '#E5E7EB', label: 'Black Diamond', shape: (s) => `<polygon points="${s/2},0.5 ${s-0.5},${s/2} ${s/2},${s-0.5} 0.5,${s/2}" fill="#E5E7EB"/>` },
  dblack: { color: '#EF4444', label: 'Double Black',  shape: (s) => `<polygon points="${s/2*0.6},0.5 ${s*0.85},${s/2} ${s/2*0.6},${s-0.5} 0.5,${s/2}" fill="#EF4444"/><polygon points="${s*0.55},0.5 ${s-0.5},${s/2} ${s*0.55},${s-0.5} ${s*0.25},${s/2}" fill="#EF4444"/>` },
}

function renderBadges() {
  document.querySelectorAll('.badge[data-difficulty]').forEach(el => {
    const d = el.dataset.difficulty
    const cfg = BADGE_CONFIG[d]
    if (!cfg) return
    const size = parseInt(el.dataset.size || '16', 10)
    const showLabel = el.dataset.label === 'true'
    const w = d === 'dblack' ? size * 1.8 : size
    const svg = `<svg class="badge__shape" width="${w}" height="${size}" viewBox="0 0 ${w} ${size}" fill="none" aria-hidden="true">${cfg.shape(size)}</svg>`
    const label = showLabel ? `<span class="badge__label">${cfg.label}</span>` : ''
    el.classList.add(`badge--${d}`)
    el.innerHTML = svg + label
  })
}

// Mobile nav toggle: shows/hides .site-nav__links on narrow screens
function initNavToggle() {
  const toggle = document.querySelector('.site-nav__toggle')
  const links = document.querySelector('.site-nav__links')
  if (!toggle || !links) return

  toggle.addEventListener('click', () => {
    const open = links.classList.toggle('is-open')
    toggle.setAttribute('aria-expanded', open)
  })

  // close the menu if a link is tapped, or if the viewport is resized past the breakpoint
  links.addEventListener('click', (e) => {
    if (e.target.tagName === 'A') {
      links.classList.remove('is-open')
      toggle.setAttribute('aria-expanded', 'false')
    }
  })
  window.addEventListener('resize', () => {
    if (window.innerWidth > 900) {
      links.classList.remove('is-open')
      toggle.setAttribute('aria-expanded', 'false')
    }
  })
}

// Universal nav search
// Searches every page in the compendium except the hub index.html files
// (the index is built by build_search_index.py and loaded as
// window.SITE_SEARCH_INDEX via assets/js/search-index.js).
function initSiteSearch() {
  const root = document.getElementById('site-search')
  if (!root) return

  const index = Array.isArray(window.SITE_SEARCH_INDEX) ? window.SITE_SEARCH_INDEX : []
  const input = root.querySelector('.site-search__input')
  const clearBtn = root.querySelector('.site-search__clear')
  const resultsBox = root.querySelector('.site-search__results')

  // Every nav link on the page is written relative to that page's depth
  // (e.g. "../../../index.html"). Reuse the logo's href to work out the
  // path back to the site root, then prefix every index entry's
  // root-relative url with it — this way the search works correctly no
  // matter how deep the current page is.
  const logoHref = document.querySelector('.site-nav__logo')?.getAttribute('href') || 'index.html'
  const rootPrefix = logoHref.replace(/index\.html$/, '')

  let activeIndex = -1
  let currentResults = []

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]))
  }

  function escapeRegExp(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  }

  function scoreEntry(entry, q) {
    const title = entry.title.toLowerCase()
    if (title === q) return 100
    if (title.startsWith(q)) return 90
    const titleIdx = title.indexOf(q)
    if (titleIdx !== -1) return 80 - titleIdx
    const bc = (entry.breadcrumb || '').toLowerCase()
    if (bc.includes(q)) return 40
    const desc = (entry.description || '').toLowerCase()
    if (desc.includes(q)) return 20
    return -1
  }

  function highlight(title, q) {
    const safe = escapeHtml(title)
    if (!q) return safe
    const re = new RegExp('(' + escapeRegExp(escapeHtml(q)) + ')', 'ig')
    return safe.replace(re, '<mark>$1</mark>')
  }

  function closeResults() {
    root.classList.remove('is-open')
    activeIndex = -1
    resultsBox.innerHTML = ''
  }

  function setActive(i) {
    const rows = resultsBox.querySelectorAll('.site-search__result')
    rows.forEach((row) => row.classList.remove('is-active'))
    if (i >= 0 && i < rows.length) {
      rows[i].classList.add('is-active')
      rows[i].scrollIntoView({ block: 'nearest' })
    }
    activeIndex = i
  }

  function renderResults(q) {
    const query = q.trim().toLowerCase()
    if (!query) {
      closeResults()
      return
    }

    const ranked = index
      .map((entry) => ({ entry, score: scoreEntry(entry, query) }))
      .filter((r) => r.score > -1)
      .sort((a, b) => b.score - a.score || a.entry.title.localeCompare(b.entry.title))

    currentResults = ranked.map((r) => r.entry)
    activeIndex = -1
    root.classList.add('is-open')

    if (currentResults.length === 0) {
      resultsBox.innerHTML = '<div class="site-search__empty">No matches in the compendium</div>'
      return
    }

    const shown = currentResults.slice(0, 8)
    const countLabel = currentResults.length > shown.length
      ? `${shown.length} of ${currentResults.length} results`
      : `${shown.length} result${shown.length === 1 ? '' : 's'}`

    const rows = shown.map((entry) => {
      const badge = entry.difficulty
        ? `<span class="badge site-search__result-badge" data-difficulty="${entry.difficulty}" data-size="14"></span>`
        : '<span class="site-search__result-badge"></span>'
      const path = escapeHtml(entry.breadcrumb || entry.realm || '')
      return `
        <div class="site-search__result" role="option" data-url="${escapeHtml(rootPrefix + entry.url)}">
          ${badge}
          <div class="site-search__result-body">
            <div class="site-search__result-name">${highlight(entry.title, query)}</div>
            <div class="site-search__result-path">${path}</div>
          </div>
        </div>`
    }).join('')

    resultsBox.innerHTML = `<div class="site-search__count">${countLabel}</div>${rows}`
    renderBadges()

    resultsBox.querySelectorAll('.site-search__result').forEach((row, i) => {
      row.addEventListener('mouseenter', () => setActive(i))
      row.addEventListener('click', () => navigateTo(row.dataset.url))
    })
  }

  function navigateTo(url) {
    if (url) window.location.href = url
  }

  input.addEventListener('input', () => {
    root.classList.toggle('has-value', input.value.length > 0)
    renderResults(input.value)
  })

  input.addEventListener('focus', () => {
    if (input.value.trim()) renderResults(input.value)
  })

  input.addEventListener('keydown', (e) => {
    const rows = resultsBox.querySelectorAll('.site-search__result')
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (rows.length) setActive((activeIndex + 1) % rows.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (rows.length) setActive((activeIndex - 1 + rows.length) % rows.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const target = currentResults[activeIndex >= 0 ? activeIndex : 0]
      if (target) navigateTo(rootPrefix + target.url)
    } else if (e.key === 'Escape') {
      closeResults()
      input.blur()
    }
  })

  clearBtn.addEventListener('click', () => {
    input.value = ''
    root.classList.remove('has-value')
    closeResults()
    input.focus()
  })

  document.addEventListener('click', (e) => {
    if (!root.contains(e.target)) closeResults()
  })

  // "/" focuses search from anywhere on the page, like most doc sites
  document.addEventListener('keydown', (e) => {
    if (e.key !== '/' || e.target === input) return
    const tag = document.activeElement && document.activeElement.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA') return
    e.preventDefault()
    input.focus()
  })
}

// Step accordion: open first step by default
document.addEventListener('DOMContentLoaded', () => {
  renderBadges()
  initNavToggle()
  initSiteSearch()

  const steps = document.querySelectorAll('.step')
  if (steps.length > 0) {
    steps[0].open = true
  }

  // Close other steps when one opens (optional single-open behavior)
  steps.forEach(step => {
    step.addEventListener('toggle', () => {
      if (step.open) {
        steps.forEach(other => {
          if (other !== step) other.open = false
        })
      }
    })
  })
})
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

// Step accordion: open first step by default
document.addEventListener('DOMContentLoaded', () => {
  renderBadges()
  initNavToggle()

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
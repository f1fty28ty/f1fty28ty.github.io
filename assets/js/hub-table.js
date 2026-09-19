// hub-table.js -- written by build_table.py (re-running the script regenerates it).
// Hub tables: single-select category chips ("All" or one category), click-to-sort
// column headers, click-anywhere-in-row navigation, and a notice on phone-width screens.
(function () {
  var DIFF_RANK = { green: 1, blue: 2, black: 3, dblack: 4 }
  var collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

  function isBlank(v) { return v === '' || v === '\u2014' }

  function initHubFilterTables() {
    document.querySelectorAll('[data-hub-table]').forEach(setupTable)
  }

  function setupTable(table) {
    if (table.hasAttribute('data-hub-ready')) return
    table.setAttribute('data-hub-ready', '')

    var filterId = table.getAttribute('data-hub-table')
    var filterBar = document.querySelector('[data-hub-filter="' + filterId + '"]')
    var wrap = table.closest('.hub-table-wrap') || table
    var tbody = table.tBodies[0]
    var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr[data-category]'))
    var emptyRow = tbody.querySelector('.hub-table__empty-row')

    rows.forEach(function (row, i) { row.setAttribute('data-order', String(i)) })

    // ── click anywhere in a row (the link itself already navigates on its own) ──
    rows.forEach(function (row) {
      var link = row.querySelector('a')
      if (!link) return
      row.addEventListener('click', function (e) {
        if (e.target.closest('a')) return
        window.location.href = link.getAttribute('href')
      })
    })

    // ── phone notice ──
    var note = document.createElement('p')
    note.className = 'hub-table__mobile-note'
    note.setAttribute('role', 'note')
    note.textContent = 'Phone view is limited: only names and difficulty show here. Use an iPad or desktop to see every column.'
    var anchor = filterBar || wrap
    anchor.parentNode.insertBefore(note, anchor)

    // ── filter: exactly one chip is on. Picking another swaps; picking the active one returns to All ──
    var current = null // null = All
    function applyFilter() {
      var visible = 0
      rows.forEach(function (row) {
        var show = current === null || row.getAttribute('data-category') === current
        row.style.display = show ? '' : 'none'
        if (show) visible += 1
      })
      if (emptyRow) emptyRow.style.display = visible === 0 ? '' : 'none'
    }

    if (filterBar) {
      var chips = Array.prototype.slice.call(filterBar.querySelectorAll('.hub-filter__chip'))
      var setCategory = function (cat) {
        current = cat
        chips.forEach(function (chip) {
          var on = cat === null
            ? chip.hasAttribute('data-filter-all')
            : chip.getAttribute('data-category') === cat
          chip.classList.toggle('is-active', on)
          chip.setAttribute('aria-pressed', String(on))
        })
        applyFilter()
      }
      chips.forEach(function (chip) {
        chip.addEventListener('click', function () {
          if (chip.hasAttribute('data-filter-all')) return setCategory(null)
          var cat = chip.getAttribute('data-category')
          setCategory(current === cat ? null : cat)
        })
      })
      setCategory(null)
    }

    // ── sort: click a header to sort ascending, again for descending, again to restore the original order ──
    var sort = { col: -1, dir: 0 }
    var headers = Array.prototype.slice.call(table.tHead.rows[0].cells)

    function cellKey(row, col) {
      var cell = row.cells[col]
      var badge = cell.querySelector('[data-difficulty]')
      if (badge) return DIFF_RANK[badge.getAttribute('data-difficulty')] || 99
      return cell.textContent.trim()
    }

    function applySort() {
      var items = rows.map(function (row) {
        return { row: row, order: Number(row.getAttribute('data-order')), key: sort.dir ? cellKey(row, sort.col) : null }
      })
      items.sort(function (a, b) {
        if (sort.dir) {
          var blankA = isBlank(a.key)
          var blankB = isBlank(b.key)
          if (blankA !== blankB) return blankA ? 1 : -1 // blanks always last
          if (!blankA) {
            var c = typeof a.key === 'number' ? a.key - b.key : collator.compare(a.key, b.key)
            if (c !== 0) return c * sort.dir
          }
        }
        return a.order - b.order // ties (and "no sort") keep the original order
      })
      items.forEach(function (item) { tbody.insertBefore(item.row, emptyRow) })
    }

    headers.forEach(function (th, col) {
      var btn = document.createElement('button')
      btn.type = 'button'
      btn.className = 'hub-table__sort'
      while (th.firstChild) btn.appendChild(th.firstChild)
      th.appendChild(btn)
      th.setAttribute('aria-sort', 'none')
      btn.addEventListener('click', function () {
        if (sort.col !== col) sort = { col: col, dir: 1 }
        else if (sort.dir === 1) sort = { col: col, dir: -1 }
        else sort = { col: -1, dir: 0 }
        headers.forEach(function (h, i) {
          h.setAttribute('aria-sort', i === sort.col ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none')
        })
        applySort()
      })
    })
  }

  // If an older cached main.js still defines initHubFilterTables (it calls it on
  // DOMContentLoaded), swap in this version so the old one doesn't also run.
  if (typeof window.initHubFilterTables === 'function') {
    window.initHubFilterTables = initHubFilterTables
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHubFilterTables)
  } else {
    initHubFilterTables()
  }
})()

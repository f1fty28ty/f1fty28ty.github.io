// hub-table.js -- written by build_table.py (re-running the script regenerates it).
// Category filter chips + click-anywhere-in-row navigation for the hub tables.
(function () {
  function initHubFilterTables() {
    document.querySelectorAll('[data-hub-table]').forEach(function (table) {
      var filterId = table.getAttribute('data-hub-table')
      var filterBar = document.querySelector('[data-hub-filter="' + filterId + '"]')
      var rows = Array.prototype.slice.call(table.querySelectorAll('tbody tr[data-category]'))
      var emptyRow = table.querySelector('.hub-table__empty-row')

      // Click anywhere in a row (the link itself already navigates on its own).
      rows.forEach(function (row) {
        var link = row.querySelector('a')
        if (!link) return
        row.addEventListener('click', function (e) {
          if (e.target.closest('a')) return
          window.location.href = link.getAttribute('href')
        })
      })

      if (!filterBar) return // single-category hubs have no chips

      var chips = Array.prototype.slice.call(filterBar.querySelectorAll('.hub-filter__chip'))
      var resetBtn = filterBar.querySelector('.hub-filter__reset')

      function applyFilter() {
        var active = {}
        chips.forEach(function (c) {
          var on = c.classList.contains('is-active')
          c.setAttribute('aria-pressed', String(on)) // keep screen readers in step
          if (on) active[c.getAttribute('data-category')] = true
        })
        var visible = 0
        rows.forEach(function (row) {
          var show = !!active[row.getAttribute('data-category')]
          row.style.display = show ? '' : 'none'
          if (show) visible += 1
        })
        if (emptyRow) emptyRow.style.display = visible === 0 ? '' : 'none'
      }

      chips.forEach(function (chip) {
        chip.addEventListener('click', function () {
          chip.classList.toggle('is-active')
          applyFilter()
        })
      })

      if (resetBtn) {
        resetBtn.addEventListener('click', function () {
          chips.forEach(function (c) { c.classList.add('is-active') })
          applyFilter()
        })
      }

      applyFilter()
    })
  }

  // If main.js already defines initHubFilterTables (it calls it on DOMContentLoaded),
  // swap in this version so the chips aren't wired up twice. Otherwise run it ourselves.
  if (typeof window.initHubFilterTables === 'function') {
    window.initHubFilterTables = initHubFilterTables
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHubFilterTables)
  } else {
    initHubFilterTables()
  }
})()

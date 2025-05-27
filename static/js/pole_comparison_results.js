document.addEventListener('DOMContentLoaded', () => {
  const initTable = (id) => {
    if (!document.querySelector(id)) return null;
    const table = $(id).DataTable({
      paging: false,
      info: false,
      searching: true,
      ordering: true,
      autoWidth: false,
      scrollX: true,
    });
    return table;
  };

  // Initialize tables in each tab if they exist
  const tables = {
    all: initTable('#tblAll'),
    issues: initTable('#tblIssues'),
  };

  // Global search input (if present)
  const searchInput = document.getElementById('globalSearch');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const val = e.target.value;
      // Apply to active tab only
      const activeTab = document.querySelector('.tab-pane.active');
      if (activeTab && activeTab.id === 'issues' && tables.issues) {
        tables.issues.search(val).draw();
      } else if (tables.all) {
        tables.all.search(val).draw();
      }
    });
  }

  // Update counts on tab labels if tables exist
  const setTabCount = (id, count) => {
    const tabBtn = document.querySelector(`button[data-bs-target="#${id}"]`);
    if (tabBtn) tabBtn.innerHTML = tabBtn.textContent.replace(/\([0-9]+\)/, '') + ` (${count})`;
  };
  if (tables.all) setTabCount('all', tables.all.data().length);
  if (tables.issues) setTabCount('issues', tables.issues.data().length);
}); 
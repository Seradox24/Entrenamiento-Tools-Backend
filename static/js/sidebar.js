(function () {
  var shell = document.getElementById("app-shell");
  var sidebar = document.getElementById("app-sidebar");
  var backdrop = document.getElementById("sidebar-backdrop");
  var toggle = document.getElementById("sidebar-toggle");

  if (!shell || !sidebar) {
    return;
  }

  function setDesktopState(state) {
    shell.dataset.sidebarState = state;
    localStorage.setItem("sidebar-state", state);

    if (toggle) {
      var expanded = state === "expanded";
      toggle.setAttribute("aria-expanded", String(expanded));
      toggle.setAttribute("aria-label", expanded ? "Contraer menu" : "Expandir menu");
    }
  }

  function openMobileSidebar() {
    sidebar.classList.remove("-translate-x-full");
    if (backdrop) {
      backdrop.classList.remove("hidden");
    }
  }

  function closeMobileSidebar() {
    sidebar.classList.add("-translate-x-full");
    if (backdrop) {
      backdrop.classList.add("hidden");
    }
  }

  setDesktopState(localStorage.getItem("sidebar-state") || "expanded");

  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = shell.dataset.sidebarState === "collapsed" ? "expanded" : "collapsed";
      setDesktopState(next);
    });
  }

  document.querySelectorAll("[data-sidebar-open]").forEach(function (button) {
    button.addEventListener("click", openMobileSidebar);
  });

  document.querySelectorAll("[data-sidebar-close]").forEach(function (button) {
    button.addEventListener("click", closeMobileSidebar);
  });
})();

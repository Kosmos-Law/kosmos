(function () {
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("sidebar-toggle");
  const overlay = document.getElementById("sidebar-overlay");

  const STORAGE_KEY = "sidebar-collapsed";
  const envClass = document.body.classList.contains("env-dev") ? "env-dev" : "";

  function openMobile() {
    sidebar.classList.add("mobile-open");
    overlay.classList.add("visible");
  }

  function closeMobile() {
    sidebar.classList.remove("mobile-open");
    overlay.classList.remove("visible");
  }

  // After a boosted swap only #main-content is replaced, so the sidebar
  // keeps its old highlight. The response is the full page, and the
  // server already chose the active item there (the view's `app`), so
  // copy that choice rather than guessing from the URL. A partial
  // response with no sidebar leaves the highlight alone.
  function updateSidebarActive(html) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const fresh = doc.getElementById("sidebar");
    if (!fresh) return;
    const freshLink = fresh.querySelector(".sidebar-nav li.active > a[id]");
    sidebar.querySelectorAll(".sidebar-nav li").forEach(function (li) {
      li.classList.remove("active");
    });
    const link = freshLink && sidebar.querySelector("#" + freshLink.id);
    if (link) link.closest("li").classList.add("active");
  }

  // Point the toggle's icon at the action it will perform: an open
  // sidebar shows the "close" glyph, a collapsed one the "open" glyph. The markup ships the close cut; this
  // corrects it on load when the stored state is collapsed.
  function syncToggleIcon() {
    const icon = toggle.querySelector("i");
    if (icon)
      icon.className =
        "icon-panel-left-" +
        (document.documentElement.classList.contains("sidebar-collapsed")
          ? "open"
          : "close");
  }

  // Desktop collapse toggle
  toggle.addEventListener("click", function () {
    const collapsed =
      document.documentElement.classList.toggle("sidebar-collapsed");

    localStorage.setItem(STORAGE_KEY, collapsed);
    syncToggleIcon();
  });

  syncToggleIcon();

  document.addEventListener("click", function (e) {
    if (e.target.closest("#sidebar-mobile-trigger")) openMobile();
  });
  overlay.addEventListener("click", closeMobile);

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && sidebar.classList.contains("mobile-open")) {
      closeMobile();
    }
  });

  // Close mobile sidebar on any nav link click
  sidebar.addEventListener("click", function (e) {
    if (e.target.closest("a") && window.innerWidth <= 768) closeMobile();
  });

  // A nav click on the page already showing reloads it (people click the
  // active item to get a fresh list) but does not stack a second history
  // entry for the same URL. This used to cancel the request outright,
  // which read as a dead click; Tasks, served at "/", took the blame most
  // often, since that is where the day is spent.
  sidebar.addEventListener("htmx:beforeRequest", function (e) {
    var link = e.detail.elt.closest("a");
    if (link && link.getAttribute("href") === window.location.pathname) {
      link.setAttribute("hx-push-url", "false");
    }
  });
  sidebar.addEventListener("htmx:afterRequest", function (e) {
    var link = e.detail.elt.closest("a");
    if (link) link.removeAttribute("hx-push-url");
  });

  // Sync body class and sidebar active state after HTMX content swap
  document.body.addEventListener("htmx:afterSwap", function (e) {
    if (e.detail.target && e.detail.target.id === "main-content") {
      updateSidebarActive(e.detail.xhr.response);

      const match = e.detail.xhr.response.match(/<body[^>]*class="([^"]*)"/);
      const newClasses = match ? match[1] : "";
      const preserved = envClass ? envClass + " " : "";

      document.body.className = (preserved + newClasses).trim();
    }
  });
})();

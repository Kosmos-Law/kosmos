// Daily dash check - ensures users view the agenda dash at least once per day
// Handles browser tabs left open overnight by checking on visibility change
(function() {
  const DASH_URL = '/dash/';
  const STORAGE_KEY = 'dailyDashCheckDate';

  // The date on the user's own calendar. (toISOString() gives the UTC date,
  // which rolls over in the afternoon or evening west of Greenwich and sent
  // people back to the dash a second time the same day.)
  function getTodayString() {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${now.getFullYear()}-${month}-${day}`;
  }

  // Leaving the page now would throw work away: a dialog is open, or the
  // cursor is in a field. The check runs again the next time the tab is
  // shown, and the server makes the same check on the next page load.
  function isMidEdit() {
    if (document.body.classList.contains('modal-open')) return true;
    const el = document.activeElement;
    if (!el) return false;
    return el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);
  }

  function checkDailyDash() {
    const lastCheckDate = localStorage.getItem(STORAGE_KEY);
    const today = getTodayString();

    // If we're already on the dash page, update the check date
    if (window.location.pathname === DASH_URL) {
      localStorage.setItem(STORAGE_KEY, today);
      return;
    }

    // If we haven't checked in today, redirect to dash
    if (lastCheckDate !== today && !isMidEdit()) {
      window.location.href = DASH_URL;
    }
  }

  // Check when the page becomes visible (handles tab switching and waking from sleep)
  document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible') {
      checkDailyDash();
    }
  });

  // Also check on initial page load
  document.addEventListener('DOMContentLoaded', function() {
    // Small delay to let the page settle and avoid race with server redirect
    setTimeout(checkDailyDash, 100);
  });
})();

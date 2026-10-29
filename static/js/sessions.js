// The session page: keep the history rail in step with the transcript,
// follow the live turn without fighting the reader, and tell the AI tab
// in another browser tab when this session changed.
(function () {
  const channel = new BroadcastChannel("ai-sessions");
  let stickToBottom = true;

  function scrollToMessage(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    el.classList.add("ai-message-highlight");
    setTimeout(() => el.classList.remove("ai-message-highlight"), 2000);
  }
  window.scrollToMessage = scrollToMessage;

  function updatePromptList() {
    const list = document.getElementById("promptList");
    if (!list) return;
    list.innerHTML = "";
    document.querySelectorAll(".ai-message-user").forEach((msg) => {
      const text = msg.querySelector(".ai-message-text").innerText;
      const link = document.createElement("a");
      link.href = "#" + msg.id;
      link.className = "ai-sidebar-item";
      link.dataset.tooltip = text.substring(0, 300) + (text.length > 300 ? "..." : "");
      link.onclick = (e) => { e.preventDefault(); scrollToMessage(msg.id); };
      const initials = document.createElement("span");
      initials.className = "ai-sidebar-item-initials";
      initials.textContent = msg.dataset.initials || "?";
      const span = document.createElement("span");
      span.className = "ai-sidebar-item-text";
      span.textContent = text.substring(0, 60) + (text.length > 60 ? "..." : "");
      link.append(initials, span);
      list.appendChild(link);
    });
    if (!list.children.length) {
      list.innerHTML = '<div class="ai-sidebar-empty">No prompts yet</div>';
    }
  }

  function scroller() {
    return document.querySelector(".ai-chat-scroll");
  }

  function scrollToBottom() {
    const container = scroller();
    if (container) container.scrollTop = container.scrollHeight;
  }

  // The live block replaces the transcript every second. A step the
  // reader opened stays open across the swap, and the view follows the
  // bottom only while the reader is already there.
  let openSteps = new Set();

  function rememberOpenSteps() {
    openSteps = new Set(
      Array.from(document.querySelectorAll("#messageContainer details[open][id]")).map((d) => d.id)
    );
  }

  function restoreOpenSteps() {
    openSteps.forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.open = true;
    });
  }

  function stopTurn() {
    const stop = document.querySelector(".session-stop");
    if (stop) { stop.click(); return true; }
    return false;
  }

  document.addEventListener("DOMContentLoaded", () => {
    updatePromptList();
    scrollToBottom();
    const container = scroller();
    if (container) {
      container.addEventListener("scroll", () => {
        stickToBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
      });
    }
    const form = document.getElementById("chatForm");
    const input = document.getElementById("aiMessageInput");
    form.addEventListener("htmx:afterRequest", (event) => {
      if (event.detail.successful) {
        input.value = "";
        stickToBottom = true;
        channel.postMessage({ type: "sessionsChanged", matterId: window.aiSessionMatterId });
      }
    });
    document.body.addEventListener("htmx:beforeSwap", (e) => {
      if (e.detail.target && e.detail.target.id === "messageContainer") rememberOpenSteps();
    });
    document.body.addEventListener("htmx:afterSwap", (e) => {
      if (e.target.id === "messageContainer") {
        restoreOpenSteps();
        updatePromptList();
        if (stickToBottom) scrollToBottom();
        if (!document.querySelector(".session-live")) {
          channel.postMessage({ type: "sessionsChanged", matterId: window.aiSessionMatterId });
        }
      }
      if (e.target.id === "sessionTitle") {
        document.title = e.target.innerText.trim().substring(0, 40) + " - AI";
        channel.postMessage({ type: "sessionsChanged", matterId: window.aiSessionMatterId });
      }
    });
    // Esc stops the turn in progress; pressed twice within half a second
    // it empties the message box.
    let lastEscape = 0;
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      const now = Date.now();
      if (now - lastEscape < 500) {
        input.value = "";
        lastEscape = 0;
      } else {
        stopTurn();
        lastEscape = now;
      }
    });
    document.getElementById("promptList").addEventListener("mouseover", (e) => {
      const item = e.target.closest(".ai-sidebar-item");
      if (item && item.dataset.tooltip) {
        const rect = item.getBoundingClientRect();
        item.style.setProperty("--tooltip-top", rect.top + rect.height / 2 + "px");
      }
    });
  });
})();

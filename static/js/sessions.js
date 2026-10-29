// The session page: keep the history rail in step with the transcript, and
// tell the AI tab in another browser tab when this session changed.
(function () {
  const channel = new BroadcastChannel("ai-sessions");

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

  function scrollToBottom() {
    const container = document.querySelector(".ai-chat-scroll");
    if (container) container.scrollTop = container.scrollHeight;
  }

  document.addEventListener("DOMContentLoaded", () => {
    updatePromptList();
    scrollToBottom();
    const form = document.getElementById("chatForm");
    form.addEventListener("htmx:afterRequest", (event) => {
      if (event.detail.successful) {
        document.getElementById("aiMessageInput").value = "";
        channel.postMessage({ type: "sessionsChanged", matterId: window.aiSessionMatterId });
      }
    });
    document.body.addEventListener("htmx:afterSwap", (e) => {
      if (e.target.id === "messageContainer") {
        updatePromptList();
        scrollToBottom();
      }
      if (e.target.id === "sessionTitle") {
        document.title = e.target.innerText.trim().substring(0, 40) + " - AI";
        channel.postMessage({ type: "sessionsChanged", matterId: window.aiSessionMatterId });
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

const icons = {
  chat: `<svg viewBox="0 0 24 24"><path d="M5 18.5 3 21v-5.5A8 8 0 1 1 6.5 19H5Z"/><path d="M8 10h8M8 14h5"/></svg>`,
  box: `<svg viewBox="0 0 24 24"><path d="m4 7 8-4 8 4-8 4-8-4Z"/><path d="M4 7v10l8 4 8-4V7M12 11v10"/></svg>`,
  truck: `<svg viewBox="0 0 24 24"><path d="M3 5h11v12H3zM14 9h4l3 3v5h-7z"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/></svg>`,
  card: `<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M7 15h4"/></svg>`,
  user: `<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>`,
  return: `<svg viewBox="0 0 24 24"><path d="M9 7 4 12l5 5"/><path d="M4 12h10a6 6 0 0 1 6 6"/></svg>`,
  tag: `<svg viewBox="0 0 24 24"><path d="M20 13 13 20 4 11V4h7l9 9Z"/><circle cx="8" cy="8" r="1"/></svg>`,
  send: `<svg viewBox="0 0 24 24"><path d="m4 4 17 8-17 8 3-8-3-8Z"/><path d="M7 12h14"/></svg>`,
  moon: `<svg viewBox="0 0 24 24"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2Z"/></svg>`,
  sun: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2"/></svg>`,
  menu: `<svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg>`,
  close: `<svg viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18"/></svg>`,
  doc: `<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h5"/></svg>`
};

const categories = [
  { label: "Sipariş", icon: icons.box, color: "blue", query: "Siparişimi nasıl takip edebilirim?" },
  { label: "İade", icon: icons.return, color: "lavender", query: "İade talebi nasıl oluşturulur?" },
  { label: "Kargo", icon: icons.truck, color: "green", query: "Kargom gecikti, ne yapmalıyım?" },
  { label: "Ödeme", icon: icons.card, color: "beige", query: "Kartımdan para çekildi ama sipariş oluşmadı" },
  { label: "Hesap", icon: icons.user, color: "blue", query: "Şifremi nasıl sıfırlarım?" },
  { label: "Kampanya", icon: icons.tag, color: "lavender", query: "Kupon kodum neden geçersiz?" }
];

const state = {
  dark: localStorage.getItem("theme") === "dark",
  sidebarOpen: false,
  loading: false,
  messages: [],
  llmContext: ""
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message) {
  const toast = document.querySelector(".toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 2500);
}

function renderMessages() {
  if (!state.messages.length) {
    return `<div class="empty-chat">
      <span class="brand-mark">${icons.chat}</span>
      <h2>Bilgi tabanına sorun</h2>
      <p>Sipariş, iade, ödeme, kargo, hesap ve kampanya konularında kaynaklı yanıt alın.</p>
    </div>`;
  }
  return state.messages.map(message => {
    if (message.role === "user") {
      return `<div class="message user-message">
        <div class="message-text">${escapeHtml(message.text)}</div>
        <span class="message-avatar user-avatar">S</span>
      </div>`;
    }
    const sources = message.sources?.length
      ? `<div class="inline-sources">
          ${message.sources.map(source => `<div class="source">
            <span>${icons.doc}</span>
            <div><strong>${escapeHtml(source.title)}</strong>
            <small>${escapeHtml(source.matched_sections.join(", "))} · ${(source.best_score * 100).toFixed(1)}%</small></div>
          </div>`).join("")}
        </div>`
      : "";
    return `<div class="message ai-message">
      <span class="message-avatar ai-avatar">AI</span>
      <div class="message-text">
        <p>${escapeHtml(message.text).replaceAll("\n", "<br>")}</p>
        <div class="answer-meta">
          <span class="confidence confidence-${message.confidence?.toLowerCase()}">${message.confidence || "LOW"}</span>
        </div>
        ${sources}
      </div>
    </div>`;
  }).join("");
}

function render() {
  document.querySelector("#app").innerHTML = `<div class="app-shell ${state.dark ? "dark" : ""}">
    <aside class="sidebar ${state.sidebarOpen ? "open" : ""}">
      <div class="sidebar-head">
        <div class="brand"><span class="brand-mark">${icons.chat}</span><span>DestekAI</span></div>
        <button class="icon-button sidebar-close" aria-label="Menüyü kapat">${icons.close}</button>
      </div>
      <button class="new-chat">${icons.chat}<span>Yeni görüşme</span></button>
      <p class="nav-label">ÖRNEK KONULAR</p>
      ${categories.map(item => `<button class="nav-item quick-query" data-query="${escapeHtml(item.query)}">
        <span class="nav-category ${item.color}">${item.icon}</span><span>${item.label}</span>
      </button>`).join("")}
      <div class="sidebar-help">
        <strong>RAG MVP</strong>
        <span>Yanıtlar 70 dokümanlık bilgi tabanından getirilir ve kullanılan kaynaklarla gösterilir.</span>
      </div>
    </aside>
    <div class="overlay ${state.sidebarOpen ? "show" : ""}"></div>
    <main class="main-content">
      <header class="topbar">
        <button class="icon-button menu-button" aria-label="Menüyü aç">${icons.menu}</button>
        <div class="page-heading"><h1>Müşteri destek asistanı</h1><p>Kaynaklara dayalı e-ticaret desteği</p></div>
        <div class="top-actions">
          <button class="theme-toggle">${state.dark ? icons.sun : icons.moon}<span>${state.dark ? "Açık mod" : "Koyu mod"}</span></button>
        </div>
      </header>
      <div class="chat-layout rag-chat-layout">
        <section class="card conversation">
          <div class="conversation-head">
            <div><span class="online"></span><strong>RAG asistanı</strong></div>
            <small>${state.loading ? "Bilgi tabanı taranıyor..." : "Hazır"}</small>
          </div>
          <div class="messages">${renderMessages()}</div>
          <form class="message-form">
            <textarea rows="1" maxlength="1000" aria-label="Mesajınız" placeholder="Örn. Kartımdan para çekildi ama sipariş oluşmadı" ${state.loading ? "disabled" : ""}></textarea>
            <button type="submit" aria-label="Gönder" ${state.loading ? "disabled" : ""}>${icons.send}</button>
          </form>
        </section>
        <aside class="right-panel">
          <section class="card context-preview-card">
            <div class="section-head">
              <h3>LLM Context Preview</h3>
              <span>En fazla 3 doküman</span>
            </div>
            <pre class="context-preview">${escapeHtml(state.llmContext || "Bir soru gönderildiğinde gruplanmış retrieval context burada gösterilir.")}</pre>
          </section>
          <section class="card sources-card">
            <div class="section-head"><h3>Nasıl çalışır?</h3></div>
            <ol class="how-it-works">
              <li>Soru güvenlik kontrolünden geçer.</li>
              <li>pgvector en ilgili chunkları bulur.</li>
              <li>En fazla 3 doküman LLM context olarak hazırlanır.</li>
            </ol>
          </section>
        </aside>
      </div>
    </main>
  </div>`;
  bindEvents();
  requestAnimationFrame(() => {
    const messages = document.querySelector(".messages");
    if (messages) messages.scrollTop = messages.scrollHeight;
  });
}

async function ask(question) {
  const query = question.trim();
  if (!query || state.loading) return;
  state.messages.push({ role: "user", text: query });
  state.loading = true;
  render();
  try {
    const response = await fetch("/api/rag/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit: 30 })
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "İstek tamamlanamadı.");
    state.llmContext = payload.llm_context;
    state.messages.push({
      role: "assistant",
      text: payload.grouped_results.length
        ? `${payload.grouped_results.length} ilgili doküman bulundu. Birleştirilmiş içerik LLM Context Preview alanında hazırlandı; LLM çağrısı yapılmadı.`
        : "Yeterli eşleşme bulunamadı.",
      sources: payload.grouped_results,
      confidence: payload.grouped_results[0]?.best_score >= 0.78
        ? "HIGH"
        : payload.grouped_results[0]?.best_score >= 0.62
          ? "MEDIUM"
          : "LOW"
    });
  } catch (error) {
    state.messages.push({
      role: "assistant",
      text: error.message || "Backend bağlantısı kurulamadı.",
      sources: [],
      confidence: "LOW"
    });
  } finally {
    state.loading = false;
    render();
  }
}

function bindEvents() {
  document.querySelector(".message-form")?.addEventListener("submit", event => {
    event.preventDefault();
    const textarea = event.currentTarget.querySelector("textarea");
    ask(textarea.value);
  });
  document.querySelectorAll(".quick-query").forEach(button => {
    button.addEventListener("click", () => {
      state.sidebarOpen = false;
      ask(button.dataset.query);
    });
  });
  document.querySelector(".new-chat")?.addEventListener("click", () => {
    state.messages = [];
    state.llmContext = "";
    state.sidebarOpen = false;
    render();
  });
  document.querySelector(".theme-toggle")?.addEventListener("click", () => {
    state.dark = !state.dark;
    localStorage.setItem("theme", state.dark ? "dark" : "light");
    render();
  });
  document.querySelector(".menu-button")?.addEventListener("click", () => {
    state.sidebarOpen = true;
    render();
  });
  document.querySelector(".sidebar-close")?.addEventListener("click", () => {
    state.sidebarOpen = false;
    render();
  });
  document.querySelector(".overlay")?.addEventListener("click", () => {
    state.sidebarOpen = false;
    render();
  });
  const textarea = document.querySelector(".message-form textarea");
  textarea?.addEventListener("input", () => {
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
  });
}

render();

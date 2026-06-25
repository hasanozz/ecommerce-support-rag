const API = "/api";
const FAQ = [
  "Kartımdan para çekildi ama siparişim oluşmadı.",
  "Siparişimi nasıl iptal edebilirim?",
  "İade talebi nasıl oluşturulur?"
];

const state = {
  user: null,
  page: "shop",
  conversationId: null,
  conversations: [],
  tickets: [],
  adminTickets: [],
  products: [],
  favorites: [],
  returns: [],
  adminReturns: [],
  adminWallets: [],
  adminCards: [],
  adminSecurityProfiles: [],
  cart: null,
  demoOrders: [],
  adminDemoOrders: [],
  adminCoupons: [],
  adminProducts: [],
  adminReviews: [],
  messages: [],
  loading: true,
  error: "",
  theme: localStorage.getItem("destekai-theme") || "light",
  contextPreview: "",
  contextOpen: false,
  copilotOpen: false,
  ticketModal: null,
  sourceModal: null,
  productDetail: null,
  productDetailDraft: { rating: "", title: "", body: "" },
  productQuery: "",
  productCategory: "",
  editingTicketId: null,
  editingDemoOrderId: null
};

const icons = {
  chat: `<svg viewBox="0 0 24 24"><path d="M5 18.5 3 21v-5.5A8 8 0 1 1 6.5 19H5Z"/><path d="M8 10h8M8 14h5"/></svg>`,
  clock: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>`,
  ticket: `<svg viewBox="0 0 24 24"><path d="M4 6h16v4a2 2 0 0 0 0 4v4H4v-4a2 2 0 0 0 0-4V6Z"/></svg>`,
  send: `<svg viewBox="0 0 24 24"><path d="m4 4 17 8-17 8 3-8-3-8Z"/><path d="M7 12h14"/></svg>`,
  up: `<svg viewBox="0 0 24 24"><path d="M7 10v10H3V10h4Zm0 9h10.5a2 2 0 0 0 1.9-1.4l1.4-5A2 2 0 0 0 19 10h-4l1-4c.3-1.4-.7-2.7-2.1-2.7L7 10v9Z"/></svg>`,
  down: `<svg viewBox="0 0 24 24"><path d="M7 14V4H3v10h4Zm0-9h10.5a2 2 0 0 1 1.9 1.4l1.4 5A2 2 0 0 1 19 14h-4l1 4c.3 1.4-.7 2.7-2.1 2.7L7 14V5Z"/></svg>`,
  logout: `<svg viewBox="0 0 24 24"><path d="M10 5H5v14h5M14 8l4 4-4 4M8 12h10"/></svg>`,
  edit: `<svg viewBox="0 0 24 24"><path d="m4 20 4.5-1 10-10-3.5-3.5-10 10L4 20Z"/><path d="m13.5 6.5 3.5 3.5"/></svg>`,
  close: `<svg viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18"/></svg>`,
  trash: `<svg viewBox="0 0 24 24"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 14h10l1-14M9 7V4h6v3"/></svg>`,
  cart: `<svg viewBox="0 0 24 24"><path d="M5 6h16l-2 8H7L5 3H2"/><circle cx="8" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/></svg>`,
  box: `<svg viewBox="0 0 24 24"><path d="m3 7 9-4 9 4-9 4-9-4Z"/><path d="M3 7v10l9 4 9-4V7M12 11v10"/></svg>`
  ,
  heart: `<svg viewBox="0 0 24 24"><path d="M12 21s-7-4.4-9.2-8.6C.9 8.9 3.2 5 7 5c2.1 0 3.7 1.1 5 2.7C13.3 6.1 14.9 5 17 5c3.8 0 6.1 3.9 4.2 7.4C19 16.6 12 21 12 21Z"/></svg>`,
  star: `<svg viewBox="0 0 24 24"><path d="m12 3 2.9 6 6.6.9-4.8 4.7 1.2 6.5L12 18.9 6.1 21l1.2-6.5L2.5 9.9 9.1 9 12 3Z"/></svg>`,
  search: `<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>`,
  shield: `<svg viewBox="0 0 24 24"><path d="M12 3 20 6v6c0 5-3.4 8.7-8 11-4.6-2.3-8-6-8-11V6l8-3Z"/></svg>`
};

function esc(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function renderMarkdown(text) {
  const lines = String(text ?? "").replaceAll("\r\n", "\n").split("\n");
  const blocks = [];
  let listType = null;
  let listItems = [];

  const flushList = () => {
    if (!listItems.length) return;
    const tag = listType === "ol" ? "ol" : "ul";
    blocks.push(`<${tag}>${listItems.map(item => `<li>${item}</li>`).join("")}</${tag}>`);
    listType = null;
    listItems = [];
  };

  for (const rawLine of lines) {
    const escaped = esc(rawLine)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`(.+?)`/g, "<code>$1</code>")
      .replace(/\*\*/g, "");
    const trimmed = rawLine.trim();
    const bulletMatch = /^[-*]\s+(.+)$/.exec(trimmed);
    const orderedMatch = /^\d+\.\s+(.+)$/.exec(trimmed);
    if (bulletMatch || orderedMatch) {
      const nextType = bulletMatch ? "ul" : "ol";
      const itemHtml = esc((bulletMatch || orderedMatch)[1])
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/`(.+?)`/g, "<code>$1</code>")
        .replace(/\*\*/g, "");
      if (listType && listType !== nextType) flushList();
      listType = nextType;
      listItems.push(itemHtml);
      continue;
    }
    flushList();
    if (!trimmed) {
      blocks.push("");
      continue;
    }
    blocks.push(`<p>${escaped}</p>`);
  }
  flushList();
  return blocks.filter(Boolean).join("");
}

function feedbackStatusLabel(value) {
  return value === "HELPFUL"
    ? "Bu mesaja olumlu geri dönüş verdiniz."
    : value === "UNHELPFUL"
      ? "Bu mesaja olumsuz geri dönüş verdiniz."
      : "";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "İşlem tamamlanamadı.");
  return body;
}

function toast(message) {
  const node = document.querySelector(".toast");
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 2600);
}

function loginPage() {
  return `<main class="login-page ${state.theme === "dark" ? "dark-page" : ""}">
    <section class="card login-card">
      <span class="brand-mark">${icons.chat}</span><h1>DestekAI</h1>
      <p>Sorularınızı, geçmiş görüşmelerinizi ve destek taleplerinizi güvenli şekilde yönetin.</p>
      ${state.error ? `<div class="error-box">${esc(state.error)}</div>` : ""}
      <a class="google-login" href="/auth/google/login">Google ile giriş yap</a>
    </section>
  </main>`;
}

function sidebar() {
  return `<aside class="sidebar store-header">
    <div class="sidebar-head"><div class="brand"><span class="brand-mark">${icons.box}</span><span>TeknoCampus Store</span></div></div>
    <button class="new-chat" data-action="new-chat">${icons.chat}<span>Copilot'u aç</span></button>
    <nav>
      <button class="nav-item ${state.page === "shop" ? "active" : ""}" data-page="shop">${icons.box}<span>Mağaza</span></button>
      <button class="nav-item ${state.page === "orders" ? "active" : ""}" data-page="orders">${icons.clock}<span>Siparişlerim</span></button>
      <button class="nav-item ${state.page === "returns" ? "active" : ""}" data-page="returns">${icons.box}<span>İadelerim</span></button>
      <button class="nav-item ${state.page === "favorites" ? "active" : ""}" data-page="favorites">${icons.heart}<span>Favorilerim</span></button>
      <button class="nav-item ${state.page === "tickets" ? "active" : ""}" data-page="tickets">${icons.ticket}<span>Ticketlarım</span></button>
      ${state.user?.is_admin ? `<button class="nav-item ${state.page === "admin-demo" ? "active" : ""}" data-page="admin-demo">${icons.edit}<span>Admin panel</span></button>` : ""}
      ${state.user?.is_admin ? `<button class="nav-item ${state.page === "admin" ? "active" : ""}" data-page="admin">${icons.ticket}<span>Admin ticket</span></button>` : ""}
    </nav>
    <div class="sidebar-help"><strong>${esc(state.user?.display_name || state.user?.email)}</strong>
      <span>${esc(state.user?.email)}</span><button data-action="logout">${icons.logout} Çıkış yap</button>
    </div>
  </aside>`;
}

function topbar(title, description = "") {
  return `<header class="topbar"><div class="page-heading"><h1>${esc(title)}</h1><p>${esc(description)}</p></div>
    <button class="theme-toggle" data-action="theme" aria-label="Temayı değiştir">
      ${state.theme === "dark" ? "Açık tema" : "Koyu tema"}
    </button></header>`;
}

function sourceList(sources = [], messageId = "") {
  if (!sources.length) return "";
  const hasRealMatch = sources.some(source => (source.best_score || 0) > 0);
  const title = hasRealMatch
    ? `${sources.length} kaynak kullanıldı`
    : `${sources.length} bağlam kaynağı kullanıldı`;
  return `<details class="source-details"><summary>${title}</summary>
    <div class="inline-sources">${sources.map((source, index) => {
      const score = Number(source.best_score || 0);
      const scoreLabel = score > 0 ? `Eşleşme: %${(score * 100).toFixed(1)}` : "Bağlam kaynağı";
      return `<button class="source" data-source-message="${messageId}" data-source-index="${index}"><div>
      <strong>${esc(source.title)}</strong>
      <small>${scoreLabel}</small>
    </div></button>`;
    }).join("")}</div></details>`;
}

function similarList(items = []) {
  if (!items.length) return "";
  return `<div class="similar-solutions"><strong>Benzer sorunlar ve çözümler</strong>${items.map(item => `
    <article class="similar-solution"><b>${esc(item.canonical_question)}</b>
      <p>${esc(item.safe_answer)}</p>
      <small>%${(item.similarity_score * 100).toFixed(1)} benzerlik · ${item.view_count} gösterim ·
      ${item.helpful_count} olumlu · %${(item.success_rate * 100).toFixed(0)} başarı</small>
      <div><button data-similar="${item.id}" data-value="HELPFUL">${icons.up} İşime yaradı</button>
      <button data-similar="${item.id}" data-value="UNHELPFUL">${icons.down} Yaramadı</button></div>
    </article>`).join("")}</div>`;
}

function faqHtml() {
  return `<section class="faq-panel"><div><strong>Sık sorulan sorular</strong></div>
    <div class="faq-grid">${FAQ.map((question, index) =>
      `<button data-faq="${index}" ${state.loading ? "disabled" : ""}>${esc(question)}</button>`
    ).join("")}</div></section>`;
}

function messagesHtml() {
  if (!state.messages.length) return `<div class="empty-chat"><span class="brand-mark">${icons.chat}</span>
    <h2>Size nasıl yardımcı olabiliriz?</h2>
    <p>Sipariş, iade, ödeme, kargo, hesap veya kampanya sorununuzu yazabilirsiniz.</p></div>`;
  return state.messages.map(item => item.role === "USER"
    ? `<div class="message user-message"><div class="message-text">${esc(item.content)}</div></div>`
    : `<div class="message ai-message"><span class="message-avatar ai-avatar">AI</span><div class="message-text">
        <div class="answer-body">${renderMarkdown(item.content)}</div>${sourceList(item.sources, item.id)}
        ${item.id ? (item.user_feedback ? `<div class="feedback-state ${item.user_feedback === "HELPFUL" ? "positive" : "negative"}">
            ${feedbackStatusLabel(item.user_feedback)}
          </div>` : `<div class="answer-actions">
            <div class="feedback-group"><button class="feedback" data-message="${item.id}" data-value="HELPFUL">${icons.up} İşime yaradı</button>
            <button class="feedback negative" data-message="${item.id}" data-value="UNHELPFUL">${icons.down} İşime yaramadı</button></div>
            <button class="open-ticket-button" data-open-ticket="${item.id}">${icons.ticket} Ticket aç</button>
          </div>`) : ""}${similarList(item.similar_solutions)}
      </div></div>`).join("");
}

function chatPage() {
  return `${topbar("Müşteri destek asistanı", "Güvenli, kaynaklı ve geçmişe kaydedilen destek görüşmesi")}
    <section class="chat-grid"><section class="card conversation">
      <div class="conversation-head"><div><span class="online"></span><strong>RAG asistanı</strong></div>
      <div class="conversation-tools"><button data-action="context">${state.contextOpen ? "Context'i kapat" : "LLM Context Preview"}</button>
      <small>${state.loading ? "İşleniyor..." : "Hazır"}</small></div></div>
      <div class="messages">${messagesHtml()}</div>${faqHtml()}
      <form class="message-form"><textarea maxlength="1000" placeholder="Sorununuzu en fazla 1000 karakterle yazın. Enter gönderir, Shift+Enter yeni satır açar..." ${state.loading ? "disabled" : ""}></textarea>
      <button ${state.loading ? "disabled" : ""}>${icons.send}</button></form>
    </section>
    ${state.contextOpen ? `<aside class="card context-preview-card"><div class="section-head"><h3>LLM Context Preview</h3></div>
      <p class="debug-note">Bu alan Gemini çağrısından bağımsız `/api/rag/search` çıktısıdır.</p>
      <pre class="context-preview">${esc(state.contextPreview || "Bir soru gönderildiğinde retrieval context burada gösterilir.")}</pre></aside>` : ""}
    </section>`;
}

function historyPage() {
  return `${topbar("Geçmiş görüşmeler")}
    <section class="record-grid">${state.conversations.length ? state.conversations.map(item => `
      <button class="record-card history-card" data-conversation="${item.id}">
        <strong>${esc(item.title)}</strong>
        <span class="status-chip">${esc(conversationStatusLabel(item.status))}</span>
        <small>Son güncelleme</small>
        <time>${new Date(item.updated_at).toLocaleString("tr-TR")}</time>
      </button>`).join("")
      : "<p>Henüz görüşme yok.</p>"}</section>`;
}

function conversationStatusLabel(status) {
  return ({
    ACTIVE: "Görüşme açık",
    ESCALATED: "Manuel desteğe aktarıldı",
    CLOSED: "Görüşme kapatıldı",
    RESOLVED: "Çözüldü"
  })[status] || "Durum güncelleniyor";
}

function statusLabel(status) {
  return ({ OPEN: "Gönderildi", IN_REVIEW: "İnceleniyor", RESOLVED: "Çözüldü" })[status] || status;
}

function demoStatusLabel(status) {
  return ({
    PREPARING: "Hazırlanıyor",
    SHIPPED: "Kargoya verildi",
    IN_TRANSIT: "Yolda",
    DELAYED: "Gecikti",
    LOST: "Kayboldu",
    DELIVERED: "Teslim edildi",
    PARTIALLY_DELIVERED: "Parçalı teslimat",
    SUCCESS: "Ödeme başarılı",
    FAILED: "Ödeme başarısız",
    CAPTURED_NO_ORDER: "Ödeme alındı, sipariş oluşmadı",
    REFUND_PENDING: "İade bekliyor",
    CREATED: "Oluşturuldu",
    PROCESSING: "İşleniyor",
    CANCELLED: "İptal edildi",
    VALID: "Geçerli",
    EXPIRED: "Süresi dolmuş",
    MIN_CART_NOT_MET: "Minimum tutar yetersiz",
    CATEGORY_MISMATCH: "Kategori uygun değil",
    DISABLED: "Pasif"
  })[status] || status;
}

function money(value) {
  return `${Number(value || 0).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} TL`;
}

function productBadge(category) {
  return ({
    electronics: "Elektronik",
    white_goods: "Beyaz eşya",
    shoes: "Ayakkabı",
    bags: "Çanta",
    coffee_equipment: "Kahve ekipmanı",
    clothing: "Giyim",
    sports: "Spor",
    market: "Market",
    home_kitchen: "Ev & Mutfak"
  })[category] || category;
}

function productInitial(name) {
  return esc((name || "Ü").trim().slice(0, 1).toLocaleUpperCase("tr-TR"));
}

function productRatingLabel(item) {
  if (!item) return "Puan yok";
  if (item.rating_average == null) return "Puan yok";
  return `${Number(item.rating_average).toFixed(1)} / 5 · ${item.review_count || 0} yorum`;
}

const ATTRIBUTE_LABELS = {
  guc_watt: "Motor gücü",
  hazne_litre: "Hazne kapasitesi",
  hiz_kademesi: "Hız kademesi",
  pil_suresi_saat: "Pil süresi",
  laptop_bolmesi: "Laptop bölmesi",
  suya_dayanikli: "Suya dayanıklı",
  makinede_yikanabilir: "Makinede yıkanabilir",
  mikrofon: "Mikrofon",
  gramaj: "Gramaj",
  tip: "Tip",
  malzeme: "Malzeme"
};

function attributeLabel(key) {
  return ATTRIBUTE_LABELS[key] || String(key || "").replaceAll("_", " ");
}

function attributeValue(key, value) {
  if (typeof value === "boolean") return value ? "Var" : "Yok";
  const text = String(value ?? "");
  const normalized = text.toLocaleLowerCase("tr-TR");
  if (normalized === "dokme") return "Dökme";
  if (normalized === "poset") return "Poşet";
  if (key === "guc_watt" && !normalized.includes("w")) return `${text} W`;
  if (key === "hazne_litre" && !normalized.includes("l")) return `${text} L`;
  if (key === "pil_suresi_saat" && !normalized.includes("saat")) return `${text} saat`;
  return text;
}

function productMatches(item, query, category) {
  const normalized = String(query || "").trim().toLocaleLowerCase("tr-TR");
  const targetCategory = String(category || "").trim();
  if (targetCategory && item.category !== targetCategory) return false;
  if (!normalized) return true;
  const haystack = [
    item.name,
    item.brand,
    item.category,
    item.subcategory,
    item.description,
    ...(item.tags || []),
    ...(item.image_urls || []),
    ...(item.attributes ? Object.entries(item.attributes).flatMap(([key, value]) => [key, value]) : [])
  ].join(" ").toLocaleLowerCase("tr-TR");
  return normalized.split(/\s+/).every(term => haystack.includes(term));
}

function filteredProducts() {
  return state.products.filter(item => productMatches(item, state.productQuery, state.productCategory));
}

function orderProducts(item) {
  return item.items.map(orderItem => esc(orderItem.product_name)).join(", ") || "Ürün bilgisi yok";
}

function canRequestReturn(order) {
  if (!order || order.return_request) return false;
  if (order.order_status === "CANCELLED" || order.payment_status === "FAILED") return false;
  return true;
}

function scenarioCards() {
  const orders = state.demoOrders || [];
  const returns = state.returns || [];
  const shipped = orders.find(item => ["SHIPPED", "IN_TRANSIT", "DELAYED"].includes(item.shipping_status));
  const delivered = orders.find(item => item.shipping_status === "DELIVERED");
  const returnItem = returns[0];
  return `<section class="scenario-center">
    <article class="scenario-card">
      <span>İptal / kargo</span>
      <strong>${esc(shipped?.order_no || "Kargoya verilen sipariş")}</strong>
      <p>${shipped ? `${orderProducts(shipped)} · ${demoStatusLabel(shipped.shipping_status)}` : "Demo senaryo oluşturunca kargoya verilmiş sipariş burada görünür."}</p>
      <button data-chat-prompt="Kargoya verilen siparişimi iptal edebilir miyim?">${icons.chat} Copilot'a sor</button>
    </article>
    <article class="scenario-card">
      <span>İade süreci</span>
      <strong>${esc(returnItem?.return_code || "İade kodu")}</strong>
      <p>${returnItem ? `${esc(returnItem.order_no || returnItem.order_id)} · ${esc(returnItem.return_status)} · ${esc(returnItem.refund_status)}` : "İade kodu, refund ve takip bilgisi burada özetlenir."}</p>
      <button data-page="returns">${icons.box} İadelerime git</button>
    </article>
    <article class="scenario-card">
      <span>Teslimat sorunu</span>
      <strong>${esc(delivered?.order_no || "Teslim edildi görünüyor")}</strong>
      <p>${delivered ? `${orderProducts(delivered)} · ${demoStatusLabel(delivered.shipping_status)}` : "Teslim edildi ama ulaşmadı senaryosunu Copilot'a anlatabilirsin."}</p>
      <button data-chat-prompt="Kargom teslim edildi görünüyor ama bana ulaşmadı.">${icons.chat} Copilot'a sor</button>
    </article>
    <article class="scenario-card">
      <span>Ödeme</span>
      <strong>Karttan çekim</strong>
      <p>Sipariş oluşmayan ödeme, başarısız ödeme ve refund senaryoları destek akışında kullanılır.</p>
      <button data-chat-prompt="Kartımdan para çekildi ama siparişim oluşmadı.">${icons.chat} Copilot'a sor</button>
    </article>
  </section>`;
}

function ticketsPage(admin = false) {
  const items = admin ? state.adminTickets : state.tickets;
  return `${topbar(admin ? "Admin ticket yönetimi" : "Destek taleplerim")}
    <section class="record-grid">${items.length ? items.map(item => `<article class="record-card ticket-card">
      <div class="ticket-card-header"><div><span class="ticket-number">Ticket #${item.id}</span>
      <strong>${esc(item.department)}</strong></div>
      ${admin ? `<button class="edit-ticket" data-edit-ticket="${item.id}" aria-label="Ticket düzenle">${icons.edit}</button>` : ""}</div>
      <div class="ticket-meta"><span class="status-chip status-${item.status.toLowerCase()}">${esc(statusLabel(item.status))}</span>
      <time>${new Date(item.updated_at).toLocaleString("tr-TR")}</time></div>
      <div class="ticket-note user-ticket-note"><small>Kullanıcı açıklaması</small>
      <p>${esc(item.user_note || "Kullanıcı açıklama eklememiş.")}</p></div>
      ${item.admin_note ? `<div class="ticket-note admin-note"><small>Admin yanıtı</small><p>${esc(item.admin_note)}</p></div>` : ""}
      ${admin && state.editingTicketId === item.id ? `<div class="admin-ticket-actions"><select data-ticket-status="${item.id}">
        ${["OPEN", "IN_REVIEW", "RESOLVED"].map(status => `<option value="${status}" ${status === item.status ? "selected" : ""}>${statusLabel(status)}</option>`).join("")}
      </select><textarea data-ticket-note="${item.id}" maxlength="1000" placeholder="Admin kararını veya kullanıcıya iletilecek notu yazın"></textarea>
      <div><button data-cancel-ticket-edit="${item.id}">Vazgeç</button><button class="primary-button" data-update-ticket="${item.id}">Güncelle</button></div></div>` : ""}
    </article>`).join("") : "<p>Ticket bulunmuyor.</p>"}</section>`;
}

function ratingSelectHtml(name = "rating", value = 0) {
  return `<select name="${esc(name)}">
    ${["", 0, 1, 2, 3, 4, 5].map(option => {
      const optionValue = option === "" ? "" : String(option);
      const selected = optionValue === String(value ?? "");
      return `<option value="${optionValue}" ${selected ? "selected" : ""}>${option === "" ? "Puan ver" : `${option}/5`}</option>`;
    }).join("")}
  </select>`;
}

function productAttributesHtml(attributes = {}) {
  const entries = Object.entries(attributes || {});
  if (!entries.length) return "<p>Teknik özellik bilgisi yok.</p>";
  return `<dl class="attribute-grid">${entries.map(([key, value]) => `
    <div><dt>${esc(attributeLabel(key))}</dt><dd>${Array.isArray(value) ? esc(value.map(item => attributeValue(key, item)).join(", ")) : esc(attributeValue(key, value))}</dd></div>
  `).join("")}</dl>`;
}

function productStars(value) {
  const score = Number(value || 0);
  const full = Math.round(score);
  return `<span class="stars">${"★".repeat(full)}${"☆".repeat(Math.max(0, 5 - full))}</span>`;
}

function productCard(item) {
  return `<article class="product-card" data-product-open="${item.id}">
    <div class="product-visual"><span>${productInitial(item.name)}</span></div>
    <div class="product-info">
      <span class="product-category">${esc(productBadge(item.category))}</span>
      <h3>${esc(item.name)}</h3>
      <p>${esc(item.brand || "")}</p>
      <small>${esc(productRatingLabel(item))}</small>
    </div>
    <div class="product-footer">
      <strong>${money(item.price)}</strong>
      <div class="product-actions">
        <button class="icon-button-small" data-product-open="${item.id}" aria-label="Ürün detay">${icons.search}</button>
        <button class="primary-button" data-add-product="${item.id}">${icons.cart} Sepete ekle</button>
      </div>
    </div>
  </article>`;
}

function productDetailModal() {
  const item = state.productDetail;
  if (!item) return "";
  const reviewCount = item.review_count || item.reviews?.length || 0;
  return `<div class="modal-layer">
    <div class="modal-backdrop" data-action="close-product-detail"></div>
    <section class="card modal product-modal">
      <button class="modal-close" data-action="close-product-detail" aria-label="Kapat">${icons.close}</button>
      <div class="product-modal-head">
        <div>
          <span class="product-category">${esc(productBadge(item.category))}</span>
          <h2>${esc(item.name)}</h2>
          <p>${esc(item.brand)} · ${esc(item.sku)}</p>
          <div class="rating-line">${productStars(item.rating_average)} <span>${esc(productRatingLabel(item))}</span></div>
        </div>
        <div class="price-box">
          <strong>${money(item.price)}</strong>
          <small>Stok: ${item.stock}</small>
        </div>
      </div>
      <div class="product-modal-body">
        <div class="product-gallery">
          <div class="product-visual large"><span>${productInitial(item.name)}</span></div>
          <p>${esc(item.description || "")}</p>
          <div class="modal-actions-row">
            <button class="primary-button" data-add-product="${item.id}">${icons.cart} Sepete ekle</button>
            <button data-product-favorite="${item.id}">${item.is_favorited ? icons.heart : icons.heart} ${item.is_favorited ? "Favoriden çıkar" : "Favoriye ekle"}</button>
            <button data-action="chat-product" data-product-id="${item.id}">${icons.chat} Copilot’a sor</button>
          </div>
        </div>
        <div class="product-meta-panel">
          <section>
            <h3>Teknik özellikler</h3>
            ${productAttributesHtml(item.attributes)}
          </section>
          <section>
            <h3>İade / garanti</h3>
            <p>${esc(item.return_policy_note || (item.returnable ? "İade edilebilir." : "İade edilemez."))}</p>
            <p>${item.warranty_months ? `${item.warranty_months} ay garanti` : "Garanti bilgisi yok."}</p>
          </section>
        </div>
      </div>
      <section class="review-section">
        <div class="section-head"><h3>Yorumlar</h3><span>${reviewCount} kayıt</span></div>
        <form class="review-form" data-review-form="${item.id}">
          <label>Puan${ratingSelectHtml("rating", state.productDetailDraft?.rating || "")}</label>
          <input name="title" maxlength="255" placeholder="Kısa başlık" value="${esc(state.productDetailDraft?.title || "")}">
          <textarea name="body" maxlength="2000" placeholder="Yorumunuz">${esc(state.productDetailDraft?.body || "")}</textarea>
          <button class="primary-button" type="submit">Yorumu gönder</button>
        </form>
        <div class="review-list">${(item.reviews || []).map(review => `
          <article class="review-card">
            <strong>${esc(review.user_display_name)}</strong>
            <small>${review.rating == null ? "Puan yok" : `${review.rating}/5`}</small>
            <p><b>${esc(review.title || "")}</b></p>
            <p>${esc(review.body || "")}</p>
          </article>
        `).join("") || "<p>Henüz yorum yok.</p>"}</div>
      </section>
    </section>
  </div>`;
}

function floatingCopilotButton() {
  return `<button class="floating-copilot" data-action="toggle-copilot">${icons.chat} Copilot</button>`;
}

function copilotDrawer() {
  if (!state.copilotOpen) return "";
  return `<aside class="copilot-drawer card">
    <div class="conversation-head">
      <div><span class="online"></span><strong>Copilot</strong></div>
      <button data-action="toggle-copilot">${icons.close}</button>
    </div>
    <div class="messages drawer-messages">${messagesHtml()}</div>
    ${faqHtml()}
    <form class="message-form drawer-form">
      <textarea maxlength="1000" placeholder="Sorunuzu yazın..." ${state.loading ? "disabled" : ""}></textarea>
      <button ${state.loading ? "disabled" : ""}>${icons.send}</button>
    </form>
  </aside>`;
}

function shopPage() {
  const cart = state.cart;
  const items = filteredProducts();
  const categories = [...new Set(state.products.map(item => item.category))];
  return `${topbar("Mağaza", "Ürün gez, sepete ekle, kupon dene, sipariş oluştur; destek gerektiğinde sağ alttaki Copilot'u kullan.")}
    <section class="commerce-layout">
      <div class="shop-area">
        <div class="commerce-hero card">
          <div>
            <span>Demo commerce</span>
            <h2>Alışveriş yap, sorun yaşa, Copilot ile çöz</h2>
            <p>Ürün kataloğu, sepet, sipariş, iade, ödeme ve kupon senaryoları aynı demo akışında çalışır.</p>
          </div>
          <button data-action="demo-reset">${icons.box} Demo senaryoyu yenile</button>
        </div>
        ${scenarioCards()}
        <div class="shop-toolbar card">
          <label class="search-field">${icons.search}<input value="${esc(state.productQuery)}" data-product-search placeholder="Ürün, marka, özellik veya tag ara"></label>
          <select data-product-category>
            <option value="">Tüm kategoriler</option>
            ${categories.map(category => `<option value="${esc(category)}" ${state.productCategory === category ? "selected" : ""}>${esc(productBadge(category))}</option>`).join("")}
          </select>
          <button data-action="clear-product-filters">${icons.close} Filtreleri temizle</button>
        </div>
        <section class="product-grid">
          ${items.map(item => productCard(item)).join("") || "<p>Ürün bulunamadı.</p>"}
        </section>
        <section class="mini-panels">
          <article class="card mini-panel">
            <div class="section-head"><h3>Siparişlerim</h3><span>${state.demoOrders.length} kayıt</span></div>
            <div class="mini-list">
              ${state.demoOrders.slice(0, 4).map(item => `<button class="mini-item" data-page="orders">
                <strong>${esc(item.order_no)}</strong><small>${orderProducts(item)} · ${esc(demoStatusLabel(item.shipping_status))}</small>
              </button>`).join("") || "<p>Henüz sipariş yok.</p>"}
            </div>
          </article>
          <article class="card mini-panel">
            <div class="section-head"><h3>Favorilerim</h3><span>${state.favorites.length} kayıt</span></div>
            <div class="mini-list">
              ${state.favorites.slice(0, 4).map(item => `<button class="mini-item" data-product-open="${item.product.id}">
                <strong>${esc(item.product.name)}</strong><small>${esc(productBadge(item.product.category))} · ${money(item.product.price)}</small>
              </button>`).join("") || "<p>Henüz favori yok.</p>"}
            </div>
          </article>
          <article class="card mini-panel">
            <div class="section-head"><h3>İadeler</h3><span>${state.returns.length} kayıt</span></div>
            <div class="mini-list">
              ${state.returns.slice(0, 3).map(item => `<article class="mini-item readonly">
                <strong>${esc(item.return_code || item.order_id)}</strong>
                <small>${esc(item.return_status)} · ${esc(item.refund_status)}</small>
              </article>`).join("") || "<p>İade kaydı yok.</p>"}
            </div>
          </article>
          <article class="card mini-panel">
            <div class="section-head"><h3>Hızlı destek</h3><span>Copilot</span></div>
            <div class="mini-list">
              ${["İade talebi nasıl oluşturulur?", "Siparişimi nasıl iptal edebilirim?", "Sepetimdeki ürüne kupon olur mu?"].map(question => `<button class="mini-item" data-chat-prompt="${esc(question)}">
                <strong>${esc(question)}</strong><small>Sağ alttaki Copilot ile cevapla</small>
              </button>`).join("")}
            </div>
          </article>
        </section>
      </div>
      <aside class="card cart-panel">
        <div class="section-head"><h3>Sepet</h3><span>${cart?.items?.length || 0} ürün</span></div>
        ${cart ? `<div class="cart-items">${cart.items.map(item => `<div class="cart-line">
          <div class="cart-line-main"><strong>${esc(item.product_name)}</strong><small>${esc(productBadge(item.category))} · ${money(item.line_total)}</small></div>
          <input aria-label="Adet" type="number" min="1" max="20" value="${item.quantity}" data-cart-qty="${item.id}">
          <button class="icon-danger" data-remove-cart="${item.id}" aria-label="Sepetten sil">${icons.trash}</button>
        </div>`).join("") || `<div class="empty-state">Sepet boş. Ürün ekleyerek demo sipariş oluşturabilirsiniz.</div>`}</div>
        <div class="coupon-row"><input data-coupon-code placeholder="Kupon kodu">
          <button data-action="apply-coupon">Uygula</button></div>
        <div class="coupon-hints"><span>DEMO10</span><span>MIN500</span><span>MODA20</span><span>ESKI50</span></div>
        ${cart.coupon_message ? `<p class="debug-note">${esc(cart.coupon_message)}</p>` : ""}
        <div class="cart-summary">
          <div><span>Ara toplam</span><strong>${money(cart.subtotal)}</strong></div>
          <div><span>İndirim</span><strong>${money(cart.discount_total)}</strong></div>
          <div class="cart-total"><span>Toplam</span><strong>${money(cart.total)}</strong></div>
        </div>
        <button class="primary-button checkout-button" data-action="checkout">Sipariş oluştur</button>` : "<p>Sepet yüklenmedi.</p>"}
      </aside>
    </section>`;
}

function favoritesPage() {
  return `${topbar("Favorilerim", "Favorilerinizdeki ürünleri inceleyin, kaldırın veya detayını açın.")}
    <section class="record-grid">
      ${state.favorites.length ? state.favorites.map(item => `
        <article class="record-card favorite-card" data-product-open="${item.product.id}">
          <div class="ticket-card-header">
            <div>
              <span class="ticket-number">${esc(item.product.sku)}</span>
              <strong>${esc(item.product.name)}</strong>
            </div>
            <button class="icon-danger" data-remove-favorite="${item.product.id}" aria-label="Favoriden çıkar">${icons.heart}</button>
          </div>
          <p>${esc(productBadge(item.product.category))} · ${money(item.product.price)} · ${esc(productRatingLabel(item.product))}</p>
          <small>${esc(item.product.description || "")}</small>
        </article>
      `).join("") : "<p>Henüz favori ürününüz yok.</p>"}
    </section>`;
}

function returnsPage() {
  return `${topbar("İadelerim", "İade kodu, refund durumu ve kargo süreçlerini buradan takip edin.")}
    <section class="record-grid">
      ${state.returns.length ? state.returns.map(item => `
        <article class="record-card return-card">
          <div class="ticket-card-header">
            <div>
              <span class="ticket-number">${esc(item.return_code || "İade")}</span>
              <strong>${esc(item.order_no || `Sipariş #${item.order_id}`)}</strong>
            </div>
            <span class="status-chip">${esc(item.return_status)}</span>
          </div>
          <div class="status-row">
            <span class="status-chip">${esc(item.return_status)}</span>
            <span class="status-chip">${esc(item.refund_status)}</span>
          </div>
          <p>${esc(item.return_reason || "")}</p>
          ${item.refund ? `<small>Refund: ${esc(item.refund.refund_reference)} · ${money(item.refund.refund_amount)}</small>` : ""}
        </article>
      `).join("") : "<p>İade kaydı bulunmuyor.</p>"}
    </section>`;
}

function demoOrdersPage(admin = false) {
  const items = admin ? state.adminDemoOrders : state.demoOrders;
  return `${topbar(admin ? "Demo sipariş yönetimi" : "Demo siparişlerim", admin ? "Kargo, ödeme ve sipariş durumlarını demo amaçlı güncelleyin." : "Chat asistanı bu sipariş durumlarını customer context olarak kullanır.")}
    ${admin ? `<section class="admin-overview">
      <article class="card metric-card"><span>Ürün</span><strong>${state.adminProducts.length}</strong><small>Katalog ve attribute verisi</small></article>
      <article class="card metric-card"><span>Yorum</span><strong>${state.adminReviews.length}</strong><small>Kullanıcı puanları ve görünür yorumlar</small></article>
      <article class="card metric-card"><span>Sipariş</span><strong>${state.adminDemoOrders.length}</strong><small>Durum yönetimi yapılabilir</small></article>
      <article class="card metric-card"><span>İade</span><strong>${state.adminReturns.length}</strong><small>Return/refund akışı</small></article>
    </section>
    <section class="coupon-section"><div class="section-head"><h3>Ürün kataloğu</h3><span>${state.adminProducts.length} ürün</span></div>
      <div class="coupon-grid">${state.adminProducts.slice(0, 12).map(product => `<article class="coupon-card">
        <div><strong>${esc(product.name)}</strong><span class="status-chip">${esc(productBadge(product.category))}</span></div>
        <p>${esc(product.brand || "-")} · ${money(product.price)} · Stok: ${product.stock}</p>
        <small>${esc(productRatingLabel(product))}</small>
      </article>`).join("") || "<p>Ürün kaydı yok.</p>"}</div></section>
    <section class="coupon-section"><div class="section-head"><h3>Ürün yorumları</h3><span>${state.adminReviews.length} yorum</span></div>
      <div class="coupon-grid">${state.adminReviews.slice(0, 8).map(review => `<article class="coupon-card">
        <div><strong>${esc(review.product_name || `Ürün #${review.product_id}`)}</strong><span class="status-chip">${review.rating == null ? "Puan yok" : `${review.rating}/5`}</span></div>
        <p>${esc(review.title || "")}</p>
        <small>${esc(review.body || "")}</small>
      </article>`).join("") || "<p>Yorum kaydı yok.</p>"}</div></section>` : ""}
    <section class="order-grid">${items.map(item => `<article class="order-card">
      <div class="order-card-head">
        <div><span class="ticket-number">${esc(item.order_no)}</span><h3>${orderProducts(item)}</h3></div>
        <div class="order-actions">
          ${admin ? `<button class="icon-button-small" data-edit-demo-order="${item.id}" aria-label="Sipariş düzenle">${icons.edit}</button>` : ""}
          <button class="icon-danger" data-delete-demo-order="${item.id}" data-admin="${admin ? "1" : "0"}" aria-label="Sipariş sil">${icons.trash}</button>
        </div>
      </div>
      <div class="status-row">
        <span class="status-chip">${esc(demoStatusLabel(item.order_status))}</span>
        <span class="status-chip">${esc(demoStatusLabel(item.payment_status))}</span>
        <span class="status-chip">${esc(demoStatusLabel(item.shipping_status))}</span>
      </div>
      <div class="order-details">
        <div><small>Toplam</small><strong>${money(item.total)}</strong></div>
        <div><small>Kupon</small><strong>${esc(item.coupon_code || "Yok")}</strong></div>
        <div><small>Tarih</small><strong>${new Date(item.updated_at).toLocaleDateString("tr-TR")}</strong></div>
      </div>
      ${item.shipment ? `<div class="shipment-box"><small>${esc(item.shipment.carrier)}</small>
        <p>${item.shipment.tracking_number ? `Takip numarası: ${esc(item.shipment.tracking_number)}` : "Takip numarası henüz yok."}</p>
        ${item.shipment.delay_reason || item.shipment.admin_note ? `<p>${esc(item.shipment.delay_reason || item.shipment.admin_note)}</p>` : ""}</div>` : ""}
      ${item.return_request ? `<div class="shipment-box"><small>İade kodu: ${esc(item.return_request.return_code || "-")}</small>
        <p>${esc(item.return_request.return_status)} · ${esc(item.return_request.refund_status)}</p>
        <p>${esc(item.return_request.return_reason || "")}</p>
        <button class="icon-button-small return-chat-button" data-chat-prompt="${esc(`${item.return_request.return_code} iade kodumla süreci nasıl takip ederim?`)}">${icons.chat} Copilot'a sor</button></div>` : ""}
      <div class="order-flow-actions">
        ${item.return_request ? `<span class="status-chip">İade talebi açıldı</span>`
          : canRequestReturn(item) ? `<button class="primary-button" data-create-return="${item.id}">${icons.box} İade talebi oluştur</button>`
          : `<span class="status-chip">İade için uygun değil</span>`}
        <button data-chat-prompt="${esc(`${item.order_no} siparişimdeki ürün için iade süreci nasıl olur?`)}">${icons.chat} Copilot'a sor</button>
      </div>
      ${item.admin_note ? `<div class="ticket-note admin-note"><small>Admin notu</small><p>${esc(item.admin_note)}</p></div>` : ""}
      ${admin && state.editingDemoOrderId === item.id ? `<div class="admin-demo-editor">
        <label>Sipariş durumu<select data-demo-order-status="${item.id}">${["CREATED", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED", "REFUND_PENDING"].map(status => `<option value="${status}" ${status === item.order_status ? "selected" : ""}>${demoStatusLabel(status)}</option>`).join("")}</select></label>
        <label>Ödeme durumu<select data-demo-payment-status="${item.id}">${["SUCCESS", "FAILED", "CAPTURED_NO_ORDER", "REFUND_PENDING"].map(status => `<option value="${status}" ${status === item.payment_status ? "selected" : ""}>${demoStatusLabel(status)}</option>`).join("")}</select></label>
        <label>Kargo durumu<select data-demo-shipping-status="${item.id}">${["PREPARING", "SHIPPED", "IN_TRANSIT", "DELAYED", "LOST", "DELIVERED", "PARTIALLY_DELIVERED"].map(status => `<option value="${status}" ${status === item.shipping_status ? "selected" : ""}>${demoStatusLabel(status)}</option>`).join("")}</select></label>
        <label>Takip no<input data-demo-tracking="${item.id}" placeholder="TRK..." value="${esc(item.shipment?.tracking_number || "")}"></label>
        <label class="full-field">Admin notu<textarea data-demo-note="${item.id}" maxlength="1000" placeholder="Gecikme nedeni veya admin notu">${esc(item.admin_note || item.shipment?.delay_reason || "")}</textarea></label>
        <div class="editor-actions"><button data-cancel-demo-edit="${item.id}">Vazgeç</button><button class="primary-button" data-update-demo-order="${item.id}">Güncelle</button></div>
      </div>` : ""}
    </article>`).join("") || `<div class="empty-state">Demo sipariş bulunmuyor.</div>`}</section>
    ${admin ? `<section class="coupon-section"><div class="section-head"><h3>Demo kuponlar</h3><span>${state.adminCoupons.length} kayıt</span></div>
      <div class="coupon-grid">${state.adminCoupons.map(coupon => `<article class="coupon-card">
        <div><strong>${esc(coupon.code)}</strong><span class="status-chip">${esc(demoStatusLabel(coupon.status))}</span></div>
        <p>${coupon.discount_type === "PERCENT" ? `%${coupon.discount_value}` : money(coupon.discount_value)} indirim · Min: ${money(coupon.min_cart_total)} · Kategori: ${esc(coupon.allowed_category || "Tümü")}</p>
        <button class="icon-danger" data-delete-demo-coupon="${coupon.id}" aria-label="Kupon sil">${icons.trash} Sil</button>
      </article>`).join("")}</div></section>` : ""}
    ${admin ? `<section class="coupon-section"><div class="section-head"><h3>İade ve refund</h3><span>${state.adminReturns.length} kayıt</span></div>
      <div class="coupon-grid">${state.adminReturns.map(item => `<article class="coupon-card">
        <div><strong>${esc(item.return_code || item.order_id)}</strong><span class="status-chip">${esc(item.return_status)}</span></div>
        <p>${esc(item.return_reason || "")}</p>
        <small>${esc(item.refund_status)}${item.refund ? ` · ${money(item.refund.refund_amount)}` : ""}</small>
      </article>`).join("") || "<p>İade kaydı yok.</p>"}</div></section>` : ""}
    ${admin ? `<section class="coupon-section"><div class="section-head"><h3>Cüzdan / kart / güvenlik</h3><span>${state.adminWallets.length} / ${state.adminCards.length} / ${state.adminSecurityProfiles.length}</span></div>
      <div class="coupon-grid">
        <article class="coupon-card">
          <strong>Cüzdan</strong>
          ${state.adminWallets.map(wallet => `<p>${wallet.user_id}: ${money(wallet.balance)} · ${esc(wallet.status)}</p>`).join("") || "<p>Cüzdan kaydı yok.</p>"}
        </article>
        <article class="coupon-card">
          <strong>Kartlar</strong>
          ${state.adminCards.map(card => `<p>${card.user_id}: ${esc(card.card_brand)} ****${esc(card.last4)} ${card.is_default ? "(varsayılan)" : ""}</p>`).join("") || "<p>Kart kaydı yok.</p>"}
        </article>
        <article class="coupon-card">
          <strong>Güvenlik</strong>
          ${state.adminSecurityProfiles.map(profile => `<p>${profile.user_id}: ${esc(profile.security_status)} · ${esc(profile.risk_note || "")}</p>`).join("") || "<p>Güvenlik kaydı yok.</p>"}
        </article>
      </div></section>` : ""}`;
}

function sourceModal() {
  if (!state.sourceModal) return "";
  const source = state.sourceModal;
  return `<div class="modal-layer"><div class="modal-backdrop" data-action="close-source"></div>
    <section class="card modal source-modal">
      <button class="modal-close" data-action="close-source" aria-label="Kapat">${icons.close}</button>
      <span class="modal-eyebrow">RAG kaynağı · %${((source.best_score || 0) * 100).toFixed(1)} eşleşme</span>
      <h2>${esc(source.title)}</h2>
      <pre>${esc(source.combined_context || "Bu kaynak eski bir görüşmeden geldiği için context içeriği kaydedilmemiş.")}</pre>
    </section></div>`;
}

function ticketModal() {
  if (!state.ticketModal) return "";
  const directTicket = state.ticketModal.mode === "direct";
  return `<div class="modal-layer"><div class="modal-backdrop" data-action="close-modal"></div>
    <section class="card modal"><h2>Manuel destek talebi</h2>
      <p>${directTicket ? "Bu cevapla ilgili destek ekibine doğrudan ticket gönderebilirsiniz." : "Yanıt sorununuzu çözmediyse ilgili destek ekibine ticket gönderebilirsiniz."}</p>
      <textarea maxlength="1000" data-ticket-modal-note placeholder="Sorunu kısaca açıklayın"></textarea>
      <div class="modal-actions"><button data-action="close-modal">Şimdilik kapat</button>
      <button class="primary-button" data-action="submit-ticket">${directTicket ? "Ticket aç" : "Feedback ver ve ticket aç"}</button></div>
      ${directTicket ? "" : `<button class="text-button" data-action="feedback-only">Yalnızca olumsuz feedback ver</button>`}
    </section></div>`;
}

function render() {
  if (state.loading && !state.user) {
    document.querySelector("#app").innerHTML = `<div class="loading-screen">Yükleniyor...</div>`;
    return;
  }
  if (!state.user) {
    document.querySelector("#app").innerHTML = loginPage();
    return;
  }
  if (state.page === "chat") state.page = "shop";
  const content = state.page === "history" ? historyPage()
    : state.page === "shop" ? shopPage()
    : state.page === "favorites" ? favoritesPage()
    : state.page === "returns" ? returnsPage()
    : state.page === "orders" ? demoOrdersPage(false)
    : state.page === "tickets" ? ticketsPage(false)
    : state.page === "admin-demo" ? demoOrdersPage(true)
    : ticketsPage(true);
  document.querySelector("#app").innerHTML =
    `<div class="app-shell ${state.theme === "dark" ? "dark" : ""}">${sidebar()}<main class="main-content">${content}</main>${floatingCopilotButton()}${copilotDrawer()}${productDetailModal()}${ticketModal()}${sourceModal()}</div>`;
  bind();
  requestAnimationFrame(() => {
    const messages = document.querySelector(".messages");
    if (messages) messages.scrollTop = messages.scrollHeight;
  });
}

async function ensureConversation() {
  if (state.conversationId) return state.conversationId;
  const conversation = await api(`${API}/conversations`, {
    method: "POST", body: JSON.stringify({ title: "Yeni görüşme" })
  });
  state.conversationId = conversation.id;
  return conversation.id;
}

async function refreshContext(content) {
  try {
    const result = await api(`${API}/rag/search`, {
      method: "POST", body: JSON.stringify({ query: content, limit: 20 })
    });
    state.contextPreview = result.llm_context || "Eşleşen context bulunamadı.";
  } catch (error) {
    state.contextPreview = `Context alınamadı: ${error.message}`;
  }
}

async function sendMessage(text) {
  const content = text.trim();
  if (!content || state.loading) return;
  state.messages.push({ role: "USER", content });
  state.loading = true;
  render();
  const contextPromise = refreshContext(content);
  try {
    const id = await ensureConversation();
    const result = await api(`${API}/conversations/${id}/messages`, {
      method: "POST", body: JSON.stringify({ message: content })
    });
    state.messages.push({
      id: result.assistant_message_id, role: "ASSISTANT", content: result.answer,
      confidence: result.confidence, confidence_score: result.confidence_score,
      priority: result.priority, ticket_available: result.ticket_available,
      ticket_recommended: result.ticket_recommended, sources: result.sources,
      similar_solutions: result.similar_solutions
    });
  } catch (error) {
    state.messages.push({ role: "ASSISTANT", content: error.message, confidence: null });
  } finally {
    await contextPromise;
    state.loading = false;
    render();
  }
}

async function loadPage(page) {
  state.page = page;
  try {
    if (page === "history") state.conversations = await api(`${API}/conversations`);
    if (page === "shop") {
      state.products = await api(`${API}/demo/products`);
      state.cart = await api(`${API}/demo/cart`);
      state.favorites = await api(`${API}/demo/favorites`);
      state.returns = await api(`${API}/demo/returns`);
      state.demoOrders = await api(`${API}/demo/orders`);
    }
    if (page === "favorites") state.favorites = await api(`${API}/demo/favorites`);
    if (page === "returns") state.returns = await api(`${API}/demo/returns`);
    if (page === "orders") state.demoOrders = await api(`${API}/demo/orders`);
    if (page === "tickets") state.tickets = await api(`${API}/tickets`);
    if (page === "admin") state.adminTickets = await api(`${API}/admin/tickets`);
    if (page === "admin-demo") {
      state.adminDemoOrders = await api(`${API}/admin/demo/orders`);
      state.adminCoupons = await api(`${API}/admin/demo/coupons`);
      state.adminProducts = await api(`${API}/admin/demo/products`);
      state.adminReviews = await api(`${API}/admin/demo/reviews`);
      state.adminReturns = await api(`${API}/admin/demo/returns`);
      state.adminWallets = await api(`${API}/admin/demo/wallets`);
      state.adminCards = await api(`${API}/admin/demo/cards`);
      state.adminSecurityProfiles = await api(`${API}/admin/demo/security-profiles`);
    }
  } catch (error) {
    toast(error.message);
  }
  render();
}

async function loadConversation(id) {
  const result = await api(`${API}/conversations/${id}`);
  state.conversationId = result.id;
  state.messages = result.messages;
  state.page = "shop";
  state.copilotOpen = true;
  render();
}

async function submitFeedback(id, value, openTicket = false, note = "") {
  const result = await api(`${API}/messages/${id}/feedback`, {
    method: "POST", body: JSON.stringify({ value, open_ticket: openTicket, note })
  });
  state.messages = state.messages.map(item =>
    item.id === Number(id) ? { ...item, user_feedback: value } : item
  );
  toast(result.ticket_id ? `Ticket #${result.ticket_id} oluşturuldu.` : result.status);
  render();
}

async function createTicket(id, note = "") {
  const result = await api(`${API}/messages/${id}/ticket`, {
    method: "POST", body: JSON.stringify({ note })
  });
  toast(`Ticket #${result.id} oluşturuldu.`);
}

async function refreshShop() {
  state.products = await api(`${API}/demo/products`);
  state.cart = await api(`${API}/demo/cart`);
  state.favorites = await api(`${API}/demo/favorites`);
  state.returns = await api(`${API}/demo/returns`);
  state.demoOrders = await api(`${API}/demo/orders`);
}

async function openProductDetail(productId) {
  state.productDetail = await api(`${API}/demo/products/${productId}`);
  state.productDetailDraft = { rating: "", title: "", body: "" };
  render();
}

async function toggleProductFavorite(productId) {
  const active = state.productDetail?.id === Number(productId) ? state.productDetail.is_favorited : null;
  if (active) {
    await api(`${API}/demo/favorites/${productId}`, { method: "DELETE" });
    toast("Favoriden çıkarıldı.");
  } else {
    await api(`${API}/demo/favorites/${productId}`, { method: "POST" });
    toast("Favorilere eklendi.");
  }
  await refreshShop();
  if (state.productDetail?.id === Number(productId)) {
    state.productDetail = await api(`${API}/demo/products/${productId}`);
  }
  render();
}

async function removeFavorite(productId) {
  await api(`${API}/demo/favorites/${productId}`, { method: "DELETE" });
  toast("Favoriden çıkarıldı.");
  await refreshShop();
  render();
}

async function submitProductReview(productId, form) {
  const rating = form.querySelector("[name='rating']").value;
  const title = form.querySelector("[name='title']").value;
  const body = form.querySelector("[name='body']").value;
  await api(`${API}/demo/products/${productId}/reviews`, {
    method: "POST",
    body: JSON.stringify({
      rating: rating === "" ? null : Number(rating),
      title,
      body
    })
  });
  toast("Yorum kaydedildi.");
  state.productDetail = await api(`${API}/demo/products/${productId}`);
  await refreshShop();
  render();
}

function bind() {
  document.querySelector(".message-form")?.addEventListener("submit", event => {
    event.preventDefault();
    const textarea = event.currentTarget.querySelector("textarea");
    const value = textarea.value;
    textarea.value = "";
    sendMessage(value);
  });
  document.querySelector(".message-form textarea")?.addEventListener("keydown", event => {
    if (event.isComposing || event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  });
  document.querySelectorAll("[data-faq]").forEach(node =>
    node.addEventListener("click", () => sendMessage(FAQ[Number(node.dataset.faq)])));
  document.querySelectorAll("[data-page]").forEach(node =>
    node.addEventListener("click", () => loadPage(node.dataset.page)));
  document.querySelector("[data-action='new-chat']")?.addEventListener("click", () => {
    state.conversationId = null;
    state.messages = [];
    state.contextPreview = "";
    state.copilotOpen = true;
    state.page = "shop";
    render();
  });
  document.querySelectorAll("[data-chat-prompt]").forEach(node =>
    node.addEventListener("click", async event => {
      event.stopPropagation();
      state.copilotOpen = true;
      await sendMessage(node.dataset.chatPrompt);
    }));
  document.querySelector("[data-action='logout']")?.addEventListener("click", async () => {
    await api("/auth/logout", { method: "POST" }); location.reload();
  });
  document.querySelector("[data-action='theme']")?.addEventListener("click", () => {
    state.theme = state.theme === "dark" ? "light" : "dark";
    localStorage.setItem("destekai-theme", state.theme); render();
  });
  document.querySelectorAll("[data-product-open]").forEach(node =>
    node.addEventListener("click", () => openProductDetail(node.dataset.productOpen)));
  document.querySelectorAll("[data-action='toggle-copilot']").forEach(node =>
    node.addEventListener("click", () => {
      state.copilotOpen = !state.copilotOpen;
      render();
    }));
  document.querySelectorAll("[data-action='close-product-detail']").forEach(node =>
    node.addEventListener("click", () => {
      state.productDetail = null;
      state.productDetailDraft = { rating: "", title: "", body: "" };
      render();
    }));
  document.querySelector("[data-action='clear-product-filters']")?.addEventListener("click", () => {
    state.productQuery = "";
    state.productCategory = "";
    render();
  });
  document.querySelector("[data-product-search]")?.addEventListener("input", event => {
    state.productQuery = event.currentTarget.value;
    render();
  });
  document.querySelector("[data-product-category]")?.addEventListener("change", event => {
    state.productCategory = event.currentTarget.value;
    render();
  });
  document.querySelectorAll("[data-product-favorite]").forEach(node =>
    node.addEventListener("click", () => toggleProductFavorite(node.dataset.productFavorite)));
  document.querySelectorAll("[data-remove-favorite]").forEach(node =>
    node.addEventListener("click", () => removeFavorite(node.dataset.removeFavorite)));
  document.querySelectorAll("[data-review-form]").forEach(node =>
    node.addEventListener("submit", event => {
      event.preventDefault();
      submitProductReview(node.dataset.reviewForm, event.currentTarget);
    }));
  document.querySelector("[data-action='chat-product']")?.addEventListener("click", async () => {
    state.copilotOpen = true;
    const product = state.productDetail;
    if (product) {
      await sendMessage(`${product.name} hakkında bilgi verir misin?`);
    }
  });
  document.querySelector("[data-action='context']")?.addEventListener("click", () => {
    state.contextOpen = !state.contextOpen; render();
  });
  document.querySelectorAll("[data-conversation]").forEach(node =>
    node.addEventListener("click", () => loadConversation(node.dataset.conversation)));
  document.querySelectorAll("[data-message]").forEach(node => node.addEventListener("click", async () => {
    if (node.dataset.value === "UNHELPFUL") {
      state.ticketModal = { messageId: node.dataset.message, mode: "feedback" }; render(); return;
    }
    await submitFeedback(node.dataset.message, "HELPFUL");
  }));
  document.querySelectorAll("[data-open-ticket]").forEach(node => node.addEventListener("click", () => {
    state.ticketModal = { messageId: node.dataset.openTicket, mode: "direct" }; render();
  }));
  document.querySelectorAll("[data-source-index]").forEach(node => node.addEventListener("click", event => {
    event.preventDefault();
    const message = state.messages.find(item => String(item.id) === node.dataset.sourceMessage);
    state.sourceModal = message?.sources?.[Number(node.dataset.sourceIndex)] || null;
    render();
  }));
  document.querySelectorAll("[data-action='close-source']").forEach(node =>
    node.addEventListener("click", () => { state.sourceModal = null; render(); }));
  document.querySelectorAll("[data-action='close-modal']").forEach(node =>
    node.addEventListener("click", () => { state.ticketModal = null; render(); }));
  document.querySelector("[data-action='feedback-only']")?.addEventListener("click", async () => {
    const id = state.ticketModal.messageId; state.ticketModal = null;
    await submitFeedback(id, "UNHELPFUL"); render();
  });
  document.querySelector("[data-action='submit-ticket']")?.addEventListener("click", async () => {
    const id = state.ticketModal.messageId;
    const mode = state.ticketModal.mode;
    const note = document.querySelector("[data-ticket-modal-note]").value;
    state.ticketModal = null;
    if (mode === "direct") await createTicket(id, note);
    else await submitFeedback(id, "UNHELPFUL", true, note);
    render();
  });
  document.querySelectorAll("[data-similar]").forEach(node => node.addEventListener("click", async () => {
    const result = await api(`${API}/similar-solutions/${node.dataset.similar}/feedback`, {
      method: "POST", body: JSON.stringify({ value: node.dataset.value })
    }); toast(result.status);
  }));
  document.querySelectorAll("[data-update-ticket]").forEach(node => node.addEventListener("click", async () => {
    const id = node.dataset.updateTicket;
    const status = document.querySelector(`[data-ticket-status='${id}']`).value;
    const adminNote = document.querySelector(`[data-ticket-note='${id}']`).value;
    await api(`${API}/admin/tickets/${id}`, {
      method: "PATCH", body: JSON.stringify({ status, admin_note: adminNote })
    });
    state.editingTicketId = null;
    await loadPage("admin"); toast("Ticket güncellendi.");
  }));
  document.querySelectorAll("[data-edit-ticket]").forEach(node => node.addEventListener("click", () => {
    state.editingTicketId = Number(node.dataset.editTicket); render();
  }));
  document.querySelectorAll("[data-cancel-ticket-edit]").forEach(node => node.addEventListener("click", () => {
    state.editingTicketId = null; render();
  }));
  document.querySelectorAll("[data-add-product]").forEach(node => node.addEventListener("click", async event => {
    event.stopPropagation();
    state.cart = await api(`${API}/demo/cart/items`, {
      method: "POST", body: JSON.stringify({ product_id: Number(node.dataset.addProduct), quantity: 1 })
    });
    toast("Ürün sepete eklendi."); render();
  }));
  document.querySelectorAll("[data-cart-qty]").forEach(node => node.addEventListener("change", async () => {
    state.cart = await api(`${API}/demo/cart/items/${node.dataset.cartQty}`, {
      method: "PATCH", body: JSON.stringify({ quantity: Number(node.value) || 1 })
    });
    render();
  }));
  document.querySelectorAll("[data-remove-cart]").forEach(node => node.addEventListener("click", async () => {
    state.cart = await api(`${API}/demo/cart/items/${node.dataset.removeCart}`, { method: "DELETE" });
    render();
  }));
  document.querySelector("[data-action='apply-coupon']")?.addEventListener("click", async () => {
    const code = document.querySelector("[data-coupon-code]").value;
    state.cart = await api(`${API}/demo/cart/apply-coupon`, {
      method: "POST", body: JSON.stringify({ code })
    });
    toast(state.cart.coupon_message || "Kupon kontrol edildi."); render();
  });
  document.querySelector("[data-action='checkout']")?.addEventListener("click", async () => {
    const order = await api(`${API}/demo/orders/checkout`, { method: "POST" });
    toast(`Sipariş oluşturuldu: ${order.order_no}`);
    await refreshShop(); render();
  });
  document.querySelector("[data-action='demo-reset']")?.addEventListener("click", async () => {
    const result = await api(`${API}/demo/reset`, { method: "POST" });
    toast(result.status);
    await refreshShop(); render();
  });
  document.querySelectorAll("[data-edit-demo-order]").forEach(node => node.addEventListener("click", () => {
    state.editingDemoOrderId = Number(node.dataset.editDemoOrder); render();
  }));
  document.querySelectorAll("[data-cancel-demo-edit]").forEach(node => node.addEventListener("click", () => {
    state.editingDemoOrderId = null; render();
  }));
  document.querySelectorAll("[data-delete-demo-order]").forEach(node => node.addEventListener("click", async () => {
    const id = node.dataset.deleteDemoOrder;
    const admin = node.dataset.admin === "1";
    await api(`${API}/${admin ? "admin/" : ""}demo/orders/${id}`, { method: "DELETE" });
    toast("Demo sipariş silindi.");
    await loadPage(admin ? "admin-demo" : "orders");
  }));
  document.querySelectorAll("[data-create-return]").forEach(node => node.addEventListener("click", async () => {
    const result = await api(`${API}/demo/orders/${node.dataset.createReturn}/return`, { method: "POST" });
    toast(`İade talebi oluşturuldu: ${result.return_code}`);
    await loadPage("orders");
  }));
  document.querySelectorAll("[data-delete-demo-coupon]").forEach(node => node.addEventListener("click", async () => {
    await api(`${API}/admin/demo/coupons/${node.dataset.deleteDemoCoupon}`, { method: "DELETE" });
    toast("Kupon silindi.");
    await loadPage("admin-demo");
  }));
  document.querySelectorAll("[data-update-demo-order]").forEach(node => node.addEventListener("click", async () => {
    const id = node.dataset.updateDemoOrder;
    const orderStatus = document.querySelector(`[data-demo-order-status='${id}']`).value;
    const paymentStatus = document.querySelector(`[data-demo-payment-status='${id}']`).value;
    const shippingStatus = document.querySelector(`[data-demo-shipping-status='${id}']`).value;
    const tracking = document.querySelector(`[data-demo-tracking='${id}']`).value;
    const note = document.querySelector(`[data-demo-note='${id}']`).value;
    await api(`${API}/admin/demo/orders/${id}`, {
      method: "PATCH", body: JSON.stringify({ order_status: orderStatus, payment_status: paymentStatus, admin_note: note })
    });
    await api(`${API}/admin/demo/orders/${id}/shipment`, {
      method: "PATCH", body: JSON.stringify({ shipping_status: shippingStatus, tracking_number: tracking, delay_reason: note, admin_note: note })
    });
    state.editingDemoOrderId = null;
    toast("Demo sipariş güncellendi.");
    await loadPage("admin-demo");
  }));
}

async function boot() {
  try {
    state.user = await api("/auth/me");
  } catch (error) {
    if (!error.message.includes("Giriş")) state.error = error.message;
  } finally {
    state.loading = false; render();
    if (state.user) await loadPage(state.page);
  }
}

boot();

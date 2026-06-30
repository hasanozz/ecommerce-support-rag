const API = "/api";
const ADMIN_FEEDBACK_ANALYTICS_ENDPOINT = `${API}/admin/feedback-analytics`;
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
  scenarioStatuses: [],
  cart: null,
  demoOrders: [],
  adminDemoOrders: [],
  adminCoupons: [],
  adminProducts: [],
  adminReviews: [],
  adminFeedbackAnalytics: null,
  adminFeedbackLoading: false,
  adminFeedbackError: "",
  adminFeedbackCommentOpen: {},
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
  productDetailTab: "overview",
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
  bot: `<svg viewBox="0 0 24 24"><path d="M9 7V5h6v2"/><rect x="5" y="7" width="14" height="11" rx="3"/><circle cx="10" cy="12" r="1"/><circle cx="14" cy="12" r="1"/><path d="M8 16h8"/><path d="M12 4v1"/></svg>`,
  copilot: `<svg viewBox="0 0 24 24"><path d="M6 5h9.5A3.5 3.5 0 0 1 19 8.5V13a3 3 0 0 1-3 3h-4.5L8 19v-3H6a3 3 0 0 1-3-3V8a3 3 0 0 1 3-3Z"/><path d="M13.5 7.5h3"/><path d="M15 6v3"/><path d="M8.2 9.2h2.6v2.6H8.2z"/></svg>`,
  arrow: `<svg viewBox="0 0 24 24"><path d="M5 12h13M13 6l5 6-5 6"/></svg>`,
  send: `<svg viewBox="0 0 24 24"><path d="m4 4 17 8-17 8 3-8-3-8Z"/><path d="M7 12h14"/></svg>`,
  up: `<svg viewBox="0 0 24 24"><path d="M7 10v10H3V10h4Zm0 9h10.5a2 2 0 0 0 1.9-1.4l1.4-5A2 2 0 0 0 19 10h-4l1-4c.3-1.4-.7-2.7-2.1-2.7L7 10v9Z"/></svg>`,
  down: `<svg viewBox="0 0 24 24"><path d="M7 14V4H3v10h4Zm0-9h10.5a2 2 0 0 1 1.9 1.4l1.4 5A2 2 0 0 1 19 14h-4l1 4c.3 1.4-.7 2.7-2.1 2.7L7 14V5Z"/></svg>`,
  logout: `<svg viewBox="0 0 24 24"><path d="M10 5H5v14h5M14 8l4 4-4 4M8 12h10"/></svg>`,
  user: `<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>`,
  edit: `<svg viewBox="0 0 24 24"><path d="m4 20 4.5-1 10-10-3.5-3.5-10 10L4 20Z"/><path d="m13.5 6.5 3.5 3.5"/></svg>`,
  close: `<svg viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18"/></svg>`,
  trash: `<svg viewBox="0 0 24 24"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 14h10l1-14M9 7V4h6v3"/></svg>`,
  cart: `<svg viewBox="0 0 24 24"><path d="M5 6h16l-2 8H7L5 3H2"/><circle cx="8" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/></svg>`,
  box: `<svg viewBox="0 0 24 24"><path d="m3 7 9-4 9 4-9 4-9-4Z"/><path d="M3 7v10l9 4 9-4V7M12 11v10"/></svg>`
  ,
  heart: `<svg viewBox="0 0 24 24"><path d="M12 21s-7-4.4-9.2-8.6C.9 8.9 3.2 5 7 5c2.1 0 3.7 1.1 5 2.7C13.3 6.1 14.9 5 17 5c3.8 0 6.1 3.9 4.2 7.4C19 16.6 12 21 12 21Z"/></svg>`,
  star: `<svg viewBox="0 0 24 24"><path d="m12 3 2.9 6 6.6.9-4.8 4.7 1.2 6.5L12 18.9 6.1 21l1.2-6.5L2.5 9.9 9.1 9 12 3Z"/></svg>`,
  search: `<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>`,
  shield: `<svg viewBox="0 0 24 24"><path d="M12 3 20 6v6c0 5-3.4 8.7-8 11-4.6-2.3-8-6-8-11V6l8-3Z"/></svg>`,
  moon: `<svg viewBox="0 0 24 24"><path d="M21 14.6A8.5 8.5 0 0 1 9.4 3a7 7 0 1 0 11.6 11.6Z"/></svg>`,
  sun: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>`
};

const DEMO_SCENARIOS = [
  {
    key: "payment-captured-no-order",
    name: "Ödeme alındı ama sipariş oluşmadı",
    description: "Başarılı ödeme kaydı var, ancak bağlı sipariş kaydı yok.",
    area: "Ödeme",
    icon: icons.ticket
  },
  {
    key: "order-not-shipped",
    name: "Hazırlanan sipariş kargoya verilmedi",
    description: "Ödemesi tamamlanmış sipariş hazırlıkta bekliyor.",
    area: "Kargo",
    icon: icons.box
  },
  {
    key: "delivered-not-received",
    name: "Teslim edildi görünüyor ama ulaşmadı",
    description: "Kargo teslim edildi statüsünde, müşteri ürünü almadığını bildiriyor.",
    area: "Teslimat",
    icon: icons.search
  },
  {
    key: "returnable-product",
    name: "İade edilebilir ürün",
    description: "Teslim edilmiş ve iade talebi için uygun ürün siparişi hazırlanır.",
    area: "İade",
    icon: icons.logout
  },
  {
    key: "non-returnable-product",
    name: "İade edilemeyen ürün",
    description: "İade politikası kısıtlı ürünle teslim edilmiş sipariş hazırlanır.",
    area: "İade",
    icon: icons.shield
  },
  {
    key: "expired-coupon",
    name: "Kupon süresi doldu",
    description: "Sepete süresi dolmuş kupon bağlamı eklenir.",
    area: "Kampanya",
    icon: icons.star
  }
];

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

function normalizeAdminFeedbackAnalytics(result = {}) {
  const recentFeedback = (result.recentFeedback ?? result.recent_feedback ?? []).map(item => ({
    ...item,
    messageId: item.messageId ?? item.message_id ?? null,
    aiAnswer: item.aiAnswer ?? item.ai_answer ?? "",
    canonicalQuery: item.canonicalQuery ?? item.canonical_query ?? null,
    confidenceScore: item.confidenceScore ?? item.confidence_score ?? null,
    feedbackValue: item.feedbackValue ?? item.feedback_value ?? "UNHELPFUL",
    feedbackComment: item.feedbackComment ?? item.feedback_comment ?? null,
    feedbackCreatedAt: item.feedbackCreatedAt ?? item.feedback_created_at ?? null,
    userId: item.userId ?? item.user_id ?? null,
    modelName: item.modelName ?? item.model_name ?? null,
    totalTokens: item.totalTokens ?? item.total_tokens ?? null,
    sources: Array.isArray(item.sources) ? item.sources : []
  }));
  const categoryBreakdown = (result.categoryBreakdown ?? result.category_breakdown ?? []).map(item => ({
    ...item,
    helpfulCount: item.helpfulCount ?? item.helpful_count ?? 0,
    unhelpfulCount: item.unhelpfulCount ?? item.unhelpful_count ?? 0,
    helpfulRate: item.helpfulRate ?? item.helpful_rate ?? 0,
    total: item.total ?? 0,
    category: item.category || "Bilinmiyor"
  }));
  return {
    ...result,
    totalFeedback: result.totalFeedback ?? result.total_feedback ?? 0,
    helpfulCount: result.helpfulCount ?? result.helpful_count ?? 0,
    unhelpfulCount: result.unhelpfulCount ?? result.unhelpful_count ?? 0,
    helpfulRate: result.helpfulRate ?? result.helpful_rate ?? 0,
    unhelpfulRate: result.unhelpfulRate ?? result.unhelpful_rate ?? 0,
    averageConfidenceScore: result.averageConfidenceScore ?? result.average_confidence_score ?? null,
    categoryBreakdown,
    recentFeedback,
    total_feedback: result.total_feedback ?? result.totalFeedback ?? 0,
    helpful_count: result.helpful_count ?? result.helpfulCount ?? 0,
    unhelpful_count: result.unhelpful_count ?? result.unhelpfulCount ?? 0,
    helpful_rate: result.helpful_rate ?? result.helpfulRate ?? 0,
    unhelpful_rate: result.unhelpful_rate ?? result.unhelpfulRate ?? 0,
    average_confidence_score: result.average_confidence_score ?? result.averageConfidenceScore ?? null,
    category_breakdown: categoryBreakdown,
    recent_feedback: recentFeedback
  };
}

async function api(path, options = {}, timeoutMs = 15000) {
  const controller = timeoutMs > 0 ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      signal: controller?.signal,
      ...options
    });
    if (response.status === 204) return null;
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = body.detail;
      const message = typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map(item => item.msg || JSON.stringify(item)).join(" ")
          : detail
            ? JSON.stringify(detail)
            : "İşlem tamamlanamadı.";
      throw new Error(message);
    }
    return body;
  } catch (error) {
    if (error?.name === "AbortError") throw new Error("İstek zaman aşımına uğradı.");
    throw error;
  } finally {
    if (timer) clearTimeout(timer);
  }
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
    <div class="sidebar-head">
      <button class="brand" data-page="shop" aria-label="TeknoCampus Copilot ana sayfası">
        <span class="brand-mark brand-mark-ai">${icons.copilot}</span>
        <span class="brand-copy"><strong>TeknoCampus Copilot</strong><small>AI Support Demo</small></span>
      </button>
    </div>
    <button class="new-chat" data-action="new-chat">${icons.bot}<span>AI Copilot</span></button>
    <nav>
      <button class="nav-item ${state.page === "shop" ? "active" : ""}" data-page="shop">${icons.box}<span>Mağaza</span></button>
      <button class="nav-item ${state.page === "orders" ? "active" : ""}" data-page="orders">${icons.clock}<span>Siparişlerim</span></button>
      <button class="nav-item ${state.page === "returns" ? "active" : ""}" data-page="returns">${icons.box}<span>İadelerim</span></button>
      <button class="nav-item ${state.page === "scenarios" ? "active" : ""}" data-page="scenarios">${icons.star}<span>Senaryolar</span></button>
      <button class="nav-item ${state.page === "favorites" ? "active" : ""}" data-page="favorites">${icons.heart}<span>Favorilerim</span></button>
      <button class="nav-item ${state.page === "tickets" ? "active" : ""}" data-page="tickets">${icons.ticket}<span>Destek Taleplerim</span></button>
      ${state.user?.is_admin ? `<button class="nav-item ${state.page === "admin-demo" ? "active" : ""}" data-page="admin-demo">${icons.edit}<span>Yönetim Paneli</span></button>` : ""}
      ${state.user?.is_admin ? `<button class="nav-item ${state.page === "admin" ? "active" : ""}" data-page="admin">${icons.ticket}<span>Admin Destek</span></button>` : ""}
    </nav>
    <div class="sidebar-help"><div class="account-summary"><span class="profile-outline" aria-hidden="true">${icons.user}</span><div><strong>${esc(state.user?.display_name || state.user?.email)}</strong>
      <span>${esc(state.user?.email)}</span></div></div><button data-action="logout" aria-label="Çıkış yap" title="Çıkış yap">${icons.logout} Çıkış yap</button>
    </div>
  </aside>`;
}

function topbar(title, description = "") {
  return `<header class="topbar"><div class="page-heading"><h1>${esc(title)}</h1><p>${esc(description)}</p></div>
    <button class="theme-toggle" data-action="theme" aria-label="${state.theme === "dark" ? "Aydınlık temaya geç" : "Koyu temaya geç"}" aria-pressed="${state.theme === "dark"}" title="${state.theme === "dark" ? "Aydınlık temaya geç" : "Koyu temaya geç"}">
      ${state.theme === "dark" ? icons.sun : icons.moon}
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

function supportCategoryLabel(category) {
  return ({
    SIPARIS: "Sipariş",
    KARGO_TESLIMAT: "Kargo",
    IADE: "İade",
    ODEME: "Ödeme",
    KAMPANYA_PUAN: "Kampanya",
    HESAP_GUVENLIK: "Hesap",
    GENEL_DESTEK: "Genel"
  })[category] || category || "Genel";
}

function supportCategoryIcon(category) {
  return ({
    SIPARIS: icons.box,
    KARGO_TESLIMAT: icons.truck || icons.box,
    IADE: icons.logout,
    ODEME: icons.ticket,
    KAMPANYA_PUAN: icons.star,
    HESAP_GUVENLIK: icons.shield,
    GENEL_DESTEK: icons.chat
  })[category] || icons.chat;
}

function latestAssistantMessage() {
  return [...state.messages].reverse().find(item => item.role === "ASSISTANT");
}

function latestUserMessage() {
  return [...state.messages].reverse().find(item => item.role === "USER");
}

function messageAnalysisHtml(item, compact = false) {
  if (!item) return "";
  const firstSource = item.sources?.[0];
  const confidence = typeof item.confidence_score === "number"
    ? `%${Math.round(item.confidence_score * 100)}`
    : item.confidence || "N/A";
  const action = item.ticket_recommended ? "Ticket önerildi" : "RAG yanıtı";
  const sourceCount = item.sources?.length || 0;
  const className = compact ? "analysis-grid compact" : "analysis-grid";
  return `<div class="${className}">
    <div class="analysis-item"><span>Kategori</span><strong>${esc(supportCategoryLabel(item.category))}</strong></div>
    <div class="analysis-item"><span>Alt kategori</span><strong>${esc(firstSource?.subcategory || item.canonical_query || "Genel destek")}</strong></div>
    <div class="analysis-item"><span>Aksiyon</span><strong>${esc(action)}</strong></div>
    <div class="analysis-item"><span>Güven</span><strong>${esc(confidence)}</strong></div>
    <div class="analysis-item"><span>Kaynak</span><strong>${sourceCount ? `${sourceCount} belge` : "0 belge"}</strong></div>
  </div>`;
}

function systemMetricsHtml() {
  const metrics = [
    { label: "5 Destek Kategorisi", value: "Sipariş, iade, ödeme, kargo, kampanya", note: "Soru otomatik sınıflandırılır.", icon: icons.box },
    { label: "RAG Yanıt Motoru", value: "Doküman referanslı cevap", note: "Yanıt kaynaklardan üretilir.", icon: icons.shield },
    { label: "Aksiyon Yönetimi", value: "Ticket ve yönlendirme", note: "Gerekirse sonraki adım açılır.", icon: icons.ticket },
    { label: "Kaynak Gösterimi", value: "İzlenebilir sonuç", note: "Kullanılan belgeler görünür.", icon: icons.star }
  ];
  return `<section class="system-metrics">${metrics.map(item => `
    <article class="metric-chip">
      <span class="metric-icon">${item.icon}</span>
      <span>${esc(item.label)}</span>
      <strong>${esc(item.value)}</strong>
      <small>${esc(item.note)}</small>
    </article>
  `).join("")}</section>`;
}

function usageFlowHtml() {
  const steps = ["Senaryoyu hazırla", "Copilot’a kendi cümlenle sor", "Kaynaklı cevabı ve aksiyonu incele"];
  return `<section class="usage-flow card">
    <div class="usage-flow-head">
      <strong>Demo Akışı</strong>
      <span>3 adım</span>
    </div>
    <div class="workflow-strip">${steps.map((step, index) => `
      <div class="workflow-step">
      <span>${index + 1}</span>
      <strong>${esc(step)}</strong>
      </div>
    `).join("")}</div>
  </section>`;
}

function copilotRailHtml() {
  const latest = latestAssistantMessage();
  const latestUser = latestUserMessage();
  const sourceCount = latest?.sources?.length || 0;
  const demoUser = latestUser?.content || "İade talebi nasıl oluşturulur?";
  const demoAnswer = latest?.content || "İade talebinizi hesap hareketleri ve sipariş kayıtları üzerinden açabilirsiniz. Uygun siparişe göre destek talebi oluşturulur.";
  const demoCategory = latest?.category || "IADE";
  const demoSubcategory = latest?.sources?.[0]?.subcategory || "İade talebi";
  const demoConfidence = typeof latest?.confidence_score === "number" ? `%${Math.round(latest.confidence_score * 100)}` : "%94";
  const demoAction = latest?.ticket_recommended ? "Ticket önerildi" : "RAG yanıtı";
  return `<section class="card support-rail-panel">
    <div class="copilot-rail-head">
      <div>
        <div class="status-row">
          <span class="ai-pill"><span class="online"></span>Canlı Demo</span>
          <span class="ai-pill ai-pill-ghost">RAG destekli</span>
        </div>
        <h3>AI Destek Asistanı</h3>
        <p>Soruları analiz eder, doğru dokümanı bulur ve aksiyon önerir.</p>
      </div>
      <button class="copilot-rail-toggle" data-action="toggle-copilot" aria-label="Copilot penceresini aç">${icons.bot}</button>
    </div>
    <div class="live-preview">
      <div class="preview-row user">
        <span>Kullanıcı sorusu</span>
        <p>${esc(demoUser)}</p>
      </div>
      <div class="preview-row bot">
        <span>Bot cevabı</span>
        <p>${esc(demoAnswer)}</p>
      </div>
    </div>
    <div class="analysis-grid compact">
      <div class="analysis-item"><span>Kategori</span><strong>${esc(supportCategoryLabel(demoCategory))}</strong></div>
      <div class="analysis-item"><span>Alt kategori</span><strong>${esc(demoSubcategory)}</strong></div>
      <div class="analysis-item"><span>Aksiyon</span><strong>${esc(demoAction)}</strong></div>
      <div class="analysis-item"><span>Güven</span><strong>${esc(demoConfidence)}</strong></div>
      <div class="analysis-item"><span>Kaynak</span><strong>${sourceCount ? `${sourceCount} belge` : "2 belge"}</strong></div>
    </div>
    <div class="rail-actions">
      <button data-chat-prompt="Bu cevabın dayandığı kaynakları kısa ve net özetler misin?">Kaynakları göster</button>
      <button data-action="open-support-ticket">Destek talebi aç</button>
      <button data-page="orders">Siparişlerime git</button>
      <button data-page="returns">İade sürecini başlat</button>
    </div>
    <div class="messages rail-messages">${copilotMessagesHtml()}</div>
    <form class="message-form rail-form" data-copilot-form>
      <textarea maxlength="1000" placeholder="Copilot'a sorunuzu yazın..." ${state.loading ? "disabled" : ""}></textarea>
      <button type="submit" ${state.loading ? "disabled" : ""}>${icons.send}</button>
    </form>
  </section>`;
}

function messagesHtml() {
  if (!state.messages.length) return `<div class="empty-chat"><span class="brand-mark">${icons.chat}</span>
    <h2>Size nasıl yardımcı olabiliriz?</h2>
    <p>Sipariş, iade, ödeme, kargo, hesap veya kampanya sorununuzu yazabilirsiniz.</p></div>`;
  return state.messages.map(item => item.role === "USER"
    ? `<div class="message user-message"><div class="message-text">${esc(item.content)}</div></div>`
    : `<div class="message ai-message"><span class="message-avatar ai-avatar">AI</span><div class="message-text">
        ${messageAnalysisHtml(item)}
        <div class="answer-body">${renderMarkdown(item.content)}</div>${sourceList(item.sources, item.id)}
        ${item.id ? (item.user_feedback ? `<div class="feedback-state ${item.user_feedback === "HELPFUL" ? "positive" : "negative"}">
            ${feedbackStatusLabel(item.user_feedback)}
          </div>` : `<div class="answer-actions">
            <div class="feedback-group"><button class="feedback" data-message="${item.id}" data-value="HELPFUL">${icons.up} İşime yaradı</button>
            <button class="feedback negative" data-message="${item.id}" data-value="UNHELPFUL">${icons.down} İşime yaramadı</button></div>
            <button class="open-ticket-button" data-open-ticket="${item.id}">${icons.ticket} Destek talebi aç</button>
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
  return ({ OPEN: "Gönderildi", PENDING: "Beklemede", IN_REVIEW: "İncelemede", RESOLVED: "Çözüldü" })[status] || status;
}

function ticketStatusClass(status) {
  return String(status || "OPEN").toLowerCase().replace(/[^a-z0-9]+/g, "_");
}

function userTicketCard(item) {
  const createdAt = new Date(item.created_at || item.updated_at).toLocaleString("tr-TR");
  const sourceText = item.source_message_id
    ? "Copilot yanıtı sonrası destek talebi oluşturuldu."
    : "Destek akışından oluşturuldu.";
  return `<article class="support-ticket-card">
    <div class="support-ticket-topline">
      <span class="ticket-number">Talep #${item.id}</span>
      <span class="status-chip status-${ticketStatusClass(item.status)}">${esc(statusLabel(item.status))}</span>
      <time>${createdAt}</time>
    </div>
    <div class="support-ticket-title">
      <span class="support-ticket-category">${esc(item.category || "GENEL")}</span>
      <h3>${esc(item.department || "Destek talebi")}</h3>
    </div>
    <div class="ticket-note user-ticket-note">
      <small>Kullanıcı açıklaması</small>
      <p>${esc(item.user_note || "Kullanıcı açıklama eklememiş.")}</p>
    </div>
    ${item.admin_note ? `<div class="ticket-note admin-note"><small>Destek ekibi notu</small><p>${esc(item.admin_note)}</p></div>` : ""}
    <div class="support-ticket-context">
      ${icons.bot}
      <span>${esc(sourceText)}</span>
    </div>
  </article>`;
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

function returnStatusLabel(status) {
  return ({
    CREATED: "Oluşturuldu",
    UNDER_REVIEW: "İncelemede",
    APPROVED: "Onaylandı",
    REJECTED: "Reddedildi",
    COMPLETED: "Tamamlandı"
  })[status] || demoStatusLabel(status);
}

function refundStatusLabel(status) {
  return ({
    PENDING: "Beklemede",
    APPROVED: "Onaylandı",
    COMPLETED: "Tamamlandı",
    FAILED: "Başarısız",
    REFUNDED: "İade edildi"
  })[status] || demoStatusLabel(status);
}

function returnRequestLabel(status) {
  return ({
    CREATED: "İade talebi oluşturuldu",
    RETURN_CODE_CREATED: "İade kodu oluşturuldu",
    UNDER_REVIEW: "İade kodu oluşturuldu",
    APPROVED: "İade onaylandı",
    REJECTED: "İade reddedildi"
  })[status] || "İade talebi";
}

function statusBadges(labels, limit = 3) {
  const unique = [...new Set(labels.filter(Boolean))];
  const visible = unique.slice(0, limit);
  const extra = unique.length - visible.length;
  return `${visible.map(label => `<span class="status-chip">${esc(label)}</span>`).join("")}${extra > 0 ? `<span class="status-chip">+${extra} durum</span>` : ""}`;
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
    home_kitchen: "Ev ve Mutfak",
    home_office: "Ev ve Ofis"
  })[category] || category;
}

function productInitial(name) {
  return esc((name || "Ü").trim().slice(0, 1).toLocaleUpperCase("tr-TR"));
}

function productDisplayName(item) {
  return (item.name || "").replace(/\s+\d+(?:[.,]\d+)?\s*(?:g|gr|kg|ml|l)$/i, "").trim();
}

function productVariantLabel(item) {
  const gramaj = item.attributes?.gramaj;
  if (gramaj) return `Gramaj: ${gramaj}`;
  return "";
}

const PRODUCT_IMAGE_POSITIONS = {
  "MARKET-CAY-SIYAH-500": ["0%", "0%"],
  "MARKET-CAY-YESIL-250": ["50%", "0%"],
  "MARKET-KAHVE-TURK-100": ["100%", "0%"],
  "COFFEE-FILTRE-250": ["0%", "33.333%"],
  "HOME-CAY-BARDAGI-6": ["50%", "33.333%"],
  "HOME-CAM-KUPA-001": ["100%", "33.333%"],
  "HOME-TERMOS-BARDAK-001": ["0%", "66.667%"],
  "COFFEE-MACHINE-FILTER-001": ["50%", "66.667%"],
  "BAGS-BACKPACK-001": ["100%", "66.667%"],
  "SHOES-SPORT-001": ["0%", "100%"],
  "ELECTRONICS-HEADPHONE-001": ["50%", "100%"]
};

function productImageHtml(item, large = false) {
  const className = `product-visual${large ? " large" : ""}`;
  const imageUrl = item.image_url || item.image_urls?.[0] || "";
  if (imageUrl) {
    return `<div class="${className}"><img src="${esc(imageUrl)}" alt="${esc(item.name)}" loading="lazy" onerror="this.hidden=true;this.parentElement.classList.add('image-missing');"><span class="product-image-placeholder">Görsel yüklenemedi</span></div>`;
  }
  if (item.sku === "WHITE-BLENDER-001") {
    return `<div class="${className}"><img src="/assets/assets/product-blender.png" alt="${esc(item.name)}" loading="lazy" onerror="this.hidden=true;this.parentElement.classList.add('image-missing');"><span class="product-image-placeholder">Görsel yüklenemedi</span></div>`;
  }
  const position = PRODUCT_IMAGE_POSITIONS[item.sku];
  if (position) {
    return `<div class="${className}"><span class="product-photo product-sheet" style="--shot-x: ${position[0]}; --shot-y: ${position[1]};" role="img" aria-label="${esc(item.name)}"></span></div>`;
  }
  return `<div class="${className}"><span class="product-initial">${productInitial(item.name)}</span></div>`;
}

function productRatingLabel(item) {
  if (!item) return "Puan yok";
  if (item.rating_average == null) return "Puan yok";
  return `${Number(item.rating_average).toFixed(1)} / 5 · ${item.review_count || 0} yorum`;
}

const PRODUCT_TECH_FALLBACKS = {
  "COFFEE-FILTER-100": [
    ["adet", 100],
    ["malzeme", "kagit"],
    ["uyumlu_kullanim", "Tek kullanımlık"],
    ["paket", "100 adet filtre"],
    ["bakim", "Her demleme için yeni filtre kullanılması önerilir."],
  ],
  "HOME-CAM-DEMLIK-001": [
    ["hacim_ml", 900],
    ["malzeme", "Isıya dayanıklı cam"],
    ["isi_dayanimi", "Sıcak içecek kullanımına uygun"],
    ["uyumlu_kullanim", "Çay ve bitki çayı"],
    ["bakim", "Bulaşık makinesinde yıkanabilir"],
    ["kapak_tipi", "cam kapak"],
  ],
  "HOME-SAKLAMA-KABI-3SET": [
    ["adet", 3],
    ["hacim_ml", "Farklı boylar"],
    ["malzeme", "cam"],
    ["kapak_tipi", "kilitli"],
    ["uyumlu_kullanim", "Kuru gıda ve mutfak düzeni"],
    ["bakim", "Elde veya bulaşık makinesinde yıkama önerilir."],
  ],
  "CLOTHING-SWEATSHIRT-001": [
    ["kumas", "pamuk_polyester"],
    ["kalip", "rahat"],
    ["bedenler", ["S", "M", "L", "XL"]],
    ["bakim", "30°C hassas yıkama"],
    ["uyumlu_kullanim", "Günlük kullanım"],
  ],
  "SPORT-YOGA-MAT-001": [
    ["kalinlik_mm", 6],
    ["olcu", "183 x 61 cm"],
    ["uzunluk_cm", 183],
    ["malzeme", "Kaymaz yüzeyli köpük"],
    ["kaymaz_yuzey", true],
    ["tasima_askisi", true],
  ],
  "ELECTRONICS-POWERBANK-10000": [
    ["kapasite_mah", 10000],
    ["guc_watt", 18],
    ["giris_cikis", "USB-C giriş, USB-A çıkış"],
    ["usb_c", true],
    ["usb_a_port", 2],
    ["hizli_sarj", true],
    ["guvenlik", "Aşırı akım ve kısa devre koruması"],
  ],
  "ELECTRONICS-WIRELESS-MOUSE-001": [
    ["baglanti", "2.4GHz"],
    ["dpi", 1600],
    ["pil_tipi", "AA"],
    ["sessiz_tiklama", true],
    ["uyumlu_kullanim", "Windows, macOS ve dizüstü bilgisayarlar"],
  ],
  "HOME-OFFICE-DESK-LAMP-001": [
    ["guc_watt", 8],
    ["baslik", "Ayarlanabilir"],
    ["isik_modu", "Okuma ve çalışma ışığı"],
    ["renk_sicakligi", "sicak_beyaz"],
    ["malzeme", "metal"],
    ["uyumlu_kullanim", "Çalışma masası ve okuma alanı"],
  ]
};

const PRODUCT_TECH_DEFAULTS = [
  ["malzeme", "Ürün sayfasında belirtilen standart malzeme"],
  ["uyumlu_kullanim", "Günlük kullanım"],
  ["bakim", "Kullanım kılavuzuna uygun bakım önerilir"]
];

function productTechnicalEntries(item) {
  const seen = new Set();
  const entries = [];
  const pushEntry = (key, value) => {
    const normalizedKey = String(key || "").trim();
    if (!normalizedKey || seen.has(normalizedKey)) return;
    seen.add(normalizedKey);
    entries.push({
      key: normalizedKey,
      label: attributeLabel(normalizedKey),
      value: attributeValue(normalizedKey, value),
      sentence: attributeSentence(normalizedKey, value)
    });
  };
  for (const [key, value] of Object.entries(item.attributes || {})) {
    pushEntry(key, value);
  }
  for (const [key, value] of PRODUCT_TECH_FALLBACKS[item.sku] || []) {
    pushEntry(key, value);
  }
  if (item.returnable !== undefined) {
    pushEntry("returnable", item.returnable);
  }
  if (item.return_policy_note) {
    pushEntry("return_policy_note", item.return_policy_note);
  }
  if (item.warranty_months != null) {
    pushEntry("warranty_months", item.warranty_months);
  }
  if (item.warranty_note) {
    pushEntry("warranty_note", item.warranty_note);
  }
  for (const [key, value] of PRODUCT_TECH_DEFAULTS) {
    if (entries.length >= 3) break;
    pushEntry(key, value);
  }
  return entries;
}

function productTechSummaryEntries(item, count = 4) {
  return productTechnicalEntries(item).slice(0, count);
}

const ATTRIBUTE_LABELS = {
  guc_watt: "Motor Gücü",
  hazne_litre: "Hazne Kapasitesi",
  hiz_kademesi: "Hız Kademesi",
  pil_suresi_saat: "Pil Süresi",
  laptop_bolmesi: "Laptop Bölmesi",
  suya_dayanikli: "Suya Dayanıklı",
  makinede_yikanabilir: "Bulaşık Makinesinde Yıkanabilir",
  mikrofon: "Mikrofon",
  gramaj: "Gramaj",
  tip: "Tip",
  malzeme: "Malzeme",
  paket: "Paket İçeriği",
  bakim: "Bakım / Yıkama",
  olcu: "Ölçü",
  isi_dayanimi: "Isı Dayanımı",
  giris_cikis: "Giriş / Çıkış",
  guvenlik: "Güvenlik",
  isik_modu: "Işık Modu",
  returnable: "İade Uygunluğu",
  return_policy_note: "İade Notu",
  warranty_months: "Garanti Süresi",
  warranty_note: "Garanti Notu",
  hacim_ml: "Hacim",
  adet: "Adet",
  uyumlu_kullanim: "Uyumlu Kullanım",
  kapak_tipi: "Kapak Tipi",
  kumas: "Kumaş",
  kalip: "Kalıp",
  renk: "Renk",
  bedenler: "Bedenler",
  kalinlik_mm: "Kalınlık",
  uzunluk_cm: "Uzunluk",
  kaymaz_yuzey: "Kaymaz Yüzey",
  tasima_askisi: "Taşıma Askısı",
  kapasite_mah: "Kapasite",
  usb_c: "USB-C",
  usb_a_port: "USB-A Port",
  hizli_sarj: "Hızlı Şarj",
  baglanti: "Bağlantı",
  dpi: "DPI",
  sessiz_tiklama: "Sessiz Tıklama",
  pil_tipi: "Pil Tipi",
  baslik: "Başlık",
  renk_sicakligi: "Renk Sıcaklığı"
};

const ATTRIBUTE_VALUE_LABELS = {
  dokme: "Dökme",
  poset: "Poşet",
  ince: "İnce",
  orta: "Orta",
  cam: "Cam",
  paslanmaz_celik: "Paslanmaz çelik",
  kaucuk: "Kauçuk",
  hafif_yagmur_dayanimi: "Hafif yağmur dayanımı",
  kagit: "Kağıt",
  filtre_kahve_makinesi: "Filtre kahve makinesi",
  isiya_dayanikli_cam: "Isıya dayanıklı cam",
  kilitli: "Kilitli",
  pamuk_polyester: "Pamuk-polyester",
  antrasit: "Antrasit",
  sicak_beyaz: "Sıcak beyaz",
  ayarlanabilir: "Ayarlanabilir",
  metal: "Metal",
  "2.4ghz": "2.4GHz"
};

function attributeLabel(key) {
  return ATTRIBUTE_LABELS[key] || String(key || "").replaceAll("_", " ");
}

function capitalizeTechnicalText(text) {
  const normalized = String(text || "").trim().replace(/\s+/g, " ");
  if (!normalized) return "";
  return normalized.charAt(0).toLocaleUpperCase("tr-TR") + normalized.slice(1);
}

function attributeValue(key, value) {
  if (typeof value === "boolean") return value ? "Var" : "Yok";
  if (Array.isArray(value)) {
    const values = value.map(item => attributeValue(key, item));
    return values.length > 1 ? `${values.slice(0, -1).join(", ")} ve ${values.at(-1)}` : values[0] || "";
  }
  const rawText = String(value ?? "");
  const normalizedRaw = rawText.toLocaleLowerCase("tr-TR");
  let text = typeof value === "number"
    ? value.toLocaleString("tr-TR")
    : ATTRIBUTE_VALUE_LABELS[normalizedRaw] || rawText.replaceAll("_", " ");
  text = capitalizeTechnicalText(text);
  const normalized = text.toLocaleLowerCase("tr-TR");
  const numericValue = typeof value === "number" || /^\d/.test(text);
  if (numericValue && key === "guc_watt" && !normalized.includes("w")) return `${text} W`;
  if (numericValue && key === "hazne_litre" && !normalized.includes("l")) return `${text} L`;
  if (numericValue && key === "pil_suresi_saat" && !normalized.includes("saat")) return `${text} saat`;
  if (numericValue && key === "kalinlik_mm" && !normalized.includes("mm")) return `${text} mm`;
  if (numericValue && key === "uzunluk_cm" && !normalized.includes("cm")) return `${text} cm`;
  if (numericValue && key === "kapasite_mah" && !normalized.includes("mah")) return `${text} mAh`;
  if (numericValue && key === "warranty_months" && !normalized.includes("ay")) return `${text} ay`;
  return text;
}

function formatUnitText(value) {
  return String(value ?? "")
    .replace(/(\d+(?:[.,]\d+)?)\s*g\b/i, "$1 g")
    .replace(/(\d+(?:[.,]\d+)?)\s*kg\b/i, "$1 kg")
    .replace(/(\d+(?:[.,]\d+)?)\s*ml\b/i, "$1 ml")
    .replace(/(\d+(?:[.,]\d+)?)\s*l\b/i, "$1 L");
}

function attributeSentence(key, value) {
  const formattedValue = Array.isArray(value)
    ? value.map(item => attributeValue(key, item)).join(", ")
    : attributeValue(key, value);
  const normalizedValue = String(formattedValue).toLocaleLowerCase("tr-TR");
  if (key === "gramaj") return `Ürünün gramajı ${formatUnitText(formattedValue)} olarak belirtilmiştir.`;
  if (key === "form") return `${formattedValue} formda sunulur.`;
  if (key === "kafein") return normalizedValue === "var" ? "Kafein içerir." : "Kafein içermez.";
  if (key === "ogutum") return `${formattedValue} öğütüm derecesine sahiptir.`;
  if (key === "kavrulma") return `${formattedValue} kavrulmuştur.`;
  if (key === "adet") return `Paket ${formattedValue} parçadan oluşur.`;
  if (key === "malzeme") {
    if (normalizedValue === "kağıt") return "Tek kullanımlık filtre kağıdından üretilmiştir.";
    return `${formattedValue} malzeme kullanılmıştır.`;
  }
  if (key === "makinede_yikanabilir") return normalizedValue === "var" ? "Bulaşık makinesinde yıkanabilir." : "Bulaşık makinesinde yıkamaya uygun değildir.";
  if (key === "hacim_ml") return /^\d/.test(formattedValue) ? `${formattedValue} hacme sahiptir.` : `Hacim bilgisi ${formattedValue} olarak belirtilmiştir.`;
  if (key === "sicak_tutma_saat") return `İçeceği yaklaşık ${formattedValue} saat sıcak tutar.`;
  if (key === "kapasite_fincan") return `Tek kullanımda ${formattedValue} fincana kadar kahve hazırlayabilir.`;
  if (key === "guc_watt") return `${formattedValue} gücünde çalışır.`;
  if (key === "zamanlayici") return normalizedValue === "var" ? "Zamanlayıcı özelliği vardır." : "Zamanlayıcı özelliği yoktur.";
  if (key === "laptop_bolmesi") return normalizedValue === "var" ? "Laptop bölmesi bulunur." : "Laptop bölmesi bulunmaz.";
  if (key === "uyumlu_laptop_inch") return `${formattedValue} inç boyutuna kadar laptoplarla uyumludur.`;
  if (key === "hacim_litre") return `${formattedValue} L hacme sahiptir.`;
  if (key === "suya_dayanikli") return normalizedValue === "var" ? "Suya dayanıklı yapıdadır." : "Suya dayanıklı değildir.";
  if (key === "taban") return `Tabanında ${formattedValue} kullanılmıştır.`;
  if (key === "su_gecirmezlik") return `Su geçirgenliği için ${formattedValue} seviyesi belirtilmiştir.`;
  if (key === "numaralar") return `${formattedValue} numara seçenekleri mevcuttur.`;
  if (key === "bluetooth") return `Bluetooth ${formattedValue} bağlantısını destekler.`;
  if (key === "pil_suresi_saat") return `Yaklaşık ${formattedValue} kullanım süresi sunar.`;
  if (key === "mikrofon") return normalizedValue === "var" ? "Mikrofonu vardır." : "Mikrofonu yoktur.";
  if (key === "hiz_kademesi") return `${formattedValue} farklı hız kademesi vardır.`;
  if (key === "uyumlu_kullanim") {
    if (normalizedValue === "tek kullanımlık") return "Her demleme için yeni filtre kullanılması önerilir.";
    if (normalizedValue.includes("filtre kahve makinesi") && normalizedValue.includes("dripper")) return "Filtre kahve ve dripper kullanımı için uygundur.";
    return `${formattedValue} için uygundur.`;
  }
  if (key === "kapak_tipi") return `${formattedValue} kapak yapısına sahiptir.`;
  if (key === "kumas") return `${formattedValue} kumaş karışımı kullanılmıştır.`;
  if (key === "kalip") return `${formattedValue} kalıpla tasarlanmıştır.`;
  if (key === "renk") return `Renk seçeneği ${formattedValue}.`;
  if (key === "bedenler") return `${formattedValue} beden seçenekleri bulunur.`;
  if (key === "kalinlik_mm") return `${formattedValue} kalınlığındadır.`;
  if (key === "uzunluk_cm") return `${formattedValue} uzunluğundadır.`;
  if (key === "kaymaz_yuzey") return normalizedValue === "var" ? "Kaymaz yüzeye sahiptir." : "Kaymaz yüzey bilgisi yoktur.";
  if (key === "tasima_askisi") return normalizedValue === "var" ? "Taşıma askısı bulunur." : "Taşıma askısı bulunmaz.";
  if (key === "kapasite_mah") return `${formattedValue} kapasite sunar.`;
  if (key === "usb_c") return normalizedValue === "var" ? "USB-C bağlantısı vardır." : "USB-C bağlantısı yoktur.";
  if (key === "usb_a_port") return `${formattedValue} adet USB-A portu bulunur.`;
  if (key === "hizli_sarj") return normalizedValue === "var" ? "Hızlı şarjı destekler." : "Hızlı şarj desteği yoktur.";
  if (key === "paket") {
    if (normalizedValue === "100 adet filtre") return "Filtre kahve ve dripper kullanımı için uygundur.";
    return `Paket içeriği: ${formattedValue}.`;
  }
  if (key === "bakim") {
    if (/[.!?]$/.test(formattedValue) || formattedValue.toLocaleLowerCase("tr-TR").includes("yıkanabilir")) return ensureSentence(formattedValue);
    return `${formattedValue} önerilir.`;
  }
  if (key === "olcu") return `Ölçü bilgisi ${formattedValue} olarak belirtilmiştir.`;
  if (key === "isi_dayanimi") return `${formattedValue}.`;
  if (key === "giris_cikis") return `${formattedValue} yapılandırmasına sahiptir.`;
  if (key === "guvenlik") return `${formattedValue} sunar.`;
  if (key === "isik_modu") return `${formattedValue} modları için uygundur.`;
  if (key === "returnable") return normalizedValue === "var" ? "İade koşullarına uygundur." : "İade kapsamında değildir.";
  if (key === "return_policy_note") return ensureSentence(formattedValue);
  if (key === "warranty_months") return `Garanti süresi ${formattedValue}.`;
  if (key === "warranty_note") return ensureSentence(formattedValue);
  if (key === "baglanti") return `${formattedValue} bağlantı tipini kullanır.`;
  if (key === "dpi") return `${formattedValue} DPI hassasiyet sunar.`;
  if (key === "sessiz_tiklama") return normalizedValue === "var" ? "Sessiz tıklama özelliği vardır." : "Sessiz tıklama özelliği yoktur.";
  if (key === "pil_tipi") return `${formattedValue} pil ile çalışır.`;
  if (key === "baslik") return `${formattedValue} başlık tasarımına sahiptir.`;
  if (key === "renk_sicakligi") return `${formattedValue} ışık rengi sunar.`;
  return `${attributeLabel(key)} bilgisi ${formattedValue} olarak belirtilmiştir.`;
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

function orderStatusChips(order) {
  const labels = [
    demoStatusLabel(order.order_status),
    demoStatusLabel(order.payment_status),
    order.return_request ? demoStatusLabel(order.return_request.return_status) : demoStatusLabel(order.shipping_status)
  ].filter(Boolean);
  return [...new Set(labels)].slice(0, 3);
}

function returnStatusChips(item) {
  const labels = [
    refundStatusLabel(item.refund_status),
    item.return_request ? returnRequestLabel(item.return_request) : ""
  ].filter(Boolean);
  return [...new Set(labels)].slice(0, 3);
}

function supportSummaryCard(icon, title, text) {
  return `<article class="support-summary-card">
    <span class="support-summary-icon">${icon}</span>
    <div>
      <strong>${esc(title)}</strong>
      <p>${esc(text)}</p>
    </div>
  </article>`;
}

function supportPageShell({
  title,
  description,
  eyebrow = "AI Destek Platformu",
  summaries = [],
  cta = "",
  body = "",
  empty = "",
  note = "",
  className = "",
  metaBadge = "Copilot bağlamı aktif",
  metaTitle = "Kurumsal Destek Akışı",
  metaDescription = "Bu sayfadaki kayıtlar Copilot tarafından müşteri bağlamı olarak kullanılabilir.",
  secondaryAction = { page: "shop", label: "Mağazaya Git", icon: icons.box }
}) {
  return `
    <section class="support-page ${esc(className)}">
      <section class="support-page-hero card">
        <div class="support-page-hero-copy">
          <span class="hero-eyebrow">${esc(eyebrow)}</span>
          <h2>${esc(title)}</h2>
          <p>${esc(description)}</p>
          ${note ? `<div class="support-page-note">${esc(note)}</div>` : ""}
        </div>
        <div class="support-page-hero-meta">
          <div class="support-page-meta-copy">
            <span class="ai-pill"><span class="online"></span>${esc(metaBadge)}</span>
            <strong>${esc(metaTitle)}</strong>
            <p>${esc(metaDescription)}</p>
          </div>
          <div class="support-page-mini-cta">
            <button class="primary-button" data-action="toggle-copilot">${icons.bot} AI Copilot</button>
            <button data-page="${esc(secondaryAction.page)}">${secondaryAction.icon} ${esc(secondaryAction.label)}</button>
          </div>
        </div>
      </section>
      ${summaries.length ? `<section class="support-summary-grid">${summaries.join("")}</section>` : ""}
      ${cta ? `<section class="support-cta-band card">${cta}</section>` : ""}
      ${body}
      ${empty || ""}
    </section>`;
}

function ticketsPage(admin = false) {
  const items = admin ? state.adminTickets : state.tickets;
  if (!admin) {
    const activeCount = items.filter(item => ["OPEN", "PENDING", "IN_REVIEW"].includes(item.status)).length;
    const copilotCount = items.filter(item => item.source_message_id).length;
    const summaries = [
      supportSummaryCard(icons.ticket, "Toplam Talep", `${items.length} kayıt`),
      supportSummaryCard(icons.clock, "Açık / Bekleyen", `${activeCount} kayıt`),
      supportSummaryCard(icons.bot, "Copilot Kaynaklı", `${copilotCount} kayıt`)
    ];
    const body = items.length ? `
      <section class="support-main card">
        <div class="section-head"><div><h3>Destek Talebi Kayıtları</h3><small>Bu talepler Copilot’un çözemediği veya destek ekibine yönlendirdiği konular için oluşturulur.</small></div><span>${items.length} kayıt</span></div>
        <div class="support-ticket-grid">
          ${items.map(userTicketCard).join("")}
        </div>
      </section>` : "";
    const empty = items.length ? "" : `
      <section class="support-empty card">
        <div class="support-empty-icon">${icons.ticket}</div>
        <div class="support-empty-copy">
          <h3>Henüz destek talebiniz yok.</h3>
          <p>Copilot’un çözemediği durumlarda destek talebi oluşturabilir veya siz destek akışından talep açabilirsiniz.</p>
        </div>
        <div class="support-empty-actions">
          <button class="primary-button" data-action="toggle-copilot">${icons.bot} AI Copilot’u aç</button>
        </div>
      </section>`;
    return supportPageShell({
      title: "Destek Taleplerim",
      description: "Copilot tarafından açılan veya kullanıcı tarafından oluşturulan destek taleplerini buradan takip edebilirsiniz.",
      summaries,
      body,
      empty,
      className: "tickets-support-page",
      metaBadge: "Talep takibi aktif",
      metaTitle: "Destek Akışı",
      metaDescription: "Copilot gerekli durumlarda destek talebi oluşturabilir. Açılan talepler burada takip edilir.",
      secondaryAction: { page: "scenarios", label: "Senaryolar", icon: icons.star }
    });
  }
  return `${topbar(admin ? "Admin Destek Yönetimi" : "Destek taleplerim")}
    <section class="record-grid">${items.length ? items.map(item => `<article class="record-card ticket-card">
      <div class="ticket-card-header"><div><span class="ticket-number">Talep #${item.id}</span>
      <strong>${esc(item.department)}</strong></div>
      ${admin ? `<button class="edit-ticket" data-edit-ticket="${item.id}" aria-label="Destek talebini düzenle">${icons.edit}</button>` : ""}</div>
      <div class="ticket-meta"><span class="status-chip status-${item.status.toLowerCase()}">${esc(statusLabel(item.status))}</span>
      <time>${new Date(item.updated_at).toLocaleString("tr-TR")}</time></div>
      <div class="ticket-note user-ticket-note"><small>Kullanıcı açıklaması</small>
      <p>${esc(item.user_note || "Kullanıcı açıklama eklememiş.")}</p></div>
      ${item.admin_note ? `<div class="ticket-note admin-note"><small>Yönetici yanıtı</small><p>${esc(item.admin_note)}</p></div>` : ""}
      ${admin && state.editingTicketId === item.id ? `<div class="admin-ticket-actions"><select data-ticket-status="${item.id}">
        ${["OPEN", "IN_REVIEW", "RESOLVED"].map(status => `<option value="${status}" ${status === item.status ? "selected" : ""}>${statusLabel(status)}</option>`).join("")}
      </select><textarea data-ticket-note="${item.id}" maxlength="1000" placeholder="Yönetici kararını veya kullanıcıya iletilecek notu yazın"></textarea>
      <div><button data-cancel-ticket-edit="${item.id}">Vazgeç</button><button class="primary-button" data-update-ticket="${item.id}">Güncelle</button></div></div>` : ""}
    </article>`).join("") : "<p>Destek talebi bulunmuyor.</p>"}</section>`;
}

function ratingSelectHtml(name = "rating", value = 0) {
  return `<select class="review-select" name="${esc(name)}">
    ${["", 0, 1, 2, 3, 4, 5].map(option => {
      const optionValue = option === "" ? "" : String(option);
      const selected = optionValue === String(value ?? "");
      return `<option value="${optionValue}" ${selected ? "selected" : ""}>${option === "" ? "Puan ver" : `${option}/5`}</option>`;
    }).join("")}
  </select>`;
}

function productAttributesHtml(entries = []) {
  const itemEntries = Array.isArray(entries) ? entries : [];
  return `<div class="technical-grid">${itemEntries.map(entry => `
    <article class="technical-item">
      <span>${esc(entry.label)}</span>
      <strong>${esc(entry.value)}</strong>
      ${entry.sentence ? `<small>${esc(entry.sentence)}</small>` : ""}
    </article>
  `).join("")}</div>`;
}

function productTechHighlightsHtml(item, count = 4) {
  const entries = productTechSummaryEntries(item, count);
  return `<div class="tech-highlight-list">${entries.map(entry => `
    <div>
      <span>${esc(entry.label)}</span>
      <strong>${esc(entry.value)}</strong>
    </div>
  `).join("")}</div>`;
}

function productChatDataset(item, prompt) {
  return `data-action="chat-product" data-current-product-id="${item.id}" data-page-context="product" data-product-name="${esc(item.name)}" data-product-category="${esc(item.category)}" data-product-brand="${esc(item.brand || "")}" data-product-sku="${esc(item.sku || "")}" data-product-price="${esc(item.price)}" data-product-stock="${esc(item.stock)}" data-chat-prompt="${esc(prompt)}"`;
}

function sentenceCase(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed) return "";
  return trimmed.charAt(0).toLocaleUpperCase("tr-TR") + trimmed.slice(1);
}

function ensureSentence(text) {
  const normalized = sentenceCase(text).replace(/\s+/g, " ");
  if (!normalized) return "";
  return /[.!?]$/.test(normalized) ? normalized : `${normalized}.`;
}

function productPolicyHtml(item) {
  const returnText = item.return_policy_note
    || (item.returnable ? "Bu ürün iade koşullarına uygundur." : "Bu ürün iade kapsamında değildir.");
  const warrantyText = item.warranty_months
    ? `Garanti süresi ${item.warranty_months} aydır. ${item.warranty_note || ""}`
    : (item.warranty_note || "Garanti bilgisi bulunmamaktadır.");
  return `<p class="policy-summary">${esc([ensureSentence(returnText), ensureSentence(warrantyText)].filter(Boolean).join(" "))}</p>`;
}

function productStars(value) {
  const score = Number(value || 0);
  const full = Math.round(score);
  return `<span class="stars">${"★".repeat(full)}${"☆".repeat(Math.max(0, 5 - full))}</span>`;
}

function productCard(item) {
  const variant = productVariantLabel(item);
  return `<article class="product-card" data-product-open="${item.id}">
    ${productImageHtml(item)}
    <div class="product-info">
      <span class="product-category">${esc(productBadge(item.category))}</span>
      <h3>${esc(productDisplayName(item))}</h3>
      <p>${esc(item.brand || "")}${variant ? `<span>${esc(variant)}</span>` : ""}</p>
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
  const tab = state.productDetailTab || "overview";
  const variant = productVariantLabel(item);
  const technicalEntries = productTechnicalEntries(item);
  const technicalCount = technicalEntries.length;
  const ratingValue = item.rating_average ? Number(item.rating_average).toFixed(1) : "4.8";
  const primaryPrompt = `${item.name} ürünü hakkında destek almak istiyorum. Ürün kategorisi: ${productBadge(item.category)}, marka: ${item.brand || "-"}, fiyat: ${money(item.price)}.`;
  const descriptionHelper = technicalEntries.find(entry =>
    ["uyumlu_kullanim", "kapasite_mah", "hacim_ml", "olcu", "kumas"].includes(entry.key)
  ) || technicalEntries[0];
  return `<div class="modal-layer">
    <div class="modal-backdrop" data-action="close-product-detail"></div>
    <section class="card modal product-modal">
      <div class="product-modal-head">
        <div class="product-head-copy">
          <span class="product-category">${esc(productBadge(item.category))}</span>
          <h2>${esc(productDisplayName(item))}</h2>
          <p>${esc(item.brand)}${variant ? ` · ${esc(variant)}` : ""} · ${esc(item.sku)}</p>
          <div class="product-head-meta">
            <div class="rating-line">${productStars(item.rating_average)} <span>${esc(productRatingLabel(item))}</span></div>
            <span class="product-head-tag">${reviewCount ? `${reviewCount} yorum` : "Yorum yok"}</span>
            <span class="product-head-tag">${technicalCount} özellik</span>
          </div>
        </div>
        <div class="product-header-right">
          <div class="price-box">
            <strong>${money(item.price)}</strong>
            <small>Fiyat</small>
          </div>
          <span class="product-stock ${item.stock > 0 ? "in-stock" : "out-of-stock"}">${item.stock > 0 ? "Stokta var" : "Stok yok"}</span>
          <button class="modal-close" data-action="close-product-detail" aria-label="Kapat">${icons.close}</button>
        </div>
      </div>
      <div class="product-tabbar" role="tablist" aria-label="Ürün detay sekmeleri">
        <button type="button" class="${tab === "overview" ? "active" : ""}" data-product-tab="overview">Ürün Özeti</button>
        <button type="button" class="${tab === "technical" ? "active" : ""}" data-product-tab="technical">Teknik Bilgiler</button>
        <button type="button" class="${tab === "reviews" ? "active" : ""}" data-product-tab="reviews">Yorumlar</button>
        <button type="button" class="${tab === "ai" ? "active" : ""}" data-product-tab="ai">AI Destek</button>
      </div>
      <div class="product-modal-body">
        <div class="product-gallery">
          <div class="product-media card">
            ${productImageHtml(item, true)}
          </div>
          <div class="product-overview card">
            <div class="section-head"><h3>Ürün Özeti</h3><span>${esc(productBadge(item.category))}</span></div>
            <div class="product-kpi-grid">
              <div><span>Marka</span><strong>${esc(item.brand || "-")}</strong></div>
              <div><span>Puan</span><strong>${ratingValue}/5</strong></div>
              <div><span>Stok</span><strong>${item.stock}</strong></div>
              <div><span>SKU</span><strong>${esc(item.sku)}</strong></div>
            </div>
          </div>
          <div class="product-actions-panel card">
            <div class="section-head"><h3>Hızlı İşlemler</h3><span>Hızlı Erişim</span></div>
            <div class="modal-actions-row">
              <button class="primary-button" data-add-product="${item.id}">${icons.cart} Sepete Ekle</button>
              <button class="favorite-button" data-product-favorite="${item.id}">${item.is_favorited ? icons.heart : icons.heart} ${item.is_favorited ? "Favoriden Çıkar" : "Favoriye Ekle"}</button>
              <button class="copilot-action-button" ${productChatDataset(item, primaryPrompt)}>${icons.chat} Copilot’a Sor</button>
            </div>
          </div>
        </div>
        <div class="product-meta-panel">
          ${tab === "overview" ? `<section class="detail-panel product-description-panel">
            <div class="section-head"><h3>Ürün Açıklaması</h3><span>Genel Bakış</span></div>
            <p>${esc(item.description || "")}</p>
            ${descriptionHelper ? `<div class="description-helper"><span>${esc(descriptionHelper.label)}</span><strong>${esc(descriptionHelper.value)}</strong></div>` : ""}
          </section>
          <section class="detail-panel compact-panel">
            <div class="section-head"><h3>Öne Çıkan Teknik Özellikler</h3><span>${technicalCount} özellik</span></div>
            ${productTechHighlightsHtml(item, 6)}
          </section>` : ""}
          ${tab === "technical" ? `<section class="detail-panel">
            <div class="section-head"><h3>Teknik Bilgiler</h3><span>${technicalCount} özellik</span></div>
            ${productAttributesHtml(technicalEntries)}
          </section>` : ""}
          ${tab === "ai" ? `<section class="detail-panel">
            <div class="section-head"><h3>AI Destek</h3><span>Copilot</span></div>
            <p class="detail-copy">Copilot bu ürünün iade uygunluğu, teslimat, kupon geçerliliği ve ürün bilgileri için kaynaklı yanıt üretebilir.</p>
            <div class="copilot-suggestions compact">
              <button ${productChatDataset(item, `${item.name} ürünü iade edilebilir mi?`)}>${icons.chat} Bu ürün iade edilebilir mi?</button>
              <button ${productChatDataset(item, `${item.name} ürünü için kupon geçerli mi?`)}>${icons.bot} Bu ürün için kupon geçerli mi?</button>
              <button ${productChatDataset(item, `${item.name} teslimat sorunu yaşarsam ne yapmalıyım?`)}>${icons.chat} Teslimat sorunu yaşarsam ne yapmalıyım?</button>
            </div>
          </section>` : ""}
          ${tab === "reviews" ? `<section class="detail-panel">
            <div class="section-head"><h3>Yorumlar</h3><span>${reviewCount} kayıt</span></div>
            <div class="review-summary card">
              <strong>${ratingValue}/5</strong>
              <p>${reviewCount ? `${reviewCount} yorum üzerinden hesaplandı.` : "Henüz yorum yok."}</p>
            </div>
            <form class="review-form card" data-review-form="${item.id}">
              <div class="review-form-head">
                <label>Puan${ratingSelectHtml("rating", state.productDetailDraft?.rating || "")}</label>
                <span class="review-form-hint">İlk yorumu siz bırakın</span>
              </div>
              <input name="title" maxlength="255" placeholder="Yorum başlığı" value="${esc(state.productDetailDraft?.title || "")}">
              <textarea name="body" maxlength="2000" placeholder="Yorumunuz">${esc(state.productDetailDraft?.body || "")}</textarea>
              <button class="primary-button" type="submit">Yorumu gönder</button>
            </form>
            <div class="review-list">${(item.reviews || []).map(review => `
              <article class="review-card">
                <div class="review-card-head">
                  <div>
                    <strong>${esc(review.user_display_name)}</strong>
                    <small>${review.rating == null ? "Puan yok" : `${review.rating}/5`}</small>
                  </div>
                  <span class="status-chip">${review.rating == null ? "Yorum" : `Puan ${review.rating}`}</span>
                </div>
                <p><b>${esc(review.title || "")}</b></p>
                <p>${esc(review.body || "")}</p>
              </article>
            `).join("") || `<div class="empty-state product-empty-state">
              <div class="support-empty-icon">${icons.chat}</div>
              <div class="support-empty-copy">
                <h3>Henüz yorum yok</h3>
                <p>İlk yorumu siz bırakın. Ürün deneyiminizi puanlayarak diğer kullanıcılara yardımcı olabilirsiniz.</p>
              </div>
            </div>`}</div>
          </section>` : ""}
          <section class="detail-panel">
            <div class="section-head"><h3>İade ve Garanti</h3><span>Politika</span></div>
            ${productPolicyHtml(item)}
          </section>
        </div>
      </div>
    </section>
  </div>`;
}

function floatingCopilotButton() {
  return `<button class="floating-copilot" data-action="toggle-copilot" aria-label="AI Copilot'u aç" title="AI Copilot'u aç">${icons.bot}</button>`;
}

function copilotAnalysisCard() {
  const latest = latestAssistantMessage();
  const category = latest?.category ? supportCategoryLabel(latest.category) : "İade";
  const subcategory = latest?.sources?.[0]?.subcategory || "İade Talebi";
  const confidence = typeof latest?.confidence_score === "number" ? `%${Math.round(latest.confidence_score * 100)}` : "%94";
  const sourceCount = latest?.sources?.length || 2;
  const action = latest?.ticket_recommended ? "Destek talebi aç" : "RAG yanıtı";
  return `<section class="copilot-analysis card">
    <div class="section-head">
      <div><h3>Analiz Sonucu</h3><small>Örnek teknik çıktı</small></div>
      <span>Demo</span>
    </div>
    <div class="analysis-grid compact copilot-analysis-grid">
      <div class="analysis-item"><span>Kategori</span><strong>${esc(category)}</strong></div>
      <div class="analysis-item"><span>Alt kategori</span><strong>${esc(subcategory)}</strong></div>
      <div class="analysis-item"><span>Güven</span><strong>${esc(confidence)}</strong></div>
      <div class="analysis-item"><span>Kaynak</span><strong>${sourceCount} doküman</strong></div>
      <div class="analysis-item"><span>Aksiyon</span><strong>${esc(action)}</strong></div>
    </div>
  </section>`;
}

function copilotQuickQuestionsHtml() {
  const prompts = [
    "İade talebi nasıl oluşturulur?",
    "Siparişimi nasıl iptal ederim?",
    "Kargom teslim edildi görünüyor ama bana ulaşmadı.",
    "Kupon kodum geçersiz diyor.",
    "Kartımdan çekim oldu ama sipariş görünmüyor."
  ];
  return `<div class="copilot-quick-questions">${prompts.map(prompt => `
    <button type="button" data-chat-prompt="${esc(prompt)}">${esc(prompt)}</button>
  `).join("")}</div>`;
}

function copilotWelcomeHtml() {
  return `<div class="copilot-welcome">
    <div class="copilot-welcome-copy">
      <span class="ai-pill"><span class="online"></span>Canlı Demo</span>
      <span class="ai-pill ai-pill-ghost">RAG Destekli</span>
      <h2>Size nasıl yardımcı olabiliriz?</h2>
      <p>Sipariş, iade, ödeme, kargo ve kampanya konularında destek alabilirsiniz.</p>
    </div>
    ${copilotAnalysisCard()}
    <div class="copilot-welcome-section">
      <div class="section-head"><div><h3>Hızlı sorular</h3><small>Tek tıkla başlatın</small></div></div>
      ${copilotQuickQuestionsHtml()}
    </div>
  </div>`;
}

function copilotMessagesHtml() {
  if (!state.messages.length) {
    return copilotWelcomeHtml();
  }
  return messagesHtml();
}

function copilotDrawer() {
  if (!state.copilotOpen) return "";
  return `<aside class="copilot-drawer card">
    <div class="conversation-head">
      <div><span class="online"></span><strong>AI Destek Copilot</strong><small>Soruları analiz eder, kaynağı bulur, aksiyon önerir.</small></div>
      <button data-action="toggle-copilot">${icons.close}</button>
    </div>
    <div class="messages drawer-messages">${copilotMessagesHtml()}</div>
    <form class="message-form drawer-form" data-copilot-form>
      <textarea maxlength="1000" placeholder="Copilot'a sorunuzu yazın..." ${state.loading ? "disabled" : ""}></textarea>
      <button type="submit" ${state.loading ? "disabled" : ""}>${icons.send}</button>
    </form>
  </aside>`;
}

function shopPage() {
  const cart = state.cart;
  const items = filteredProducts();
  const categories = [...new Set(state.products.map(item => item.category))];
  return `${topbar("AI Destek Operasyon Merkezi", "Sipariş, iade, ödeme, kargo ve kampanya sorunlarını kaynaklara dayalı yanıtlayan demo destek platformu.")}
    <section class="commerce-layout ai-first-layout">
      <div class="shop-area">
        <div class="commerce-hero card ai-hero">
          <div class="hero-copy">
            <span class="hero-eyebrow">Teknopark Demo · AI First</span>
            <h2>AI Copilot ile Akıllı Müşteri Desteği</h2>
            <p>Senaryoyu hazırlayın, sorunuzu doğal dille yazın; Copilot kaynaklı yanıtı, kategori analizini ve gerekli aksiyonu birlikte sunsun.</p>
            <div class="hero-badges">
              <span>Kaynaklı Yanıt</span>
              <span>Kategori Analizi</span>
              <span>Aksiyon Önerisi</span>
            </div>
          </div>
        </div>
        ${usageFlowHtml()}
        ${systemMetricsHtml()}
        <section class="scenario-entry-card card">
          <span class="support-summary-icon">${icons.star}</span>
          <div>
            <strong>Demo verisini hazırlayın, soruyu Copilot’a kendiniz yazın.</strong>
            <p>Senaryolar sipariş, iade ve ödeme bağlamını hazırlar; destek sorusu yine kullanıcıdan gelir.</p>
          </div>
          <button data-page="scenarios">${icons.arrow} Senaryolara git</button>
        </section>
        <section class="catalog-head">
          <div>
            <span class="catalog-kicker">Demo Veri Katmanı</span>
            <h2>Ürün Kataloğu</h2>
            <p>Ürün, sipariş, iade ve kupon verileri Copilot yanıtlarında bağlam olarak kullanılır.</p>
          </div>
        </section>
        <div class="shop-toolbar card">
          <label class="search-field">${icons.search}<input value="${esc(state.productQuery)}" data-product-search placeholder="Ürün, marka, özellik veya etiket ara"></label>
          <select class="category-select" data-product-category>
            <option value="">Tüm kategoriler</option>
            ${categories.map(category => `<option value="${esc(category)}" ${state.productCategory === category ? "selected" : ""}>${esc(productBadge(category))}</option>`).join("")}
          </select>
          <button class="clear-filters-button" data-action="clear-product-filters">${icons.close} Filtreleri temizle</button>
        </div>
        <section class="product-grid">
          ${items.map(item => productCard(item)).join("") || "<p>Ürün bulunamadı.</p>"}
        </section>
        <section class="demo-state-head">
          <div>
            <h2>Demo Durumu</h2>
            <p>Sipariş, favori, iade ve sepet bilgileri burada görüntülenir. Copilot bu verileri destek bağlamı olarak kullanabilir.</p>
          </div>
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
        </section>
      </div>
      <aside class="support-rail">
        ${copilotRailHtml()}
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
      </aside>
    </section>`;
}

function favoritesPage() {
  const summaries = [
    supportSummaryCard(icons.heart, "Favori Ürünler", `${state.favorites.length} kayıt`),
    supportSummaryCard(icons.bot, "Copilot Bağlamı", "Karşılaştırma ve destek"),
    supportSummaryCard(icons.search, "Hızlı Erişim", "Detayları tek tıkla açın")
  ];
  const body = state.favorites.length ? `
    <section class="support-main card">
      <div class="section-head"><div><h3>Favori ürünler</h3><small>Favori ürünleriniz ürün karşılaştırma ve satın alma destek sorularında Copilot’a bağlam sağlar.</small></div><span>${state.favorites.length} kayıt</span></div>
      <div class="favorites-product-grid">
        ${state.favorites.map(item => `
          <article class="record-card favorite-card" data-product-open="${item.product.id}">
            <div class="favorite-card-header">
              <div>
                <span class="favorite-category">${esc(productBadge(item.product.category))}${item.product.brand ? ` · ${esc(item.product.brand)}` : ""}</span>
                <strong>${esc(item.product.name)}</strong>
              </div>
              <button class="favorite-remove-button" data-remove-favorite="${item.product.id}" aria-label="Favoriden çıkar" title="Favoriden çıkar">${icons.heart}</button>
            </div>
            <div class="favorite-card-meta">
              <strong>${money(item.product.price)}</strong>
              <span>${esc(productRatingLabel(item.product))}</span>
            </div>
            <p>${esc(item.product.description || "")}</p>
            <button class="favorite-detail-button" data-product-open="${item.product.id}">${icons.search} Detayı aç</button>
          </article>
        `).join("")}
      </div>
    </section>` : "";
  const empty = state.favorites.length ? "" : `
    <section class="support-empty card">
      <div class="support-empty-icon">${icons.heart}</div>
      <div class="support-empty-copy">
        <h3>Henüz favori ürününüz yok.</h3>
        <p>Mağazadan ürünleri favorilere ekleyerek burada görüntüleyebilirsiniz.</p>
      </div>
      <div class="support-empty-actions">
        <button class="primary-button" data-page="shop">${icons.box} Mağazaya git</button>
      </div>
    </section>`;
  return supportPageShell({
    title: "Favorilerim",
    description: "Favori ürünlerinizi inceleyin, karşılaştırın veya Copilot’a ürün tercihi bağlamı olarak kullanın.",
    summaries,
    body,
    empty,
    className: "favorites-support-page",
    metaBadge: "Copilot bağlamı aktif",
    metaTitle: "Favori Bağlamı",
    metaDescription: "Favori ürünleriniz ürün karşılaştırma, satın alma yönlendirmesi ve destek soruları için Copilot tarafından bağlam olarak kullanılabilir.",
    secondaryAction: { page: "shop", label: "Mağazaya git", icon: icons.box }
  });
}

function returnsPage() {
  const summaries = [
    supportSummaryCard(icons.ticket, "İade Talebi", `${state.returns.length} kayıt`),
    supportSummaryCard(icons.box, "İade Kodu", "Takip ve doğrulama"),
    supportSummaryCard(icons.chat, "Ödeme İadesi", "Tutar ve durum")
  ];
  const body = state.returns.length ? `
    <section class="support-main card">
      <div class="section-head"><div><h3>İade Kayıtları</h3><small>Bu kayıtlar iade uygunluğu, iade kodu ve ödeme iadesi sorularında Copilot tarafından bağlam olarak kullanılır.</small></div><span>${state.returns.length} kayıt</span></div>
      <div class="record-grid support-record-grid">
        ${state.returns.map(item => `
          <article class="record-card return-card">
            <div class="ticket-card-header">
              <div>
                <span class="ticket-number">${esc(item.return_code || "İade Kodu")}</span>
                <strong>${esc(item.product_name || item.order_no || `Sipariş #${item.order_id}`)}</strong>
                <span class="return-order-ref">${esc(item.order_no || `Sipariş #${item.order_id}`)}</span>
              </div>
              <span class="status-chip">${esc(returnStatusLabel(item.return_status))}</span>
            </div>
            <div class="status-row">
              ${returnStatusChips(item).map(label => `<span class="status-chip">${esc(label)}</span>`).join("")}
            </div>
            <p>${esc(shortText(item.return_reason || "İade açıklaması yok.", 120))}</p>
            <div class="return-meta-row">
              <small>İade durumu: ${esc(returnStatusLabel(item.return_status))}</small>
              <small>Ödeme iadesi: ${esc(refundStatusLabel(item.refund_status))}</small>
              ${item.refund ? `<small>İade tutarı: ${money(item.refund.refund_amount)}</small>` : ""}
            </div>
            <button class="return-chat-button" data-chat-prompt="${esc(`${item.return_code || "Bu iade kaydı"} için destek almak istiyorum. İade durumu: ${returnStatusLabel(item.return_status)}. İlgili sipariş: ${item.order_no || `Sipariş #${item.order_id}`}.`)}" data-current-order-id="${item.order_id}" data-current-return-id="${item.id}" data-page-context="returns">${icons.chat} Copilot'a sor</button>
          </article>
        `).join("")}
      </div>
    </section>` : "";
  const empty = state.returns.length ? "" : `
    <section class="support-empty card">
      <div class="support-empty-icon">${icons.ticket}</div>
      <div class="support-empty-copy">
        <h3>Henüz iade kaydı yok</h3>
        <p>Bir sipariş oluşturduktan sonra iade sürecini Copilot ile test edebilirsiniz. Copilot iade uygunluğu, iade kodu ve ödeme iadesi konularında kaynaklara dayalı yanıt üretir.</p>
      </div>
      <div class="support-empty-actions">
        <button class="primary-button" data-page="scenarios">${icons.star} Senaryolar</button>
        <button data-page="shop">${icons.box} Mağazaya git</button>
        <button data-action="toggle-copilot">${icons.bot} AI Copilot</button>
      </div>
    </section>`;
  return supportPageShell({
    title: "İadelerim",
    description: "Bu sayfadaki iade kayıtları Copilot için iade uygunluğu, iade kodu ve ödeme iadesi bağlamı oluşturur.",
    summaries,
    body,
    empty,
    className: "returns-support-page",
    metaTitle: "İade Bağlamı",
    metaDescription: "Bu sayfadaki iade kodu, iade durumu ve ödeme iadesi bilgileri Copilot tarafından destek bağlamı olarak kullanılabilir.",
    secondaryAction: { page: "scenarios", label: "Senaryolar", icon: icons.star }
  });
}

function ordersPage() {
  const summaries = [
    supportSummaryCard(icons.clock, "Aktif Sipariş", `${state.demoOrders.filter(item => !["CANCELLED"].includes(item.order_status)).length} kayıt`),
    supportSummaryCard(icons.box, "İptal Akışı", "İade ve iptal bağlamı"),
    supportSummaryCard(icons.search, "Kargo Takibi", "Teslimat durumu")
  ];
  const body = state.demoOrders.length ? `
    <section class="support-main card">
      <div class="section-head"><div><h3>Sipariş Kayıtları</h3><small>Bu kayıtlar iptal, kargo, teslimat ve iade sorularında Copilot tarafından bağlam olarak kullanılır.</small></div><span>${state.demoOrders.length} kayıt</span></div>
      <div class="order-grid support-order-grid">
        ${state.demoOrders.map(item => `<article class="order-card">
          <div class="order-card-head">
            <div><span class="ticket-number">${esc(item.order_no)}</span><h3>${orderProducts(item)}</h3></div>
            <div class="order-actions">
              <button class="icon-danger subtle-delete" data-delete-demo-order="${item.id}" data-admin="0" aria-label="Sipariş sil">${icons.trash}</button>
            </div>
          </div>
          <div class="status-row">
            ${orderStatusChips(item).map(label => `<span class="status-chip">${esc(label)}</span>`).join("")}
          </div>
          <div class="order-details">
            <div><small>Toplam</small><strong>${money(item.total)}</strong></div>
            <div><small>Kupon</small><strong>${esc(item.coupon_code || "Yok")}</strong></div>
            <div><small>Tarih</small><strong>${new Date(item.updated_at).toLocaleDateString("tr-TR")}</strong></div>
          </div>
          ${item.shipment ? `<div class="shipment-box compact-context"><small>${esc(item.shipment.carrier)}</small>
            <p>${item.shipment.tracking_number ? `Takip: ${esc(item.shipment.tracking_number)}` : "Takip numarası henüz yok."}</p>
            ${item.shipment.delay_reason || item.shipment.admin_note ? `<p>${esc(shortText(item.shipment.delay_reason || item.shipment.admin_note, 120))}</p>` : ""}</div>` : ""}
          <div class="order-flow-actions">
            ${item.return_request ? `<span class="status-chip">İade talebi açıldı</span>`
              : canRequestReturn(item) ? `<button class="primary-button" data-create-return="${item.id}">${icons.box} İade talebi oluştur</button>`
              : `<span class="status-chip">İade için uygun değil</span>`}
            <button data-chat-prompt="${esc(`${item.order_no} siparişimdeki ürün için iade süreci nasıl olur?`)}" data-current-order-id="${item.id}" data-current-return-id="${item.return_request?.id || ""}" data-page-context="orders">${icons.chat} Copilot'a sor</button>
          </div>
          ${item.return_request ? `<div class="shipment-box compact-context"><small>İade kodu: ${esc(item.return_request.return_code || "-")}</small>
            <p>${esc(item.return_request.return_status)} · ${esc(item.return_request.refund_status)}</p>
            <p>${esc(shortText(item.return_request.return_reason || "", 110))}</p>
            <button class="icon-button-small return-chat-button" data-chat-prompt="${esc(`${item.return_request.return_code} iade kodumla süreci nasıl takip ederim?`)}" data-current-order-id="${item.id}" data-current-return-id="${item.return_request.id}" data-page-context="returns">${icons.chat} Copilot'a sor</button></div>` : ""}
        </article>`).join("")}
      </div>
    </section>` : "";
  const empty = state.demoOrders.length ? "" : `
    <section class="support-empty card">
      <div class="support-empty-icon">${icons.clock}</div>
      <div class="support-empty-copy">
        <h3>Henüz demo sipariş yok</h3>
        <p>Mağazadan ürün ekleyip demo sipariş oluşturabilirsiniz. Copilot bu siparişleri iptal, kargo ve teslimat senaryolarında bağlam olarak kullanır.</p>
      </div>
      <div class="support-empty-actions">
        <button class="primary-button" data-page="shop">${icons.box} Mağazaya git</button>
        <button class="primary-button" data-page="scenarios">${icons.star} Sipariş iptali senaryosunu çalıştır</button>
        <button data-action="toggle-copilot">${icons.bot} AI Copilot</button>
      </div>
    </section>`;
  return supportPageShell({
    title: "Siparişlerim",
    description: "Bu sayfadaki siparişler iptal, kargo, teslimat ve iade sorularında Copilot için müşteri bağlamı oluşturur.",
    summaries,
    body,
    empty,
    className: "orders-support-page",
    metaTitle: "Sipariş Bağlamı",
    metaDescription: "Bu sayfadaki sipariş, kargo ve iade bilgileri Copilot tarafından destek bağlamı olarak kullanılabilir.",
    secondaryAction: { page: "scenarios", label: "Senaryolar", icon: icons.star }
  });
}

function scenarioPrepared(key) {
  return Boolean(state.scenarioStatuses.find(item => item.key === key)?.prepared);
}

function scenarioManagementCard(item) {
  const prepared = scenarioPrepared(item.key);
  return `<article class="scenario-management-card">
    <div class="scenario-card-head">
      <span class="scenario-area">${esc(item.area)}</span>
      <span class="scenario-status ${prepared ? "ready" : ""}">${prepared ? "Hazırlandı" : "Hazır değil"}</span>
    </div>
    <div class="scenario-card-copy">
      <h3>${esc(item.name)}</h3>
      <p>${esc(item.description)}</p>
    </div>
    <div class="scenario-card-meta">
      <span class="scenario-icon">${item.icon}</span>
      <small>Etkilenen alan: <strong>${esc(item.area)}</strong></small>
    </div>
    <div class="scenario-actions">
      <button class="scenario-primary" data-scenario-prepare="${esc(item.key)}">${icons.box} Senaryoyu Hazırla</button>
      <button class="scenario-secondary" data-scenario-clear="${esc(item.key)}">${icons.trash} Senaryoyu Temizle</button>
    </div>
  </article>`;
}

function scenariosPage() {
  const summaries = [
    supportSummaryCard(icons.star, "Demo Hazırlığı", "6 senaryo"),
    supportSummaryCard(icons.bot, "Manuel Soru", "Soruyu siz yazarsınız"),
    supportSummaryCard(icons.search, "Senaryo Sıfırlama", "Senaryo bazlı temizleme")
  ];
  const body = `
    <section class="scenario-info-box">
      ${icons.shield}
      <p>Bu sayfadaki butonlar yalnızca demo verisini hazırlar. Copilot’a otomatik soru gönderilmez.</p>
    </section>
    <section class="scenario-management-grid">
      ${DEMO_SCENARIOS.map(scenarioManagementCard).join("")}
    </section>`;
  return supportPageShell({
    title: "Demo Senaryoları",
    description: "Sunumda test edeceğiniz destek durumlarını hazırlayın, ardından Copilot’a kendi cümlenizle sorun.",
    summaries,
    body,
    className: "scenarios-support-page",
    metaBadge: "Demo akışı hazır",
    metaTitle: "Senaryo Bağlamı",
    metaDescription: "Hazırlanan senaryolar Copilot için destek bağlamı oluşturur. Senaryoyu hazırladıktan sonra soruyu manuel olarak yazabilirsiniz.",
    secondaryAction: { page: "shop", label: "Mağazaya git", icon: icons.box }
  });
}

function percent(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return `%${Math.round(Number(value) * 100)}`;
}

function shortText(value, length = 150) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}

function sourceSummary(sources = []) {
  if (!sources.length) return "Kaynak yok";
  return sources.slice(0, 2).map(source => source.title || source.doc_id || "Kaynak").join(", ");
}

function adminSection(id, title, description, count, body, kicker = "Demo Yönetimi") {
  return `<section class="admin-dashboard-section" id="${id}">
    <div class="admin-section-head">
      <div><span class="section-kicker">${esc(kicker)}</span><h3>${esc(title)}</h3><p>${esc(description)}</p></div>
      <span class="section-count">${esc(count)}</span>
    </div>
    ${body}
  </section>`;
}

function adminHumanJudgeSection() {
  if (state.adminFeedbackLoading) {
    return adminSection(
      "human-judge",
      "Human-as-a-Judge",
      "Kullanıcı feedbackleri üzerinden AI cevaplarının faydalı/faydasız bulunma durumunu analiz eder.",
      "Yükleniyor",
      `<div class="empty-state">AI Feedback analitiği yükleniyor.</div>`,
      "AI Feedback"
    );
  }
  if (state.adminFeedbackError) {
    return adminSection(
      "human-judge",
      "Human-as-a-Judge",
      "Kullanıcı feedbackleri üzerinden AI cevaplarının faydalı/faydasız bulunma durumunu analiz eder.",
      "Hata",
      `<div class="empty-state">
        <strong>Human-as-a-Judge verileri yüklenemedi.</strong>
        <p>Feedback analytics endpointi yanıt vermedi veya hata döndürdü.</p>
        <button class="primary-button" data-action="refresh-human-judge">Tekrar dene</button>
      </div>`,
      "AI Feedback"
    );
  }
  const data = state.adminFeedbackAnalytics;
  if (!data) {
    return adminSection(
      "human-judge",
      "Human-as-a-Judge",
      "Kullanıcı feedbackleri üzerinden AI cevaplarının faydalı/faydasız bulunma durumunu analiz eder.",
      "0 feedback",
      `<div class="empty-state">Henüz AI Feedback verisi yok. Kullanıcılar Copilot cevaplarına feedback verdiğinde burada görünecek.</div>`,
      "AI Feedback"
    );
  }
  const total = data.totalFeedback || 0;
  const categories = data.categoryBreakdown || [];
  const recent = data.recentFeedback || [];
  const maxCategoryTotal = Math.max(1, ...categories.map(item => item.total || 0));
  const body = total ? `<div class="admin-overview judge-overview">
      <article class="card metric-card"><span>Toplam Feedback</span><strong>${total}</strong><small>AI cevap oyu</small></article>
      <article class="card metric-card"><span>Helpful Oranı</span><strong>${percent(data.helpfulRate)}</strong><small>${data.helpfulCount || 0} olumlu</small></article>
      <article class="card metric-card"><span>Unhelpful Oranı</span><strong>${percent(data.unhelpfulRate)}</strong><small>${data.unhelpfulCount || 0} olumsuz</small></article>
      <article class="card metric-card"><span>Ortalama Confidence</span><strong>${data.averageConfidenceScore == null ? "—" : percent(data.averageConfidenceScore)}</strong><small>Model güven skoru</small></article>
    </div>
    <div class="judge-layout">
      <article class="admin-panel-card category-breakdown-panel">
        <div class="section-head"><h3>Kategori Dağılımı</h3><span>${categories.length} kategori</span></div>
        <div class="category-breakdown">${categories.map(item => {
          const helpfulWidth = Math.round(((item.helpful_count || 0) / maxCategoryTotal) * 100);
          const unhelpfulWidth = Math.round(((item.unhelpful_count || 0) / maxCategoryTotal) * 100);
          return `<div class="category-row">
            <div><strong>${esc(item.category || "GENEL")}</strong><span>${item.total} feedback · ${percent(item.helpful_rate)} helpful</span></div>
            <div class="stacked-bar" aria-label="${esc(item.category || "GENEL")} feedback dağılımı">
              <span class="bar-helpful" style="width:${helpfulWidth}%"></span>
              <span class="bar-unhelpful" style="width:${unhelpfulWidth}%"></span>
            </div>
            <small>${item.helpful_count || 0} helpful / ${item.unhelpful_count || 0} unhelpful</small>
          </div>`;
        }).join("") || `<div class="empty-state">Kategori dağılımı yok.</div>`}</div>
      </article>
      <article class="admin-panel-card recent-feedback-panel">
        <div class="section-head"><h3>Son Feedback Verilen AI Cevapları</h3><span>${recent.length} kayıt</span></div>
        <div class="feedback-list">${recent.map((item, index) => {
          const feedbackKey = `${item.messageId || index}-${item.feedbackCreatedAt || index}`;
          const feedbackComment = String(item.feedbackComment ?? "").trim();
          const commentOpen = Boolean(state.adminFeedbackCommentOpen[feedbackKey]);
          return `<article class="feedback-row">
          <div class="feedback-row-head">
            <strong>${esc(shortText(item.canonicalQuery || "Kullanıcı sorusu yok", 90))}</strong>
            <span class="feedback-row-actions">
              <span class="feedback-badge ${item.feedbackValue === "HELPFUL" ? "helpful" : "unhelpful"}">${esc(item.feedbackValue)}</span>
              ${feedbackComment ? `<span class="feedback-comment-chip">Yorum var</span>` : ""}
            </span>
          </div>
          <p>${esc(shortText(item.aiAnswer, 180))}</p>
          <div class="feedback-meta">
            <span class="status-chip">${esc(item.category || "GENEL")}</span>
            <span>Confidence: ${item.confidenceScore == null ? "—" : percent(item.confidenceScore)}</span>
            <span>${esc(sourceSummary(item.sources))}</span>
            <time>${item.feedbackCreatedAt ? new Date(item.feedbackCreatedAt).toLocaleString("tr-TR") : "Tarih yok"}</time>
          </div>
          ${feedbackComment ? `<button class="feedback-comment-toggle" data-feedback-comment-toggle="${esc(feedbackKey)}">${commentOpen ? "Geri bildirimi gizle" : "Geri bildirimi gör"}</button>` : `<small class="feedback-comment-muted">Yorum yok</small>`}
          ${feedbackComment && commentOpen ? `<div class="feedback-comment-box"><small>Kullanıcı geri bildirimi</small><p>${esc(feedbackComment)}</p></div>` : ""}
        </article>`;
        }).join("") || `<div class="empty-state">Henüz AI Feedback verisi yok. Kullanıcılar Copilot cevaplarına feedback verdiğinde burada görünecek.</div>`}</div>
      </article>
    </div>` : `<div class="empty-state">Henüz AI Feedback verisi yok. Kullanıcılar Copilot cevaplarına feedback verdiğinde burada görünecek.</div>`;
  return adminSection(
    "human-judge",
    "Human-as-a-Judge",
    "Kullanıcı feedbackleri üzerinden AI cevaplarının faydalı/faydasız bulunma durumunu analiz eder.",
    `${total} feedback`,
    body,
    "AI Feedback"
  );
}

function demoOrdersPage(admin = false) {
  const items = admin ? state.adminDemoOrders : state.demoOrders;
  if (!admin) {
    return `${topbar("Demo siparişlerim", "Sohbet asistanı bu sipariş durumlarını müşteri bağlamı olarak kullanır.")}
      <section class="order-grid">${orderCards(items, false)}</section>`;
  }
  const productsBody = `<div class="admin-two-column">
    <article class="admin-panel-card">
      <div class="section-head"><h3>Ürün Kataloğu</h3><span>${state.adminProducts.length} ürün</span></div>
      <p class="admin-section-note">Demo ürün verileri sipariş ve destek senaryolarına bağlam sağlar.</p>
      <div class="admin-compact-grid">${state.adminProducts.slice(0, 12).map(product => `<article class="admin-compact-card">
        <div><strong>${esc(product.name)}</strong><span class="status-chip">${esc(productBadge(product.category))}</span></div>
        <p>${esc(product.brand || "-")} · ${money(product.price)} · Stok: ${product.stock}</p>
        <small>${esc(productRatingLabel(product))}</small>
      </article>`).join("") || `<div class="empty-state">Ürün kaydı yok.</div>`}</div>
    </article>
    <article class="admin-panel-card">
      <div class="section-head"><h3>Ürün Yorumları</h3><span>${state.adminReviews.length} yorum</span></div>
      <p class="admin-section-note">Müşterilerin ürünlere verdiği puan ve yorumlar.</p>
      <div class="admin-compact-grid">${state.adminReviews.slice(0, 8).map(review => `<article class="admin-compact-card">
        <div><strong>${esc(review.product_name || `Ürün #${review.product_id}`)}</strong><span class="status-chip">${review.rating == null ? "Puan yok" : `${review.rating}/5`}</span></div>
        <p>${esc(review.title || "Başlık yok")}</p>
        <small>${esc(shortText(review.body || "Yorum metni yok.", 110))}</small>
      </article>`).join("") || `<div class="empty-state">Yorum kaydı yok.</div>`}</div>
    </article>
  </div>`;
  const ordersBody = `<div class="order-grid admin-order-grid">${orderCards(items, true)}</div>
    <article class="admin-panel-card">
      <div class="section-head"><h3>İade/Ödeme İadesi</h3><span>${state.adminReturns.length} kayıt</span></div>
      <p class="admin-section-note">Bu veriler Copilot’un ödeme, kupon ve iade sorularına bağlam sağlar.</p>
      <div class="admin-compact-grid">${state.adminReturns.map(item => `<article class="admin-compact-card">
        <div><strong>${esc(item.return_code || item.order_id)}</strong><span class="status-chip">${esc(returnStatusLabel(item.return_status))}</span></div>
        <p>${esc(item.return_reason || "İade nedeni yok.")}</p>
        <small>${esc(refundStatusLabel(item.refund_status))}${item.refund ? ` · ${money(item.refund.refund_amount)}` : ""}</small>
      </article>`).join("") || `<div class="empty-state">İade kaydı yok.</div>`}</div>
    </article>`;
  const financeBody = `<div class="admin-two-column">
    <article class="admin-panel-card">
      <div class="section-head"><h3>Kuponlar</h3><span>${state.adminCoupons.length} kayıt</span></div>
      <p class="admin-section-note">Bu veriler Copilot’un ödeme, kupon ve iade sorularına bağlam sağlar.</p>
      <div class="admin-compact-grid">${state.adminCoupons.map(coupon => `<article class="admin-compact-card">
        <div><strong>${esc(coupon.code)}</strong><span class="status-chip">${esc(demoStatusLabel(coupon.status))}</span></div>
        <p>${coupon.discount_type === "PERCENT" ? `%${coupon.discount_value}` : money(coupon.discount_value)} indirim · Min: ${money(coupon.min_cart_total)}</p>
        <small>Kategori: ${esc(coupon.allowed_category || "Tümü")}</small>
        <button class="icon-danger" data-delete-demo-coupon="${coupon.id}" aria-label="Kupon sil">${icons.trash} Sil</button>
      </article>`).join("") || `<div class="empty-state">Kupon kaydı yok.</div>`}</div>
    </article>
    <article class="admin-panel-card">
      <div class="section-head"><h3>Müşteri Finansal Bağlamı</h3><span>${state.adminWallets.length + state.adminCards.length + state.adminSecurityProfiles.length} kayıt</span></div>
      <p class="admin-section-note">Bu veriler Copilot’un ödeme, kart ve güvenlik sorularına bağlam sağlar.</p>
      <div class="finance-context-grid">
        <div><strong>Cüzdan</strong>${state.adminWallets.map(wallet => `<p>${wallet.user_id}: ${money(wallet.balance)} · ${esc(wallet.status)}</p>`).join("") || "<p>Cüzdan kaydı yok.</p>"}</div>
        <div><strong>Kartlar</strong>${state.adminCards.map(card => `<p>${card.user_id}: ${esc(card.card_brand)} ****${esc(card.last4)} ${card.is_default ? "(varsayılan)" : ""}</p>`).join("") || "<p>Kart kaydı yok.</p>"}</div>
        <div><strong>Güvenlik</strong>${state.adminSecurityProfiles.map(profile => `<p>${profile.user_id}: ${esc(demoStatusLabel(profile.security_status))} · ${esc(profile.risk_note || "")}</p>`).join("") || "<p>Güvenlik kaydı yok.</p>"}</div>
      </div>
    </article>
  </div>`;
  const adminReturnCount = state.adminReturns.length || state.adminDemoOrders.filter(item => item.return_request).length;
  return `${topbar("Demo Yönetim Paneli", "Ürün, sipariş, iade, kupon ve müşteri bağlamı verilerini demo amaçlı yönetin.")}
    <section class="admin-overview">
      <article class="card metric-card"><span>Ürün</span><strong>${state.adminProducts.length}</strong><small>Katalog Verisi</small></article>
      <article class="card metric-card"><span>Yorum</span><strong>${state.adminReviews.length}</strong><small>Ürün Feedbackleri</small></article>
      <article class="card metric-card"><span>Sipariş</span><strong>${state.adminDemoOrders.length}</strong><small>Demo Akışları</small></article>
      <article class="card metric-card"><span>İade</span><strong>${adminReturnCount}</strong><small>İade Ve Ödeme</small></article>
    </section>
    <nav class="admin-section-nav" aria-label="Yönetim paneli bölümleri">
      <a href="#products-reviews">Ürün & Yorum</a>
      <a href="#orders-returns">Sipariş & İade</a>
      <a href="#coupons-finance">Kupon & Ödeme</a>
      <a href="#human-judge">Human-as-a-Judge</a>
    </nav>
    ${adminSection("products-reviews", "Ürün Ve Yorum Yönetimi", "Ürün kataloğu ile ürün yorumlarını ayrı ve kompakt bir alanda izleyin.", `${state.adminProducts.length} ürün / ${state.adminReviews.length} yorum`, productsBody)}
    ${adminSection("orders-returns", "Sipariş Ve İade Yönetimi", "Demo siparişleri, iade durumlarını ve Copilot bağlamını yönetin.", `${state.adminDemoOrders.length} sipariş / ${adminReturnCount} iade`, ordersBody)}
    ${adminSection("coupons-finance", "Kupon Ve Ödeme Bağlamı", "Kupon, cüzdan, kart ve güvenlik kayıtlarını destek bağlamı olarak izleyin.", `${state.adminCoupons.length} kupon`, financeBody)}
    ${adminHumanJudgeSection()}`;
}

function orderCards(items, admin = false) {
  return items.map(item => `<article class="order-card admin-order-card">
    <div class="order-card-head">
      <div><span class="ticket-number">${esc(item.order_no)}</span><h3>${orderProducts(item)}</h3></div>
      <div class="order-actions">
        ${admin ? `<button class="icon-button-small" data-edit-demo-order="${item.id}" aria-label="Sipariş düzenle">${icons.edit}</button>` : ""}
        <button class="icon-danger" data-delete-demo-order="${item.id}" data-admin="${admin ? "1" : "0"}" aria-label="Sipariş sil">${icons.trash}</button>
      </div>
    </div>
    <div class="status-row admin-status-row">
      ${statusBadges([demoStatusLabel(item.order_status), demoStatusLabel(item.payment_status), demoStatusLabel(item.shipping_status)])}
    </div>
    <div class="order-details">
      <div><small>Toplam</small><strong>${money(item.total)}</strong></div>
      <div><small>Kupon</small><strong>${esc(item.coupon_code || "Yok")}</strong></div>
      <div><small>Tarih</small><strong>${new Date(item.updated_at).toLocaleDateString("tr-TR")}</strong></div>
    </div>
    ${item.shipment ? `<div class="shipment-box compact-context"><small>${esc(item.shipment.carrier)}</small>
      <p>${item.shipment.tracking_number ? `Takip: ${esc(item.shipment.tracking_number)}` : "Takip numarası henüz yok."}</p>
      ${item.shipment.delay_reason || item.shipment.admin_note ? `<p>${esc(shortText(item.shipment.delay_reason || item.shipment.admin_note, 120))}</p>` : ""}</div>` : ""}
    ${item.return_request ? `<div class="shipment-box compact-context"><small>İade kodu: ${esc(item.return_request.return_code || "-")}</small>
      <p>${esc(returnRequestLabel(item.return_request.return_request || item.return_request.return_status))} · ${esc(refundStatusLabel(item.return_request.refund_status))}</p>
      <p>${esc(shortText(item.return_request.return_reason || "", 110))}</p>
      <button class="icon-button-small return-chat-button" data-chat-prompt="${esc(`${item.return_request.return_code} iade kodumla süreci nasıl takip ederim?`)}" data-current-order-id="${item.id}" data-current-return-id="${item.return_request.id}" data-page-context="returns">${icons.chat} Copilot'a sor</button></div>` : ""}
    <div class="order-flow-actions admin-order-actions">
      ${item.return_request ? `<span class="status-chip">İade talebi açıldı</span>`
        : canRequestReturn(item) ? `<button class="primary-button" data-create-return="${item.id}">${icons.box} İade talebi oluştur</button>`
        : `<span class="status-chip">İade için uygun değil</span>`}
      <button data-chat-prompt="${esc(`${item.order_no} siparişimdeki ürün için iade süreci nasıl olur?`)}" data-current-order-id="${item.id}" data-current-return-id="${item.return_request?.id || ""}" data-page-context="orders">${icons.chat} Copilot'a sor</button>
    </div>
    ${item.admin_note ? `<div class="ticket-note admin-note"><small>Yönetici notu</small><p>${esc(shortText(item.admin_note, 130))}</p></div>` : ""}
    ${admin && state.editingDemoOrderId === item.id ? `<div class="admin-demo-editor">
      <label>Sipariş durumu<select data-demo-order-status="${item.id}">${["CREATED", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED", "REFUND_PENDING"].map(status => `<option value="${status}" ${status === item.order_status ? "selected" : ""}>${demoStatusLabel(status)}</option>`).join("")}</select></label>
      <label>Ödeme durumu<select data-demo-payment-status="${item.id}">${["SUCCESS", "FAILED", "CAPTURED_NO_ORDER", "REFUND_PENDING"].map(status => `<option value="${status}" ${status === item.payment_status ? "selected" : ""}>${demoStatusLabel(status)}</option>`).join("")}</select></label>
      <label>Kargo durumu<select data-demo-shipping-status="${item.id}">${["PREPARING", "SHIPPED", "IN_TRANSIT", "DELAYED", "LOST", "DELIVERED", "PARTIALLY_DELIVERED"].map(status => `<option value="${status}" ${status === item.shipping_status ? "selected" : ""}>${demoStatusLabel(status)}</option>`).join("")}</select></label>
      <label>Takip no<input data-demo-tracking="${item.id}" placeholder="TRK..." value="${esc(item.shipment?.tracking_number || "")}"></label>
      <label class="full-field">Yönetici notu<textarea data-demo-note="${item.id}" maxlength="1000" placeholder="Gecikme nedeni veya yönetici notu">${esc(item.admin_note || item.shipment?.delay_reason || "")}</textarea></label>
      <div class="editor-actions"><button data-cancel-demo-edit="${item.id}">Vazgeç</button><button class="primary-button" data-update-demo-order="${item.id}">Güncelle</button></div>
    </div>` : ""}
  </article>`).join("") || `<div class="empty-state">Demo sipariş bulunmuyor.</div>`;
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
  const feedbackOnly = state.ticketModal.mode === "feedback";
  return `<div class="modal-layer"><div class="modal-backdrop" data-action="close-modal"></div>
    <section class="card modal ticket-modal">
      <div class="ticket-modal-line ticket-modal-title">${feedbackOnly ? "Olumsuz geri bildirim" : "Manuel destek talebi"}</div>
      <div class="ticket-modal-line ticket-modal-copy">${directTicket ? "Bu cevapla ilgili destek ekibine doğrudan destek talebi gönderebilirsiniz." : "Yanıt sorununuzu çözmediyse ilgili destek ekibine destek talebi gönderebilirsiniz."}</div>
      <textarea maxlength="1000" data-ticket-modal-note placeholder="${feedbackOnly ? "Neden işinize yaramadı?" : "Sorunu kısaca açıklayın"}"></textarea>
      <div class="modal-actions"><button data-action="close-modal">Şimdilik kapat</button>
      <button class="primary-button" data-action="submit-ticket">${directTicket ? "Destek talebi aç" : "Geri bildirim ver ve destek talebi aç"}</button></div>
      ${directTicket ? "" : `<button class="text-button" data-action="feedback-only">Yalnızca olumsuz geri bildirim ver</button>`}
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
    : state.page === "orders" ? ordersPage()
    : state.page === "scenarios" ? scenariosPage()
    : state.page === "tickets" ? ticketsPage(false)
    : state.page === "admin-demo" ? demoOrdersPage(true)
    : ticketsPage(true);
  document.querySelector("#app").innerHTML =
    `<div class="app-shell ${state.theme === "dark" ? "dark" : ""}">${sidebar()}<main class="main-content">${content}</main>${state.copilotOpen ? '<div class="copilot-backdrop" data-action="toggle-copilot"></div>' : ""}${state.copilotOpen ? "" : floatingCopilotButton()}${copilotDrawer()}${productDetailModal()}${ticketModal()}${sourceModal()}</div>`;
  bind();
  requestAnimationFrame(() => {
    const messages = document.querySelector(".messages");
    if (messages && state.messages.length) messages.scrollTop = messages.scrollHeight;
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

function positiveId(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : undefined;
}

function activeChatContext(extra = {}) {
  const base = {
    page_context: state.productDetail ? "product" : state.page,
    current_product_id: state.productDetail?.id,
    current_cart_id: state.page === "shop" ? state.cart?.id : undefined
  };
  return Object.fromEntries(
    Object.entries({ ...base, ...extra }).filter(([, value]) =>
      value !== undefined && value !== null && value !== ""
    )
  );
}

function chatContextFromDataset(dataset) {
  return activeChatContext({
    current_product_id: positiveId(dataset.currentProductId),
    current_order_id: positiveId(dataset.currentOrderId),
    current_cart_id: positiveId(dataset.currentCartId),
    current_return_id: positiveId(dataset.currentReturnId),
    current_payment_id: positiveId(dataset.currentPaymentId),
    page_context: dataset.pageContext
  });
}

async function sendMessage(text, context = {}) {
  const content = text.trim();
  if (!content || state.loading) return;
  state.messages.push({ role: "USER", content });
  state.loading = true;
  render();
  const contextPromise = refreshContext(content);
  try {
    const id = await ensureConversation();
    const result = await api(`${API}/conversations/${id}/messages`, {
      method: "POST", body: JSON.stringify({ message: content, ...activeChatContext(context) })
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
    if (page === "scenarios") {
      state.scenarioStatuses = await api(`${API}/demo/scenarios`);
      state.cart = await api(`${API}/demo/cart`);
      state.returns = await api(`${API}/demo/returns`);
      state.demoOrders = await api(`${API}/demo/orders`);
    }
    if (page === "tickets") state.tickets = await api(`${API}/tickets`);
    if (page === "admin") state.adminTickets = await api(`${API}/admin/tickets`);
    if (page === "admin-demo") {
      state.adminFeedbackAnalytics = null;
      state.adminFeedbackError = "";
      refreshAdminFeedbackAnalytics();
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

async function refreshAdminFeedbackAnalytics() {
  if (!state.user?.is_admin) return;
  state.adminFeedbackLoading = true;
  state.adminFeedbackError = "";
  render();
  try {
    const result = await api(ADMIN_FEEDBACK_ANALYTICS_ENDPOINT);
    state.adminFeedbackAnalytics = normalizeAdminFeedbackAnalytics(result);
  } catch (error) {
    state.adminFeedbackAnalytics = null;
    state.adminFeedbackError = error.message;
    toast(error.message);
  } finally {
    state.adminFeedbackLoading = false;
    render();
  }
}

async function loadConversation(id) {
  const result = await api(`${API}/conversations/${id}`);
  state.conversationId = result.id;
  state.messages = result.messages;
  state.page = "shop";
  state.copilotOpen = true;
  render();
}

async function submitFeedback(id, value, openTicket = false, note = "", comment = "") {
  const result = await api(`${API}/messages/${id}/feedback`, {
    method: "POST", body: JSON.stringify({
      value,
      open_ticket: openTicket,
      note,
      comment: comment || note
    })
  });
  state.messages = state.messages.map(item =>
    item.id === Number(id) ? { ...item, user_feedback: value } : item
  );
  toast(result.ticket_id ? `Destek talebi #${result.ticket_id} oluşturuldu.` : result.status);
  await refreshAdminFeedbackAnalytics();
  render();
}

async function createTicket(id, note = "") {
  const result = await api(`${API}/messages/${id}/ticket`, {
    method: "POST", body: JSON.stringify({ note })
  });
  toast(`Destek talebi #${result.id} oluşturuldu.`);
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
  state.productDetailTab = "overview";
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
  document.querySelectorAll(".message-form").forEach(form => {
    form.addEventListener("submit", event => {
      event.preventDefault();
      const textarea = event.currentTarget.querySelector("textarea");
      const value = textarea.value;
      textarea.value = "";
      sendMessage(value);
    });
  });
  document.querySelectorAll(".message-form textarea").forEach(textarea => {
    textarea.addEventListener("keydown", event => {
      if (event.isComposing || event.key !== "Enter" || event.shiftKey) return;
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    });
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
      if (node.dataset.action === "chat-product") return;
      event.stopPropagation();
      state.copilotOpen = true;
      await sendMessage(node.dataset.chatPrompt, chatContextFromDataset(node.dataset));
    }));
  document.querySelector("[data-action='open-support-ticket']")?.addEventListener("click", () => {
    const latest = latestAssistantMessage();
    if (!latest?.id) {
      toast("Önce bir Copilot yanıtı üretin.");
      return;
    }
    state.ticketModal = { messageId: latest.id, mode: "direct" };
    render();
  });
  document.querySelector("[data-action='logout']")?.addEventListener("click", async () => {
    await api("/auth/logout", { method: "POST" }); location.reload();
  });
  document.querySelector("[data-action='refresh-human-judge']")?.addEventListener("click", async () => {
    await refreshAdminFeedbackAnalytics();
  });
  document.querySelector("[data-action='theme']")?.addEventListener("click", () => {
    state.theme = state.theme === "dark" ? "light" : "dark";
    localStorage.setItem("destekai-theme", state.theme); render();
  });
  document.querySelectorAll("[data-product-open]").forEach(node =>
    node.addEventListener("click", event => {
      if (node.tagName === "BUTTON") event.stopPropagation();
      openProductDetail(node.dataset.productOpen);
    }));
  document.querySelectorAll("[data-action='toggle-copilot']").forEach(node =>
    node.addEventListener("click", () => {
      state.copilotOpen = !state.copilotOpen;
      render();
    }));
  document.querySelectorAll("[data-action='close-product-detail']").forEach(node =>
    node.addEventListener("click", () => {
      state.productDetail = null;
      state.productDetailTab = "overview";
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
  document.querySelectorAll("[data-product-tab]").forEach(node =>
    node.addEventListener("click", () => {
      state.productDetailTab = node.dataset.productTab;
      render();
    }));
  document.querySelectorAll("[data-remove-favorite]").forEach(node =>
    node.addEventListener("click", event => {
      event.stopPropagation();
      removeFavorite(node.dataset.removeFavorite);
    }));
  document.querySelectorAll("[data-review-form]").forEach(node =>
    node.addEventListener("submit", event => {
      event.preventDefault();
      submitProductReview(node.dataset.reviewForm, event.currentTarget);
    }));
  document.querySelectorAll("[data-action='chat-product']").forEach(node =>
    node.addEventListener("click", async event => {
      event.stopPropagation();
      const prompt = node.dataset.chatPrompt;
      if (!prompt) return;
      state.productDetail = null;
      state.productDetailTab = "overview";
      state.productDetailDraft = { rating: "", title: "", body: "" };
      state.copilotOpen = true;
      await sendMessage(prompt, chatContextFromDataset(node.dataset));
    }));
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
    const id = state.ticketModal.messageId;
    const comment = document.querySelector("[data-ticket-modal-note]").value;
    state.ticketModal = null;
    await submitFeedback(id, "UNHELPFUL", false, "", comment); render();
  });
  document.querySelector("[data-action='submit-ticket']")?.addEventListener("click", async () => {
    const id = state.ticketModal.messageId;
    const mode = state.ticketModal.mode;
    const note = document.querySelector("[data-ticket-modal-note]").value;
    state.ticketModal = null;
    if (mode === "direct") await createTicket(id, note);
    else await submitFeedback(id, "UNHELPFUL", true, note, note);
    render();
  });
  document.querySelectorAll("[data-feedback-comment-toggle]").forEach(node =>
    node.addEventListener("click", () => {
      const key = node.dataset.feedbackCommentToggle;
      state.adminFeedbackCommentOpen[key] = !state.adminFeedbackCommentOpen[key];
      render();
    }));
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
    await loadPage("admin"); toast("Destek talebi güncellendi.");
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
  document.querySelectorAll("[data-scenario-prepare]").forEach(node => node.addEventListener("click", async () => {
    const result = await api(`${API}/demo/scenarios/${node.dataset.scenarioPrepare}/prepare`, { method: "POST" });
    toast(result.status);
    await loadPage("scenarios");
  }));
  document.querySelectorAll("[data-scenario-clear]").forEach(node => node.addEventListener("click", async () => {
    const result = await api(`${API}/demo/scenarios/${node.dataset.scenarioClear}/clear`, { method: "POST" });
    toast(result.status);
    await loadPage("scenarios");
  }));
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

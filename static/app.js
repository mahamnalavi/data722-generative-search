/* Sahulat Home demo store: the website.
 *
 * Pages (hash-based, so it all runs from one HTML file):
 *   #/                        home
 *   #/c/<Category>            category page
 *   #/p/<product_id>          product page
 *   #/search?q=..&from=..     search results
 *
 * "This visit" tracking lives in sessionStorage (this tab only; cleared when
 * the tab closes). Only a coarse summary is sent with a search: page category,
 * categories and product types viewed, and price range. Never IDs.
 */
(() => {
  "use strict";

  const CATEGORIES = ["Kitchenware", "Tools", "Organizers", "Furniture"];
  const CAT_BLURB = {
    Kitchenware: "Cookware, prep tools, baking and storage jars",
    Tools: "Hand and power tools, plumbing, electrical, ladders",
    Organizers: "Kitchen, wardrobe, bathroom and desk storage",
    Furniture: "Seating, tables, desks and storage furniture",
  };
  const ICONS = {
    Kitchenware: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 10h16v3a7 7 0 0 1-7 7h-2a7 7 0 0 1-7-7z"/><path d="M2 10h2M20 10h2M9 6c0-1 1-1.5 1-2.5M13 6c0-1 1-1.5 1-2.5"/></svg>',
    Tools: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14.5 5.5a4 4 0 0 0 4.9 5L21 12l-8.5 8.5a2.1 2.1 0 0 1-3-3L18 9l1.5-1.5"/><path d="M14.5 5.5 12 3 3 12l2.5 2.5"/></svg>',
    Organizers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="1.5"/><path d="M3 12h18M10 8h4M10 16h4"/></svg>',
    Furniture: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 11V5a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6"/><path d="M4 11h16v4H4zM6 15v5M18 15v5"/></svg>',
  };
  const EXAMPLES = [
    "something to separate egg whites from yolks",
    "pyaz barik katne wali cheez",
    "shelves for a small bathroom, no drilling",
    "light for load shedding under Rs 1500",
  ];

  const main = document.getElementById("main");
  const topForm = document.getElementById("top-search");
  const topQ = document.getElementById("top-q");
  const FEATURED_TYPES = ["egg_separator", "pressure_cooker", "emergency_light", "cordless_drill",
    "shower_caddy", "spice_rack", "office_chair", "prayer_chair"];
  let products = [];
  let byId = {};

  // ---------- helpers ----------
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const rs = (n) => "Rs " + Number(n).toLocaleString("en-PK");
  const stockLabel = (p) =>
    p.stock_qty === 0 ? '<span class="stock out">Out of stock</span>'
      : p.stock_qty <= 5 ? `<span class="stock low">Only ${p.stock_qty} left</span>`
      : '<span class="stock">In stock</span>';

  // AI-generated product photos (fictional products; labelled in the footer). Others keep their illustration.
  const PHOTOS = new Set(["FUR-012", "FUR-032", "FUR-036", "KIT-001", "KIT-003", "KIT-017", "KIT-020", "KIT-021", "KIT-022", "KIT-026", "KIT-046", "KIT-049", "KIT-053", "KIT-057", "ORG-005", "ORG-013", "ORG-023", "TOL-004", "TOL-016", "TOL-018", "TOL-026", "TOL-027"]);
  const art = (p) => PHOTOS.has(p.product_id)
    ? `<img src="/static/img/products/${esc(p.product_id)}.webp" alt="${esc(p.title)}" loading="lazy">`
    : (window.illustrationFor && window.illustrationFor(p)) || ICONS[p.category] || "";

  function card(p) {
    return `<a class="card" href="#/p/${esc(p.product_id)}">
      <div class="thumb t-${esc(p.category)}">${art(p)}</div>
      <div class="card-body">
        <span class="card-title">${esc(p.title)}</span>
        <span class="card-brand">${esc(p.brand)}</span>
        <div class="card-foot"><span class="price">${rs(p.price_pkr)}</span>${stockLabel(p)}</div>
      </div></a>`;
  }

  // ---------- this-visit memory (sessionStorage, wrapped in try/catch) ----------
  const KEY = "sahulat_visit_v1";
  let memoryFallback = { pages: [], viewed: [], searches: [] };
  function loadVisit() {
    try { return JSON.parse(sessionStorage.getItem(KEY)) || { pages: [], viewed: [], searches: [] }; }
    catch { return memoryFallback; }
  }
  function saveVisit(v) {
    memoryFallback = v;
    try { sessionStorage.setItem(KEY, JSON.stringify(v)); } catch { /* storage blocked: keep in memory */ }
    document.getElementById("visit-count").textContent = v.pages.length + v.viewed.length + v.searches.length;
  }
  function track(kind, item) {
    const v = loadVisit();
    const list = v[kind];
    const last = list[list.length - 1];
    if (last && JSON.stringify({ ...last, ts: 0 }) === JSON.stringify({ ...item, ts: 0 })) return; // ignore reloads
    list.push({ ...item, ts: Date.now() });
    if (list.length > 30) list.shift();
    saveVisit(v);
  }

  /** The only behavioural data that leaves the browser: a coarse summary. */
  function visitSummary(fromCategory) {
    const v = loadVisit();
    const catCounts = {};
    v.pages.forEach((p) => { catCounts[p.category] = (catCounts[p.category] || 0) + 1; });
    v.viewed.forEach((p) => { catCounts[p.category] = (catCounts[p.category] || 0) + 1; });
    const prices = v.viewed.map((p) => p.price).sort((a, b) => a - b);
    return {
      page_category: fromCategory || null,
      categories_browsed: catCounts,
      product_types_viewed: [...new Set(v.viewed.slice(-10).map((p) => p.type))],
      price_band: prices.length ? { min: prices[0], max: prices[prices.length - 1], median: prices[Math.floor(prices.length / 2)] } : null,
      recent_searches: v.searches.slice(-3).map((s) => s.q),
    };
  }

  function renderVisitPanel() {
    const v = loadVisit();
    const s = visitSummary(null);
    const body = document.getElementById("visit-body");
    const cats = Object.entries(s.categories_browsed);
    body.innerHTML = `
      <div class="vp-section"><h3>Categories looked at</h3>${cats.length ? `<ul>${cats.map(([c, n]) => `<li>${esc(c)}: ${n} ${n === 1 ? "page" : "pages"}</li>`).join("")}</ul>` : '<p class="vp-empty">None yet.</p>'}</div>
      <div class="vp-section"><h3>Products viewed</h3>${v.viewed.length ? `<ul>${v.viewed.slice(-8).reverse().map((p) => `<li>${esc(byId[p.id]?.title || p.type)} (${rs(p.price)})</li>`).join("")}</ul>` : '<p class="vp-empty">None yet.</p>'}</div>
      <div class="vp-section"><h3>Price range of products viewed</h3>${s.price_band ? `<p>${rs(s.price_band.min)} to ${rs(s.price_band.max)}</p>` : '<p class="vp-empty">Not enough to tell yet.</p>'}</div>
      <div class="vp-section"><h3>Searches</h3>${v.searches.length ? `<ul>${v.searches.slice(-5).reverse().map((x) => `<li>${esc(x.q)}</li>`).join("")}</ul>` : '<p class="vp-empty">None yet.</p>'}</div>
      <div class="vp-section"><h3>Sent with your next search or chat message</h3><p class="vp-empty">The page you're on, the categories and product types above, and the price range. Search uses them to order results slightly. They never override what you type, and never bring back items outside your budget.</p></div>`;
  }

  const panel = document.getElementById("visit-panel");
  const scrim = document.getElementById("scrim");
  const visitBtn = document.getElementById("visit-btn");
  function openPanel() { renderVisitPanel(); panel.hidden = false; scrim.hidden = false; document.getElementById("visit-close").focus(); }
  function closePanel() { panel.hidden = true; scrim.hidden = true; visitBtn.focus(); }
  visitBtn.addEventListener("click", openPanel);
  document.getElementById("visit-close").addEventListener("click", closePanel);
  scrim.addEventListener("click", closePanel);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) closePanel(); });
  document.getElementById("visit-clear").addEventListener("click", () => { saveVisit({ pages: [], viewed: [], searches: [] }); renderVisitPanel(); });

  // ---------- pages ----------
  let currentCategory = null; // the category the shopper is "in"; sent as search context

  function renderHome() {
    currentCategory = null;
    const featured = FEATURED_TYPES.map((t) => products.find((p) => p.product_type === t && p.in_stock)).filter(Boolean);
    main.innerHTML = `
      <section class="promo">
        <h1>Everything for the home, from tawa to toolbox.</h1>
        <p>Kitchenware, tools, storage and furniture for Pakistani homes.</p>
        <div class="promo-links">${CATEGORIES.map((c) => `<a href="#/c/${c}">${c}</a>`).join("")}</div>
      </section>
      <div class="cat-grid">${CATEGORIES.map((c) => `
        <a class="cat-tile" href="#/c/${c}">${ICONS[c]}<h3>${c}</h3>
          <p>${CAT_BLURB[c]}. ${products.filter((p) => p.category === c).length} products.</p></a>`).join("")}
      </div>
      <section class="ai-band" aria-labelledby="ai-title">
        <span class="ai-tag">AI search</span>
        <h2 id="ai-title">Don't know what it's called? Describe what it's for.</h2>
        <p>Search understands needs as well as product names, in English, Urdu or Roman Urdu. It only suggests products from this store, and says so when nothing fits.</p>
        <form class="ai-form" id="ai-form" role="search">
          <label class="sr" for="ai-q">Describe what you need</label>
          <input id="ai-q" type="search" autocomplete="off" placeholder="e.g. something to keep spices tidy in a small kitchen">
          <button type="submit">Search</button>
        </form>
        <div class="examples"><span>Try:</span>${EXAMPLES.map((e) => `<button type="button" data-q="${esc(e)}">${esc(e)}</button>`).join("")}</div>
      </section>
      <div class="row-head"><h2>Featured products</h2></div>
      <div class="grid">${featured.map(card).join("")}</div>`;
    document.getElementById("ai-form").addEventListener("submit", (e) => { e.preventDefault(); go(document.getElementById("ai-q").value); });
    main.querySelectorAll(".examples button").forEach((b) => b.addEventListener("click", () => go(b.dataset.q)));
  }

  function renderCategory(cat) {
    if (!CATEGORIES.includes(cat)) return renderNotFound();
    currentCategory = cat;
    track("pages", { category: cat });
    const items = products.filter((p) => p.category === cat);
    const subs = [...new Set(items.map((p) => p.subcategory))].sort();
    let activeSub = null;
    let sort = "default";
    main.innerHTML = `
      <div class="page-head"><div><h1>${esc(cat)}</h1><p class="meta" id="cat-meta"></p></div>
        <label>Sort <select id="sort"><option value="default">Featured</option><option value="asc">Price: low to high</option><option value="desc">Price: high to low</option></select></label>
      </div>
      <div class="filters" role="group" aria-label="Filter by type">${subs.map((s) => `<button type="button" class="chip" aria-pressed="false" data-sub="${esc(s)}">${esc(s)}</button>`).join("")}</div>
      <div class="grid" id="cat-grid"></div>`;
    const draw = () => {
      let list = activeSub ? items.filter((p) => p.subcategory === activeSub) : items.slice();
      if (sort === "asc") list.sort((a, b) => a.price_pkr - b.price_pkr);
      if (sort === "desc") list.sort((a, b) => b.price_pkr - a.price_pkr);
      document.getElementById("cat-grid").innerHTML = list.map(card).join("");
      document.getElementById("cat-meta").textContent = `${list.length} products${activeSub ? " in " + activeSub : ""}`;
    };
    main.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => {
      activeSub = activeSub === b.dataset.sub ? null : b.dataset.sub;
      main.querySelectorAll(".chip").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.sub === activeSub)));
      draw();
    }));
    document.getElementById("sort").addEventListener("change", (e) => { sort = e.target.value; draw(); });
    draw();
  }

  function renderProduct(id) {
    const p = byId[id];
    if (!p) return renderNotFound();
    currentCategory = p.category;
    track("viewed", { id: p.product_id, type: p.product_type, category: p.category, price: p.price_pkr });
    const specs = Object.entries(p.attributes).map(([k, v]) => `<dt>${esc(k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()))}</dt><dd>${esc(v)}</dd>`).join("");
    const others = products.filter((x) => x.product_type === p.product_type && x.product_id !== p.product_id);
    main.innerHTML = `
      <nav class="crumbs" aria-label="Breadcrumb"><a href="#/c/${esc(p.category)}">${esc(p.category)}</a> / ${esc(p.subcategory)}</nav>
      <div class="pdp">
        <div class="thumb t-${esc(p.category)}">${art(p)}</div>
        <div>
          <h1>${esc(p.title)}</h1>
          <span class="card-brand">${esc(p.brand)}</span>
          <span class="price">${rs(p.price_pkr)}</span>${stockLabel(p)}
          <dl class="specs">${specs}</dl>
          <p class="desc">${esc(p.description)}</p>
          ${p.what_its_for && p.what_its_for.length ? `<section class="wif" aria-labelledby="wif-h"><h2 id="wif-h">What it's for</h2>
            <ul>${p.what_its_for.map((u) => `<li>${esc(u)}</li>`).join("")}</ul>
            <small>Summarised by AI from the product details. Check the specs before buying.</small></section>` : ""}
        </div>
      </div>
      ${others.length ? `<section class="variants"><h2 class="section">Other options</h2><div class="grid">${others.map(card).join("")}</div></section>` : ""}`;
  }

  async function renderSearch(q, from) {
    currentCategory = from || null;
    topQ.value = q;
    main.innerHTML = `<div class="page-head"><div><h1>Results for “${esc(q)}”</h1><p class="meta" id="s-meta" aria-live="polite">Searching…</p></div></div><div id="s-body"></div>`;
    let data;
    try {
      const res = await fetch("/api/search", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, context: visitSummary(from) }),
      });
      if (!res.ok) throw new Error(`The search service replied with error ${res.status}.`);
      data = await res.json();
    } catch (err) {
      document.getElementById("s-meta").textContent = "";
      document.getElementById("s-body").innerHTML = `<div class="empty"><h2>Search didn't run</h2><p>${esc(err.message)} Check your connection and search again.</p></div>`;
      return;
    }
    track("searches", { q, from: from || null });
    const n = data.results.length;
    const how = data.mode === "keyword" ? "matched by keywords" : data.mode === "hybrid" ? "matched by meaning and keywords" : "matched by meaning";
    document.getElementById("s-meta").textContent =
      `${n} ${n === 1 ? "result" : "results"}, ${how}, in ${data.latency_ms} ms${from ? `. Searched from the ${from} page` : ""}`;

    const parts = [];
    if (data.fallback) parts.push(`<p class="notice warn">AI search is unavailable right now (${esc(data.fallback)}), so these are plain keyword matches. Describing a use may miss the right product.</p>`);
    const c = data.constraints || {};
    const cons = [];
    if (c.max_price) cons.push(`under ${rs(c.max_price)}`);
    if (c.in_stock) cons.push("in stock");
    if (cons.length) parts.push(`<p class="notice">Showing only items ${cons.join(" and ")}${data.removed_by_constraints ? ` (${data.removed_by_constraints} other matches left out because they don't fit)` : ""}.</p>`);
    if (!n) {
      parts.push(`<div class="empty"><h2>Nothing in our catalogue fits${cons.length ? " those limits" : ""}</h2><p>Try different words, ${cons.length ? "a higher budget, " : ""}or browse a category.</p></div>`);
    } else if (data.no_close_match) {
      parts.push(`<div class="notice warn"><strong>No close match in our catalogue.</strong> These are the nearest items, but they may not do what you described.</div>`);
      parts.push(`<div class="grid">${data.results.map(card).join("")}</div>`);
    } else {
      parts.push(`<div class="grid">${data.results.map(card).join("")}</div>`);
    }
    parts.push(`<p class="meta">Not finding it? <button type="button" class="ask-link" id="ask-from-search">Ask Sahulat about “${esc(q)}”</button></p>`);
    document.getElementById("s-body").innerHTML = parts.join("");
    document.getElementById("ask-from-search").addEventListener("click", () => { openChat(); sendChat(q); });
  }

  function renderNotFound() {
    main.innerHTML = `<div class="empty"><h1>Page not found</h1><p>That page doesn't exist. <a href="#/">Go to the home page</a>.</p></div>`;
  }

  // ---------- Ask Sahulat chat ----------
  const CHAT_KEY = "sahulat_chat_v1";
  const chatPanel = document.getElementById("chat-panel");
  const askBtn = document.getElementById("ask-btn");
  const chatLog = document.getElementById("chat-log");
  const chatForm = document.getElementById("chat-form");
  const chatQ = document.getElementById("chat-q");
  let chatBusy = false;
  const loadChat = () => { try { return JSON.parse(sessionStorage.getItem(CHAT_KEY)) || []; } catch { return chatMemory; } };
  let chatMemory = [];
  const saveChat = (t) => { chatMemory = t; try { sessionStorage.setItem(CHAT_KEY, JSON.stringify(t)); } catch { /* memory only */ } };

  function pickCard(p) {
    return `<a class="pick" href="#/p/${esc(p.product_id)}"><div class="thumb t-${esc(p.category)}">${art(p)}</div>
      <span><b>${esc(p.title)}</b><span class="pp">${rs(p.price_pkr)}</span> ${stockLabel(p)}
      ${p.why ? `<span class="why">${esc(p.why)}</span>` : ""}</span></a>`;
  }
  function renderChat() {
    const turns = loadChat();
    document.getElementById("chat-sub").textContent =
      `AI assistant. Suggests only products from this store.${currentCategory ? ` Opened from the ${currentCategory} page.` : ""}`;
    chatLog.innerHTML = (turns.length ? "" : `<p class="msg hint">Describe what you need, in English, Urdu or Roman Urdu. For example: “something to keep rotis warm” or “sasta sa spice box”.</p>`) +
      turns.map((t) => t.role === "user"
        ? `<div class="msg user">${esc(t.content)}</div>`
        : `<div class="msg bot${t.warn ? " warn" : ""}">${esc(t.content)}${(t.products || []).map(pickCard).join("")}</div>`).join("") +
      (chatBusy ? `<p class="msg hint">Looking through the catalogue…</p>` : "");
    chatLog.scrollTop = chatLog.scrollHeight;
  }
  function openChat() { chatPanel.hidden = false; askBtn.hidden = true; renderChat(); chatQ.focus(); }
  function closeChat() { chatPanel.hidden = true; askBtn.hidden = false; askBtn.focus(); }
  async function sendChat(text) {
    text = (text || "").trim();
    if (!text || chatBusy) return;
    const turns = loadChat();
    turns.push({ role: "user", content: text });
    saveChat(turns);
    chatBusy = true; chatForm.querySelector("button").disabled = true; renderChat();
    try {
      const res = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: turns.slice(-6).map(({ role, content }) => ({ role, content })), context: visitSummary(currentCategory) }),
      });
      if (!res.ok) throw new Error(`error ${res.status}`);
      const data = await res.json();
      turns.push({ role: "assistant", content: data.reply || "Here is what I found.", products: data.products || [],
                   warn: Boolean(data.diagnostics && data.diagnostics.fallback) });
    } catch (err) {
      turns.push({ role: "assistant", content: `The assistant couldn't be reached (${err.message}). Check your connection and send again.`, warn: true });
    }
    saveChat(turns.slice(-12));
    chatBusy = false; chatForm.querySelector("button").disabled = false; renderChat();
  }
  askBtn.addEventListener("click", openChat);
  document.getElementById("chat-close").addEventListener("click", closeChat);
  document.getElementById("chat-reset").addEventListener("click", () => { saveChat([]); renderChat(); chatQ.focus(); });
  chatForm.addEventListener("submit", (e) => { e.preventDefault(); const t = chatQ.value; chatQ.value = ""; sendChat(t); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !chatPanel.hidden && panel.hidden) closeChat(); });

  // ---------- routing ----------
  function go(q) {
    q = (q || "").trim();
    if (!q) return;
    location.hash = `#/search?q=${encodeURIComponent(q)}${currentCategory ? `&from=${encodeURIComponent(currentCategory)}` : ""}`;
  }
  topForm.addEventListener("submit", (e) => { e.preventDefault(); go(topQ.value); });

  function route() {
    const h = location.hash.slice(1) || "/";
    const [path, qs] = h.split("?");
    const params = new URLSearchParams(qs || "");
    const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
    if (parts.length === 0) renderHome();
    else if (parts[0] === "c") renderCategory(parts[1]);
    else if (parts[0] === "p") renderProduct(parts[1]);
    else if (parts[0] === "search") renderSearch(params.get("q") || "", params.get("from"));
    else renderNotFound();
    document.querySelectorAll("#cat-nav a").forEach((a) => a.setAttribute("aria-current", a.dataset.cat === currentCategory && parts[0] === "c" ? "page" : "false"));
    if (parts[0] !== "search") topQ.value = "";
    window.scrollTo(0, 0);
  }

  async function start() {
    document.getElementById("cat-nav").innerHTML = CATEGORIES.map((c) => `<a href="#/c/${c}" data-cat="${c}">${c}</a>`).join("");
    saveVisit(loadVisit());
    try {
      const res = await fetch("/api/catalogue");
      if (!res.ok) throw new Error(res.status);
      products = await res.json();
      byId = Object.fromEntries(products.map((p) => [p.product_id, p]));
    } catch {
      main.innerHTML = `<div class="empty"><h1>The store didn't load</h1><p>The product list couldn't be fetched. Reload the page to try again.</p></div>`;
      return;
    }
    window.addEventListener("hashchange", route);
    route();
  }
  start();
})();

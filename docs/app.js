const CAT_CLASS = { eco: "eco", pol: "pol", tek: "tek", car: "car", int: "int", liv: "liv" };

let activeCat = "all";
let query = "";
let factOnly = true;
let showScrapsOnly = false;
let debounceTimer = null;
let newsData = null; // raw payload from data/news.json

function loadScraps() {
  try { return JSON.parse(localStorage.getItem("nusantaraDaily.scraps") || "[]"); }
  catch { return []; }
}
function saveScraps() {
  try { localStorage.setItem("nusantaraDaily.scraps", JSON.stringify(scraps)); }
  catch { /* private window or blocked storage: scraps just won't persist */ }
}
let scraps = loadScraps();

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function highlight(text, q) {
  const safe = escapeHtml(text);
  if (!q) return safe;
  const idx = safe.toLowerCase().indexOf(q.toLowerCase());
  if (idx === -1) return safe;
  return safe.slice(0, idx) + '<mark style="background:rgba(255,184,77,0.45);border-radius:3px;">' + safe.slice(idx, idx + q.length) + "</mark>" + safe.slice(idx + q.length);
}

// Static build: there is no server to filter/paginate for us, so every view
// (category tab, search, fact-only toggle, scrap list, the 15-item default
// cap) is computed here from the one news.json payload fetched on load.
function getFilteredItems() {
  const all = (newsData && newsData.items) || [];
  if (showScrapsOnly) {
    const items = all.filter(a => scraps.includes(a.id));
    return { items, matchCount: items.length, truncated: false };
  }
  let items = all;
  if (activeCat !== "all") items = items.filter(a => a.category === activeCat);
  if (factOnly) items = items.filter(a => a.type === "news");
  const q = query.trim().toLowerCase();
  if (q) {
    items = items.filter(a =>
      (a.title + " " + a.summary + " " + a.sources.map(s => s.name).join(" ")).toLowerCase().includes(q)
    );
  }
  const matchCount = items.length;
  let truncated = false;
  if (activeCat === "all" && !q && matchCount > 15) {
    items = items.slice(0, 15);
    truncated = true;
  }
  return { items, matchCount, truncated };
}

function renderTabs() {
  const tabsEl = document.getElementById("tabs");
  tabsEl.hidden = showScrapsOnly;
  if (showScrapsOnly || !newsData) return;
  const categories = newsData.categories || [];
  const totalAll = categories.reduce((sum, c) => sum + c.count, 0);
  const all = [{ id: "all", label: "전체", count: totalAll, cls: "" }]
    .concat(categories.map(c => ({ ...c, cls: CAT_CLASS[c.id] || "" })));

  tabsEl.innerHTML = all.map(c => `
    <button class="tab" data-cat="${c.id}" data-active="${activeCat === c.id}">
      ${c.cls ? `<span class="dot" style="background:var(--cat-${c.cls})"></span>` : ""}
      ${c.label}<span style="opacity:.65;font-weight:500;">&nbsp;${c.count}</span>
    </button>`).join("");

  tabsEl.querySelectorAll(".tab").forEach(btn => {
    btn.addEventListener("click", () => { activeCat = btn.dataset.cat; renderAll(); });
  });
}

function renderViewNotice(truncated, total, matchCount) {
  const notice = document.getElementById("viewNotice");
  if (showScrapsOnly || !truncated) { notice.hidden = true; return; }
  notice.hidden = false;
  notice.textContent = `최신 상위 ${total}건 표시 중 (전체 ${matchCount}건 · 카테고리를 선택하면 더 볼 수 있어요)`;
}

function cardHtml(a, i) {
  const cls = CAT_CLASS[a.category] || "";
  const primary = a.sources[0] || { name: "-", url: "#" };
  const crossVerified = a.sources.length > 1;
  const saved = scraps.includes(a.id);
  let domain = "";
  try { domain = new URL(primary.url).hostname.replace(/^www\./, ""); } catch { /* malformed source url */ }

  return `
    <article class="card glass" style="animation-delay:${0.04 * i}s">
      <div class="card-top">
        <div class="badges">
          <span class="badge" style="color:var(--cat-${cls});background:color-mix(in srgb, var(--cat-${cls}) 16%, transparent)"><span class="dot"></span>${escapeHtml(a.category_label)}</span>
          <span class="badge ${a.type}">${a.type === "news" ? "뉴스" : "오피니언"}</span>
        </div>
        <div class="card-top-right">
          <span class="timestamp">${escapeHtml(a.published_at)}</span>
          <button class="bookmark-btn" data-id="${a.id}" data-saved="${saved}" title="스크랩">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3H7a2 2 0 0 0-2 2v16l7-4 7 4V5a2 2 0 0 0-2-2z"/></svg>
          </button>
        </div>
      </div>
      <h2 class="headline"><a href="${primary.url}" target="_blank" rel="noopener noreferrer">${highlight(a.title, query)}</a></h2>
      ${a.summary ? `<p class="summary">${highlight(a.summary, query)}</p>` : ""}
      ${crossVerified ? `<div class="verify-row"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>${a.sources.length}개 매체 교차 확인 — ${a.sources.map(s => escapeHtml(s.name)).join(", ")}</div>` : ""}
      <div class="source-row">
        <span class="source"><b>${escapeHtml(primary.name)}</b> <span class="src-url">· ${escapeHtml(domain)}</span></span>
        <a class="open" href="${primary.url}" target="_blank" rel="noopener noreferrer">원문 보기
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M7 17L17 7M7 7h10v10"/></svg>
        </a>
      </div>
    </article>`;
}

function renderFeed() {
  const feed = document.getElementById("feed");
  const scrapHeading = document.getElementById("scrapHeading");
  const { items, matchCount, truncated } = getFilteredItems();

  if (showScrapsOnly) {
    scrapHeading.hidden = false;
    scrapHeading.innerHTML = `⭐ 내 스크랩 <span style="color:var(--amber)">${items.length}건</span>`;
  } else {
    scrapHeading.hidden = true;
  }
  renderViewNotice(truncated, items.length, matchCount);

  if (items.length === 0) {
    feed.innerHTML = showScrapsOnly
      ? `<div class="empty-scrap card glass">아직 스크랩한 기사가 없습니다.<br>카드 우측 상단의 🔖 아이콘을 눌러 저장해보세요.</div>`
      : `<div class="empty-scrap card glass">일치하는 기사가 없습니다. 다른 검색어나 카테고리를 시도해보세요.</div>`;
    return;
  }
  feed.innerHTML = items.map((a, i) => cardHtml(a, i)).join("");
}

function renderStats() {
  const categories = (newsData && newsData.categories) || [];
  const el = document.getElementById("statList");
  el.innerHTML = categories.map(c => `
    <div class="stat-row">
      <span class="label"><span class="dot" style="background:var(--cat-${CAT_CLASS[c.id] || ""})"></span>${escapeHtml(c.label)}</span>
      <span class="n">${c.count}건</span>
    </div>`).join("");
}

function renderSources() {
  const sources = (newsData && newsData.sources) || [];
  const el = document.getElementById("srcList");
  el.innerHTML = sources.slice(0, 12).map(s => `
    <li>
      <span class="name"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>${escapeHtml(s.name)}</span>
      <span class="n">${s.count}건</span>
    </li>`).join("");
}

function renderFactStats() {
  const all = (newsData && newsData.items) || [];
  const total = all.length;
  const newsCount = all.filter(a => a.type === "news").length;
  const opinionCount = total - newsCount;
  animateNumber("statTotal", total);
  animateNumber("statNews", newsCount);
  animateNumber("statOpinion", opinionCount);
  requestAnimationFrame(() => {
    document.getElementById("statBar").style.width = total ? Math.round(newsCount / total * 100) + "%" : "0%";
  });
}

function animateNumber(id, target) {
  const el = document.getElementById(id);
  const start = performance.now();
  const dur = 700;
  function tick(now) {
    const p = Math.min(1, (now - start) / dur);
    el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function renderMeta() {
  const dot = document.getElementById("liveDot");
  const label = document.getElementById("lastUpdated");
  const errorBanner = document.getElementById("errorBanner");
  const errors = (newsData && newsData.errors) || {};
  const errorCount = Object.keys(errors).length;

  dot.classList.toggle("stale", errorCount > 0);
  label.textContent = newsData && newsData.last_updated ? `마지막 갱신 ${newsData.last_updated}` : "갱신 정보 없음";

  if (errorCount > 0) {
    errorBanner.hidden = false;
    errorBanner.textContent = `일부 카테고리를 불러오지 못했습니다 (${Object.keys(errors).join(", ")}). 다음 자동 갱신 때 다시 시도됩니다.`;
  } else {
    errorBanner.hidden = true;
  }
}

function renderHero() {
  const all = (newsData && newsData.items) || [];
  const top3 = all.slice(0, 3);
  const grid = document.getElementById("heroGrid");
  grid.innerHTML = top3.map((a, i) => {
    const primary = a.sources[0] || { name: "-", url: "#" };
    const extra = a.sources.length > 1 ? ` 외 ${a.sources.length - 1}곳` : "";
    return `
    <a class="hero-card" href="${primary.url}" target="_blank" rel="noopener noreferrer">
      <span class="hero-rank">0${i + 1} · ${escapeHtml(a.category_label)}</span>
      <span class="hero-headline">${escapeHtml(a.title)}</span>
      <span class="hero-src">${escapeHtml(primary.name)}${extra}</span>
    </a>`;
  }).join("");

  const now = new Date();
  document.getElementById("heroDate").textContent =
    now.toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric", weekday: "short" }) + " · 자카르타";
}

function renderAll() {
  renderTabs();
  renderFeed();
  renderStats();
  renderSources();
  renderFactStats();
  renderMeta();
}

async function loadNews() {
  const res = await fetch(`data/news.json?t=${Date.now()}`);
  newsData = await res.json();
  renderAll();
  renderHero();
}

async function forceRefresh() {
  const btn = document.getElementById("refreshBtn");
  btn.classList.add("spinning");
  btn.disabled = true;
  try {
    await Promise.all([loadNews(), loadMarkets()]);
  } finally {
    btn.classList.remove("spinning");
    btn.disabled = false;
  }
}

document.getElementById("searchInput").addEventListener("input", e => {
  query = e.target.value;
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(renderFeed, 150);
});

const switchEl = document.getElementById("switchEl");
function toggleFact() {
  factOnly = !factOnly;
  switchEl.dataset.on = String(factOnly);
  switchEl.setAttribute("aria-checked", String(factOnly));
  renderFeed();
}
switchEl.addEventListener("click", toggleFact);
switchEl.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleFact(); } });

document.getElementById("refreshBtn").addEventListener("click", forceRefresh);

const scrapBtn = document.getElementById("scrapBtn");
scrapBtn.addEventListener("click", () => {
  showScrapsOnly = !showScrapsOnly;
  scrapBtn.dataset.active = String(showScrapsOnly);
  renderTabs();
  renderFeed();
});
document.getElementById("scrapCount").textContent = scraps.length;

document.getElementById("feed").addEventListener("click", e => {
  const btn = e.target.closest(".bookmark-btn");
  if (!btn) return;
  const id = btn.dataset.id;
  scraps = scraps.includes(id) ? scraps.filter(x => x !== id) : scraps.concat(id);
  saveScraps();
  document.getElementById("scrapCount").textContent = scraps.length;
  renderFeed();
});

function zoneTime(offsetHours) {
  const now = new Date();
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  const t = new Date(utcMs + offsetHours * 3600000);
  return String(t.getHours()).padStart(2, "0") + ":" + String(t.getMinutes()).padStart(2, "0");
}
function tickClock() {
  document.getElementById("clockWIB").textContent = zoneTime(7);
  document.getElementById("clockWITA").textContent = zoneTime(8);
  document.getElementById("clockKST").textContent = zoneTime(9);
}
tickClock();
setInterval(tickClock, 15000);

function formatMarket(v, decimals) {
  return v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
function renderMarkets(state) {
  const el = document.getElementById("marketTickers");
  if (!state || !state.markets || state.markets.length === 0) {
    el.innerHTML = `<span style="font-size:12px;color:var(--ink-dim)">시세를 불러오지 못했습니다</span>`;
    return;
  }
  el.innerHTML = state.markets.map(m => {
    const up = m.change >= 0;
    const arrow = up ? "M12 19V5M5 12l7-7 7 7" : "M12 5v14M5 12l7 7 7-7";
    return `
    <div class="ticker">
      <span class="label">${escapeHtml(m.label)}</span>
      <span class="value">${formatMarket(m.value, m.decimals)}</span>
      <span class="change ${up ? "up" : "down"}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="${arrow}"/></svg>${Math.abs(m.change).toFixed(2)}%
      </span>
    </div>`;
  }).join("");
}
async function loadMarkets() {
  const res = await fetch(`data/markets.json?t=${Date.now()}`);
  const state = await res.json();
  renderMarkets(state);
}

loadNews();
loadMarkets();
setInterval(loadMarkets, 60000);

// Side panel — thin UI layer.
// Background owns the save request, so closing this panel never kills a save.

const BRIDGE_URL = "http://localhost:5128";

const TOPICS = {
  ai: "AI and agents", engineering: "Software engineering", design: "Design", startups: "Startups and product",
  craft: "Work and craft", writing: "Writing and content", money: "Money and markets", other: "Other",
};

const SHELVES = {
  reading: "Reading",
  article: "Reading",
  "x-article": "Reading",
  post: "Posts",
  tweet: "Posts",
  inspiration: "Inspiration",
  tool: "Tools",
  repo: "Tools",
  video: "Reading",
};

const $ = (id) => document.getElementById(id);

const saveView = $("save-view");
const libraryView = $("library-view");
const pageFavicon = $("page-favicon");
const pageTitle = $("page-title");
const pageHost = $("page-host");
const urlInput = $("url-input");
const noteInput = $("note-input");
const saveBtn = $("save-btn");
const statusEl = $("status");
const pushGithub = $("push-github");
const helper = $("helper");
const helperText = $("helper-text");

let tabPage = { id: null, windowId: null, url: "", title: "", favIconUrl: "" };
let overrideUrl = ""; // set by "Change", right-click on a link, or retry
let selectedKind = "auto";
let ogImage = "";      // the page's own preview image (og:image)
let shot = "";         // screenshot data URL, only saved on the Inspiration shelf
let shotMode = "";     // "full" | "area" | ""
let shotDeclined = false;
let lastFailed = null;
let libraryItems = [];
let libraryFilter = "All";
let libraryIsLocal = false;

// ---- Current page ----

function isSaveable(url) {
  return /^https?:\/\//i.test(url || "");
}

function hostOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; }
}

function faviconFor(url, hint) {
  if (hint && hint.startsWith("http")) return hint;
  const host = hostOf(url);
  return host ? `https://www.google.com/s2/favicons?sz=64&domain=${encodeURIComponent(host)}` : "icons/icon16.png";
}

function targetUrl() {
  return (overrideUrl || tabPage.url || "").trim();
}

function renderPageCard() {
  const url = targetUrl();
  const usingTab = !overrideUrl && url === tabPage.url;

  if (!isSaveable(url)) {
    pageFavicon.src = "icons/icon16.png";
    pageTitle.textContent = url ? "This page can’t be saved" : "Nothing to save here";
    pageHost.textContent = "Open a web page, or paste a link.";
    saveBtn.disabled = !overrideUrl;
    renderThumb();
    return;
  }

  saveBtn.disabled = false;
  pageFavicon.src = faviconFor(url, usingTab ? tabPage.favIconUrl : "");
  pageTitle.textContent = usingTab && tabPage.title ? tabPage.title : hostOf(url);
  pageHost.textContent = url.replace(/^https?:\/\/(www\.)?/, "");
  renderThumb();
}

async function refreshTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const changed = (tab?.url || "") !== tabPage.url;
  tabPage = {
    id: tab?.id ?? null,
    windowId: tab?.windowId ?? null,
    url: tab?.url || "",
    title: tab?.title || "",
    favIconUrl: tab?.favIconUrl || "",
  };
  if (changed) {
    ogImage = "";
    clearShot();
    loadPreviewImage();
  }
  renderPageCard();
}

// Read og:image straight from the open tab, so it works on logged-in pages too.
async function loadPreviewImage() {
  if (!tabPage.id || !isSaveable(tabPage.url)) return renderThumb();
  const url = tabPage.url;
  try {
    const [{ result } = {}] = await chrome.scripting.executeScript({
      target: { tabId: tabPage.id },
      func: () => {
        const pick = (sel) => document.querySelector(sel)?.getAttribute("content") || document.querySelector(sel)?.getAttribute("href");
        const raw =
          pick('meta[property="og:image"]') ||
          pick('meta[name="og:image"]') ||
          pick('meta[name="twitter:image"]') ||
          pick('meta[property="twitter:image"]') ||
          pick('link[rel="image_src"]');
        try { return raw ? new URL(raw, location.href).href : ""; } catch { return ""; }
      },
    });
    if (url === tabPage.url) ogImage = result || "";
  } catch {
    ogImage = ""; // chrome://, Web Store, PDFs and similar pages can't be scripted
  }
  renderThumb();
}

function renderThumb() {
  const thumb = $("thumb");
  const img = $("thumb-img");
  const inspo = selectedKind === "inspiration";
  const src = inspo && shot ? shot : overrideUrl ? "" : ogImage;

  $("shot-bar").hidden = !inspo || !isSaveable(targetUrl()) || !!overrideUrl;
  $("shot-full").classList.toggle("on", inspo && shotMode === "full");
  $("shot-area").classList.toggle("on", inspo && shotMode === "area");
  $("thumb-badge").hidden = !(inspo && shot);
  thumb.classList.toggle("shot", inspo && !!shot);

  if (!src) {
    thumb.hidden = true;
    img.removeAttribute("src");
    return;
  }
  if (img.getAttribute("src") !== src) {
    img.onerror = () => { if (src === ogImage) { ogImage = ""; renderThumb(); } };
    img.src = src;
  }
  thumb.hidden = false;
}

chrome.tabs.onActivated.addListener(() => {
  if (!overrideUrl) refreshTab();
});
chrome.tabs.onUpdated.addListener((_id, change, tab) => {
  if (!tab.active || overrideUrl) return;
  if (change.url || change.title || change.favIconUrl || change.status === "complete") refreshTab();
});

$("edit-url").addEventListener("click", () => {
  const show = urlInput.hidden;
  urlInput.hidden = !show;
  if (show) {
    urlInput.value = targetUrl();
    urlInput.focus();
    urlInput.select();
  } else {
    overrideUrl = "";
    renderPageCard();
  }
  $("edit-url").textContent = show ? "Use this tab" : "Change";
});

urlInput.addEventListener("input", () => {
  overrideUrl = urlInput.value.trim();
  urlInput.classList.remove("invalid");
  renderPageCard();
});

function setOverride(url) {
  overrideUrl = url;
  urlInput.hidden = false;
  urlInput.value = url;
  $("edit-url").textContent = "Use this tab";
  renderPageCard();
}

// ---- Shelf chips ----

$("shelf-chips").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  selectedKind = chip.dataset.kind;
  document.querySelectorAll("#shelf-chips .chip").forEach((c) => {
    const on = c === chip;
    c.classList.toggle("on", on);
    c.setAttribute("aria-checked", String(on));
  });
  if (selectedKind === "inspiration" && !shot && !shotDeclined && !overrideUrl && isSaveable(tabPage.url)) {
    captureFull();
  } else {
    setShotHint("");
    renderThumb();
  }
});

// ---- Screenshots (Inspiration shelf) ----

const MAX_SHOT_WIDTH = 1600;

function setShotHint(text, isError = false) {
  const el = $("shot-hint");
  el.textContent = text;
  el.classList.toggle("error", isError);
  el.hidden = !text;
}

function clearShot() {
  shot = "";
  shotMode = "";
  shotDeclined = false;
  setShotHint("");
  cancelAreaSelect();
}

async function captureTab() {
  return chrome.tabs.captureVisibleTab(tabPage.windowId ?? chrome.windows.WINDOW_ID_CURRENT, { format: "png" });
}

// Crop (optional) and shrink to a JPEG so the vault repo stays small.
async function processShot(dataUrl, area, viewport) {
  const bitmap = await createImageBitmap(await (await fetch(dataUrl)).blob());
  const scale = viewport ? bitmap.width / viewport.w : 1;
  const sx = area ? Math.round(area.x * scale) : 0;
  const sy = area ? Math.round(area.y * scale) : 0;
  const sw = area ? Math.round(area.w * scale) : bitmap.width;
  const sh = area ? Math.round(area.h * scale) : bitmap.height;
  const out = Math.min(1, MAX_SHOT_WIDTH / sw);
  const canvas = new OffscreenCanvas(Math.round(sw * out), Math.round(sh * out));
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bitmap, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
  const blob = await canvas.convertToBlob({ type: "image/jpeg", quality: 0.85 });
  return new Promise((resolve) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.readAsDataURL(blob);
  });
}

async function captureFull() {
  shotDeclined = false;
  $("thumb").classList.add("loading");
  try {
    shot = await processShot(await captureTab());
    shotMode = "full";
    setShotHint("");
  } catch (err) {
    setShotHint(`Couldn’t capture this tab. ${err.message || ""}`.trim(), true);
  } finally {
    $("thumb").classList.remove("loading");
    renderThumb();
  }
}

async function startAreaSelect() {
  if (!tabPage.id) return;
  try {
    await chrome.scripting.executeScript({ target: { tabId: tabPage.id }, files: ["content/select-area.js"] });
    setShotHint("Drag on the page to pick an area. Press Esc to cancel.");
    $("shot-area").classList.add("on");
  } catch (err) {
    setShotHint("This page doesn’t allow area selection. Use Whole screen instead.", true);
  }
}

function cancelAreaSelect() {
  if (!tabPage.id) return;
  chrome.scripting
    .executeScript({ target: { tabId: tabPage.id }, func: () => window.__bvSelectCancel && window.__bvSelectCancel() })
    .catch(() => {});
}

async function onAreaPicked(message) {
  if (message.cancelled) {
    setShotHint(message.reason === "too-small" ? "That area was too small. Try dragging a bigger box." : "");
    renderThumb();
    return;
  }
  $("thumb").classList.add("loading");
  try {
    await new Promise((r) => setTimeout(r, 60));
    shot = await processShot(await captureTab(), message.rect, message.viewport);
    shotMode = "area";
    shotDeclined = false;
    setShotHint("");
  } catch (err) {
    setShotHint(`Couldn’t capture that area. ${err.message || ""}`.trim(), true);
  } finally {
    $("thumb").classList.remove("loading");
    renderThumb();
  }
}

$("shot-full").addEventListener("click", captureFull);
$("shot-area").addEventListener("click", startAreaSelect);
$("shot-clear").addEventListener("click", () => {
  shot = "";
  shotMode = "";
  shotDeclined = true;
  setShotHint("Saving without a screenshot. The page’s preview image is used instead.");
  renderThumb();
});

function resetShelf() {
  $("shelf-chips").querySelector('[data-kind="auto"]').click();
}

// ---- Publish toggle ----

chrome.storage.local.get("pushToGithub", ({ pushToGithub }) => {
  pushGithub.checked = !!pushToGithub;
});
pushGithub.addEventListener("change", () => {
  chrome.storage.local.set({ pushToGithub: pushGithub.checked });
});

// ---- Save ----

function save(retry) {
  const payload = retry || {
    url: targetUrl(),
    note: noteInput.value.trim(),
    kind: selectedKind,
    title: !overrideUrl ? tabPage.title : "",
    image: !overrideUrl ? ogImage : "",
    screenshot: selectedKind === "inspiration" && !overrideUrl ? shot : "",
    pushToGithub: pushGithub.checked,
  };

  if (!isSaveable(payload.url)) {
    urlInput.hidden = false;
    urlInput.classList.add("invalid");
    urlInput.focus();
    return;
  }

  chrome.runtime.sendMessage({ type: "SAVE_ARTICLE", payload });

  showStatus("saving", {
    title: `Saving ${hostOf(payload.url)}`,
    sub: payload.pushToGithub
      ? "Reading the page, sorting it, then publishing. You can close this panel."
      : "Reading the page and sorting it. You can close this panel.",
  });

  noteInput.value = "";
  shot = "";
  shotMode = "";
  shotDeclined = false;
  setShotHint("");
  resetShelf();
  if (overrideUrl) {
    overrideUrl = "";
    urlInput.hidden = true;
    $("edit-url").textContent = "Change";
    renderPageCard();
  }
}

saveBtn.addEventListener("click", () => save());

document.addEventListener("keydown", (e) => {
  if (saveView.hidden) return;
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    if (!saveBtn.disabled) save();
  }
  if (e.key === "Enter" && e.target === urlInput) {
    e.preventDefault();
    save();
  }
});

// ---- Status card ----

function showStatus(state, { title, sub = "", chips = [], image = "", note = "", actions = [] }) {
  statusEl.hidden = false;
  statusEl.className = `status ${state}`;
  $("status-icon").textContent = state === "done" ? "✓" : state === "failed" ? "!" : "";
  $("status-title").textContent = title;
  $("status-sub").textContent = sub;

  const imgEl = $("status-image");
  imgEl.hidden = !image;
  if (image) {
    imgEl.onerror = () => (imgEl.hidden = true);
    imgEl.src = image;
  }

  const chipsEl = $("status-chips");
  chipsEl.innerHTML = "";
  chips.forEach(({ text, kind }) => {
    const span = document.createElement("span");
    span.className = kind ? "chip kind" : "chip";
    span.textContent = text;
    chipsEl.appendChild(span);
  });
  chipsEl.hidden = chips.length === 0;

  const noteEl = $("status-note");
  noteEl.textContent = note;
  noteEl.hidden = !note;

  const actionsEl = $("status-actions");
  actionsEl.innerHTML = "";
  actions.forEach(({ label, onClick }) => {
    const b = document.createElement("button");
    b.className = "ghost-btn";
    b.textContent = label;
    b.addEventListener("click", onClick);
    actionsEl.appendChild(b);
  });
}

function shelfOf(item) {
  if (item.shelf && SHELVES[item.shelf]) return SHELVES[item.shelf];
  if (item.kind && item.kind !== "auto" && SHELVES[item.kind]) return SHELVES[item.kind];
  if (item.type && SHELVES[item.type]) return SHELVES[item.type];
  if (/^https?:\/\/(www\.)?(x|twitter)\.com\/[^/]+\/status\//.test(item.url || "")) return "Posts";
  if (item.origin === "bookmark") return "Tools";
  return "Reading";
}

function showDone(data) {
  const shelf = shelfOf(data);
  let sub = data.title || hostOf(data.url);
  if (data.pushed) sub += " · Published to GitHub";
  if (data.pushError) sub += ` · Publishing failed: ${data.pushError}`;
  if (data.jevError) sub += " · Jev was unavailable, sorted by simple rules";
  else if (data.classifiedBy === "rules") sub += " · Sorted by simple rules (add a TypeSafe key for Jev)";
  if (data.needsReview) sub += " · Jev wasn’t sure about the shelf";

  const chips = [{ text: shelf, kind: true }];
  if (data.topic && TOPICS[data.topic]) chips.push({ text: TOPICS[data.topic] });
  else if (data.category && data.category !== shelf) chips.push({ text: data.category });
  (data.tags || []).slice(0, 3).forEach((t) => chips.push({ text: t }));

  showStatus("done", {
    title: `${data.updated ? "Updated in" : "Saved to"} ${shelf}`,
    sub,
    chips,
    image: data.screenshot ? `${BRIDGE_URL}/${data.screenshot}` : "",
    note: data.note || "",
    actions: [{ label: "Dismiss", onClick: () => (statusEl.hidden = true) }],
  });
}

function showFailed(result) {
  lastFailed = result;
  showStatus("failed", {
    title: "Couldn’t save",
    sub: result.error || "Something went wrong.",
    actions: [
      { label: "Try again", onClick: () => lastFailed && save(lastFailed.payload || { url: lastFailed.url, note: lastFailed.note || "", kind: lastFailed.kind || "auto", title: "", pushToGithub: pushGithub.checked }) },
      { label: "Dismiss", onClick: () => (statusEl.hidden = true) },
    ],
  });
}

chrome.runtime.onMessage.addListener((message, sender) => {
  if (message.type === "BV_AREA") {
    if (sender.tab && sender.tab.id === tabPage.id) onAreaPicked(message);
    return;
  }
  if (message.type === "PREFILL_URL") {
    showSave();
    if (message.url && message.url !== tabPage.url) setOverride(message.url);
    noteInput.focus();
    return;
  }
  if (message.type !== "SAVE_STATUS") return;
  if (message.state === "loading") {
    showStatus("saving", { title: `Saving ${hostOf(message.url)}`, sub: "Reading the page and sorting it. You can close this panel." });
  } else if (message.state === "done") {
    showDone(message.data);
  } else if (message.state === "error") {
    showFailed(message.result || { error: message.error });
  }
});

// ---- Recent ----

function rowEl(item, { rich = false, deletable = false } = {}) {
  const a = document.createElement("a");
  a.className = rich ? "row rich" : "row";
  a.href = item.url;
  a.target = "_blank";
  a.rel = "noopener";

  const img = document.createElement("img");
  img.className = "favicon";
  img.src = faviconFor(item.url);
  img.alt = "";
  a.appendChild(img);

  const body = document.createElement("div");
  body.style.minWidth = "0";
  const title = document.createElement("div");
  title.className = "row-title";
  title.textContent = item.title || hostOf(item.url);
  body.appendChild(title);

  if (rich) {
    const sub = document.createElement("div");
    sub.className = "row-sub";
    const left = document.createElement("span");
    left.textContent = [hostOf(item.url), formatDate(item.savedAt || item.timestamp)].filter(Boolean).join(", ");
    const right = document.createElement("span");
    right.textContent = shelfOf(item);
    sub.append(left, right);
    body.appendChild(sub);
    if (item.screenshot) {
      const shotImg = document.createElement("img");
      shotImg.className = "row-shot";
      shotImg.src = `${BRIDGE_URL}/${item.screenshot}`;
      shotImg.alt = "";
      shotImg.onerror = () => shotImg.remove();
      body.appendChild(shotImg);
    }
    if (item.note) {
      const b = document.createElement("span");
      b.className = "bubble";
      b.textContent = item.note;
      body.appendChild(b);
    }
  }
  a.appendChild(body);

  if (!rich) {
    const side = document.createElement("span");
    side.className = "row-meta";
    side.textContent = shelfOf(item);
    a.appendChild(side);
  } else if (deletable) {
    a.style.gridTemplateColumns = "16px minmax(0,1fr) auto";
    const del = document.createElement("button");
    del.className = "row-del";
    del.title = "Remove from vault";
    del.textContent = "×";
    del.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      removeBookmark(item.id);
    });
    a.appendChild(del);
  }
  return a;
}

async function renderRecent() {
  const { history = [] } = await chrome.storage.local.get("history");
  const list = $("recent-list");
  list.innerHTML = "";
  const done = history.filter((h) => h.success !== false).slice(0, 5);
  if (done.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Nothing saved yet. Your saves will show up here.";
    list.appendChild(empty);
    return;
  }
  done.forEach((h) => list.appendChild(rowEl(h)));
}

chrome.storage.onChanged.addListener((changes) => {
  if (changes.history) renderRecent();
});

// ---- Library ----

async function loadLibrary() {
  const list = $("lib-list");
  const empty = $("lib-empty");
  list.innerHTML = "";
  empty.hidden = true;
  try {
    const resp = await fetch(`${BRIDGE_URL}/items`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    libraryItems = (await resp.json()).items || [];
    libraryIsLocal = false;
  } catch {
    libraryIsLocal = true;
    const { history = [] } = await chrome.storage.local.get("history");
    libraryItems = history.filter((h) => h.success !== false);
    empty.hidden = false;
    empty.innerHTML = "Showing saves from this browser only. Start the helper to see your whole vault:<br><br><code>python3 bridge/server.py</code>";
  }
  renderFilters();
  renderLibrary();
}

function renderFilters() {
  const counts = { All: libraryItems.length, Reading: 0, Posts: 0, Inspiration: 0, Tools: 0 };
  libraryItems.forEach((i) => { counts[shelfOf(i)] = (counts[shelfOf(i)] || 0) + 1; });
  const el = $("lib-filters");
  el.innerHTML = "";
  Object.entries(counts).forEach(([name, n]) => {
    if (name !== "All" && n === 0) return;
    const b = document.createElement("button");
    b.className = name === libraryFilter ? "chip on" : "chip";
    b.innerHTML = `${name}<span class="count"></span>`;
    b.querySelector(".count").textContent = n;
    b.addEventListener("click", () => {
      libraryFilter = name;
      renderFilters();
      renderLibrary();
    });
    el.appendChild(b);
  });
}

function renderLibrary() {
  const q = $("lib-search").value.trim().toLowerCase();
  const list = $("lib-list");
  list.innerHTML = "";
  const items = libraryItems.filter((i) => {
    if (libraryFilter !== "All" && shelfOf(i) !== libraryFilter) return false;
    if (!q) return true;
    return [i.title, i.url, i.note, i.category, TOPICS[i.topic], ...(i.tags || [])].some((v) => (v || "").toLowerCase().includes(q));
  });
  items.forEach((i) => list.appendChild(rowEl(i, { rich: true, deletable: !!i.id && !libraryIsLocal })));
  if (items.length === 0 && libraryItems.length > 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = q ? `Nothing matches “${q}”.` : "Nothing on this shelf yet.";
    list.appendChild(empty);
  }
}

$("lib-search").addEventListener("input", renderLibrary);

async function removeBookmark(id) {
  try {
    await fetch(`${BRIDGE_URL}/item/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
  } finally {
    loadLibrary();
  }
}

function showSave() {
  libraryView.hidden = true;
  saveView.hidden = false;
}

function showLibrary() {
  saveView.hidden = true;
  libraryView.hidden = false;
  loadLibrary();
  $("lib-search").focus();
}

$("open-library").addEventListener("click", showLibrary);
$("see-all").addEventListener("click", showLibrary);
$("back-btn").addEventListener("click", showSave);

// ---- Helper status ----

async function checkHelper() {
  try {
    const resp = await fetch(`${BRIDGE_URL}/health`, { cache: "no-store" });
    if (!resp.ok) throw new Error();
    helper.className = "helper on";
    helperText.textContent = "Helper running";
    helper.title = "The local helper is running";
  } catch {
    helper.className = "helper off";
    helperText.textContent = "Helper off";
    helper.title = "Start it with: python3 bridge/server.py";
  }
}

// ---- Helpers ----

function formatDate(value) {
  if (!value) return "";
  const d = new Date(value.length === 10 ? value + "T00:00:00" : value);
  if (isNaN(d)) return "";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

// ---- Init ----

async function checkPendingResult() {
  const { lastSaveResult } = await chrome.storage.local.get("lastSaveResult");
  if (!lastSaveResult) return;
  if (Date.now() - new Date(lastSaveResult.timestamp).getTime() > 120_000) return;
  if (lastSaveResult.success) showDone(lastSaveResult);
  else showFailed(lastSaveResult);
}

refreshTab();
renderRecent();
checkHelper();
setInterval(checkHelper, 10_000);
checkPendingResult();

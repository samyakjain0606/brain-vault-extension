// Background service worker
// Owns the save lifecycle — runs even if side panel is closed.
// Side panel is just a thin UI that fires messages and listens for updates.

const BRIDGE_URL = "http://localhost:5128";
const HELPER_OFF = "The local helper isn’t running. Start it with: python3 bridge/server.py";

chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch(console.error);

// ---- Context menu ----

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "save-to-brain-vault",
    title: "Save to Brain Vault",
    contexts: ["page", "link"],
  });
});

function openPanelWith(tabId, url) {
  chrome.sidePanel.open({ tabId }).then(() => {
    setTimeout(() => chrome.runtime.sendMessage({ type: "PREFILL_URL", url }).catch(() => {}), 400);
  });
}

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "save-to-brain-vault") {
    openPanelWith(tab.id, info.linkUrl || info.pageUrl);
  }
});

// ---- Keyboard shortcut ----

chrome.commands.onCommand.addListener((command) => {
  if (command !== "save-article") return;
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) openPanelWith(tabs[0].id, tabs[0].url);
  });
});

// ---- Message handler ----

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SAVE_ARTICLE") {
    saveItem(message.payload);
    sendResponse({ accepted: true });
    return false;
  }
});

// ---- Core save logic (runs in background, survives side panel close) ----

async function postJson(path, body) {
  const resp = await fetch(`${BRIDGE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  return { resp, data };
}

async function saveItem(payload) {
  const { url, note = "", kind = "auto", title = "", image = "", screenshot = "", pushToGithub = false } = payload;
  const saveId = Date.now().toString();
  broadcast({ type: "SAVE_STATUS", state: "loading", saveId, url });

  try {
    const { resp, data } = await postJson("/save", { url, note, kind, title, image, screenshot, pushToGithub });
    if (!resp.ok) throw new Error(data.error || `Helper error ${resp.status}`);
    const item = data.item || {};
    const result = {
      id: item.id,
      title: item.title,
      shelf: item.shelf,
      topic: item.topic,
      tags: item.tags || [],
      source: item.source || "",
      screenshot: item.screenshot || "", // path inside the vault, never the image data
      classifiedBy: item.classifiedBy,
      needsReview: !!item.needsReview,
      updated: !!data.updated,
      jevError: data.jevError || "",
      pushed: !!data.pushed,
      pushError: data.pushError || "",
    };

    const entry = { success: true, saveId, url, note, kind, ...result, timestamp: new Date().toISOString() };
    await chrome.storage.local.set({ lastSaveResult: entry });
    await addToHistory(entry);
    broadcast({ type: "SAVE_STATUS", state: "done", saveId, data: entry });

    chrome.notifications.create(saveId, {
      type: "basic",
      iconUrl: "icons/icon128.png",
      title: "Saved to Brain Vault",
      message: `${entry.title || url}${entry.pushed ? "\nPublished to GitHub" : ""}`,
    });
  } catch (err) {
    const error = err.message.includes("Failed to fetch") ? HELPER_OFF : err.message;
    const entry = { success: false, saveId, url, note, kind, error, payload, timestamp: new Date().toISOString() };
    await chrome.storage.local.set({ lastSaveResult: entry });
    broadcast({ type: "SAVE_STATUS", state: "error", saveId, error, result: entry });

    chrome.notifications.create(saveId, {
      type: "basic",
      iconUrl: "icons/icon128.png",
      title: "Brain Vault couldn’t save this",
      message: error,
    });
  }
}

// Send message to side panel (silently fails if panel is closed)
function broadcast(msg) {
  chrome.runtime.sendMessage(msg).catch(() => {});
}

async function addToHistory(entry) {
  const { history = [] } = await chrome.storage.local.get("history");
  history.unshift(entry);
  if (history.length > 100) history.length = 100;
  await chrome.storage.local.set({ history });
}

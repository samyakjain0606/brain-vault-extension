// Injected on demand by the side panel ("Select area").
// Draws a drag-to-select overlay, then reports the rectangle back in CSS pixels.
// The overlay removes itself before reporting so it never shows up in the capture.

(() => {
  if (window.__bvSelectCancel) window.__bvSelectCancel();

  const root = document.createElement("div");
  root.setAttribute("data-brain-vault", "");
  root.style.cssText =
    "position:fixed;inset:0;z-index:2147483647;cursor:crosshair;background:rgba(24,24,22,.38);user-select:none;";

  const box = document.createElement("div");
  box.style.cssText =
    "position:fixed;display:none;pointer-events:none;border:1.5px solid #fff;border-radius:4px;" +
    "box-shadow:0 0 0 100vmax rgba(24,24,22,.38),0 0 0 1px rgba(0,0,0,.25) inset;";

  const hint = document.createElement("div");
  hint.textContent = "Drag to select an area. Esc to cancel.";
  hint.style.cssText =
    "position:fixed;top:16px;left:50%;transform:translateX(-50%);pointer-events:none;" +
    "font:500 13px/1 -apple-system,BlinkMacSystemFont,Inter,sans-serif;color:#2A2A27;background:#fff;" +
    "padding:9px 14px;border-radius:999px;box-shadow:0 8px 24px rgba(0,0,0,.18);";

  const size = document.createElement("div");
  size.style.cssText =
    "position:fixed;display:none;pointer-events:none;font:500 11px/1 ui-monospace,Menlo,monospace;" +
    "color:#fff;background:#7466E8;padding:4px 6px;border-radius:5px;";

  root.append(box, hint, size);
  document.documentElement.appendChild(root);

  let start = null;
  let rect = null;

  const clamp = (v, max) => Math.max(0, Math.min(v, max));

  function onDown(e) {
    if (e.button !== 0) return;
    e.preventDefault();
    start = { x: clamp(e.clientX, innerWidth), y: clamp(e.clientY, innerHeight) };
    root.style.background = "transparent";
    box.style.display = "block";
    size.style.display = "block";
    hint.style.display = "none";
    onMove(e);
  }

  function onMove(e) {
    if (!start) return;
    const x2 = clamp(e.clientX, innerWidth);
    const y2 = clamp(e.clientY, innerHeight);
    rect = {
      x: Math.min(start.x, x2),
      y: Math.min(start.y, y2),
      w: Math.abs(x2 - start.x),
      h: Math.abs(y2 - start.y),
    };
    Object.assign(box.style, { left: rect.x + "px", top: rect.y + "px", width: rect.w + "px", height: rect.h + "px" });
    size.textContent = `${Math.round(rect.w)} × ${Math.round(rect.h)}`;
    Object.assign(size.style, { left: rect.x + "px", top: Math.max(0, rect.y - 22) + "px" });
  }

  function onUp() {
    if (!start) return;
    const picked = rect && rect.w >= 12 && rect.h >= 12 ? rect : null;
    finish(picked ? { rect: picked } : { cancelled: true, reason: "too-small" });
  }

  function onKey(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      finish({ cancelled: true });
    }
  }

  function cleanup() {
    root.remove();
    removeEventListener("keydown", onKey, true);
    delete window.__bvSelectCancel;
  }

  function finish(result) {
    cleanup();
    // Wait two frames so the overlay is gone from the screen before the panel captures.
    requestAnimationFrame(() =>
      requestAnimationFrame(() =>
        chrome.runtime.sendMessage({
          type: "BV_AREA",
          ...result,
          viewport: { w: innerWidth, h: innerHeight },
        })
      )
    );
  }

  root.addEventListener("mousedown", onDown);
  root.addEventListener("mousemove", onMove);
  root.addEventListener("mouseup", onUp);
  addEventListener("keydown", onKey, true);
  window.__bvSelectCancel = cleanup;
})();

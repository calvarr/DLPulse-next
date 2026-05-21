/* global fetch */

const THEME_ICON_NAMES = [
  "chromecast",
  "download",
  "search",
  "play",
  "refresh",
  "rename",
  "delete",
  "folder",
  "close",
  "stop",
  "playpause",
  "repeat",
  "shuffle",
  "save",
  "check",
  "upgrade",
  "copy",
  "link",
  "settings",
  "library",
  "donate",
  "credits",
  "file",
];

const THEME_ICONS = Object.fromEntries(
  THEME_ICON_NAMES.map((name) => [
    name,
    { dark: `/static/${name}-dark.svg`, light: `/static/${name}-light.svg` },
  ])
);
THEME_ICONS.app = {
  dark: "/static/dlpulse_icon.svg",
  light: "/static/dlpulse_icon_light.svg",
};

function appIconUrl() {
  return themedIconUrl("app");
}

function currentUiTheme() {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

function themedIconUrl(kind) {
  const pack = THEME_ICONS[kind];
  if (!pack) return THEME_ICONS.app.dark;
  return pack[currentUiTheme()] || pack.dark;
}

function createThemedIcon(kind, className = "btn-icon") {
  const im = document.createElement("img");
  im.className = className;
  im.src = themedIconUrl(kind);
  im.alt = "";
  im.setAttribute("data-themed-icon", kind);
  return im;
}

function updateThemedIcons() {
  document.querySelectorAll("img[data-themed-icon]").forEach((im) => {
    const kind = im.getAttribute("data-themed-icon");
    if (kind) im.src = themedIconUrl(kind);
  });
  const favicon = document.querySelector('link[rel="icon"][type="image/svg+xml"]');
  if (favicon) favicon.href = appIconUrl();
}

function setButtonIconLabel(btn, label) {
  if (!btn) return;
  const icon = btn.querySelector("img[data-themed-icon]");
  btn.textContent = "";
  if (icon) btn.appendChild(icon);
  if (label) btn.appendChild(document.createTextNode(" " + label));
}

function makeIconButton(kind, label, className = "ghost") {
  const b = document.createElement("button");
  b.type = "button";
  b.className = `${className} btn-with-icon`.trim();
  b.appendChild(createThemedIcon(kind));
  if (label) b.appendChild(document.createTextNode(" " + label));
  return b;
}

function initStaticButtonIcons() {
  document.querySelectorAll("button[data-btn-icon]").forEach((btn) => {
    const kind = btn.getAttribute("data-btn-icon");
    if (!kind) return;
    const label = btn.getAttribute("data-btn-label");
    const text =
      label != null && label !== ""
        ? label
        : label === ""
          ? ""
          : btn.textContent.trim();
    btn.classList.add("btn-with-icon");
    if (btn.classList.contains("btn-cast-row") === false && kind === "chromecast") {
      btn.classList.add("btn-cast-row");
    }
    btn.textContent = "";
    btn.appendChild(createThemedIcon(kind));
    if (text) btn.appendChild(document.createTextNode(" " + text));
  });
}

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.ok === false) throw new Error(j.error || r.statusText || "Request failed");
  return j;
}

function $(id) {
  return document.getElementById(id);
}

function setStatus(el, text, cls) {
  el.textContent = text || "";
  el.className = "status" + (cls ? " " + cls : "");
}

let formatPresets = [];
/** @type {string[]} */
let _internalRelayQueue = [];
/** @type {string[]} Display titles parallel to `_internalRelayQueue`. */
let _internalRelayTitles = [];
/** @type {string[]} Original URL order for this session (unshuffle). */
let _internalRelayQueueBase = [];
/** @type {string[]} Original titles for unshuffle. */
let _internalRelayTitlesBase = [];
let _internalRelayIdx = 0;
/** @type {0|1|2} 0 off, 1 all, 2 one — matches Chromecast queue repeat. */
let _internalRepeatCycle = 0;
let _internalShuffleOn = false;
const _INTERNAL_REPEAT_LABELS = ["off", "all", "one"];
/** @type {(() => void) | null} */
let _onInternalPlayerEnded = null;
/** @type {string|null} */
let lastCastMediaToken = null;
/** @type {{ cast_stream_url: string, label: string }[]} */
let lastRemoteCastItems = [];
let lastCcLanIp = "";
let lastCcStreamPort = 0;
let ccShuffleOn = false;
/** @type {ReturnType<typeof setInterval> | null} */
let ccPollTimer = null;
let ccSeekProgrammatic = false;
/** @type {"none"|"search"|"playlist"} */
let activeResultKind = "none";
let sessionOutputDir = null;
let playbackMode = "internal";
const SHOW_ALL_FILES_KEY = "dlpulse_show_all_files";
/** @type {Record<string, string>} Fallback when ``localStorage`` is unavailable (pywebview). */
const _uiPrefMem = Object.create(null);

function uiPrefGet(key) {
  try {
    if (typeof localStorage !== "undefined" && localStorage != null) {
      return localStorage.getItem(key);
    }
  } catch (_) {
    /* SecurityError or missing in embedded WebView */
  }
  return _uiPrefMem[key] ?? null;
}

function uiPrefSet(key, value) {
  try {
    if (typeof localStorage !== "undefined" && localStorage != null) {
      localStorage.setItem(key, value);
      return;
    }
  } catch (_) {
    /* ignore */
  }
  _uiPrefMem[key] = value;
}

function showAllFilesEnabled() {
  return uiPrefGet(SHOW_ALL_FILES_KEY) === "1";
}

function syncShowAllFilesCheckboxes() {
  const on = showAllFilesEnabled();
  const lib = $("lib-show-all-files");
  const fs = $("fs-show-all-files");
  if (lib) lib.checked = on;
  if (fs) fs.checked = on;
}

function setShowAllFiles(on) {
  uiPrefSet(SHOW_ALL_FILES_KEY, on ? "1" : "0");
  syncShowAllFilesCheckboxes();
}

function initShowAllFilesPreference() {
  syncShowAllFilesCheckboxes();
  const onShowAllChange = async () => {
    const lib = $("lib-show-all-files");
    setShowAllFiles(!!lib?.checked);
    try {
      await refreshLibrary();
    } catch (e) {
      setStatus($("lib-status"), e.message, "error");
    }
    const overlay = $("fs-browser");
    if (overlay && !overlay.hidden && fsBrowserState.currentPath) {
      fsLoadBrowse(fsBrowserState.currentPath).catch((err) => fsSetError(err.message));
    }
  };
  $("lib-show-all-files")?.addEventListener("change", onShowAllChange);
  $("fs-show-all-files")?.addEventListener("change", onShowAllChange);
}

function titleFromStreamUrl(url) {
  try {
    const u = new URL(url, window.location.origin);
    const seg = decodeURIComponent(u.pathname.split("/").pop() || "");
    if (seg && seg !== "media") return seg;
  } catch (_) {
    /* ignore */
  }
  return "";
}

function normalizeRelayTitles(urls, titles) {
  const list = (urls || []).map((u) => String(u).trim()).filter(Boolean);
  const raw = Array.isArray(titles) ? titles : [];
  return list.map((u, i) => {
    const t = String(raw[i] || "").trim();
    return t || titleFromStreamUrl(u) || `Track ${i + 1}`;
  });
}

function updatePlayerNowPlaying() {
  const el = $("player-now-playing");
  if (!el) return;
  const len = _internalRelayQueue.length;
  if (!len || _internalRelayIdx < 0 || _internalRelayIdx >= len) {
    el.textContent = "";
    el.hidden = true;
    return;
  }
  const title = (_internalRelayTitles[_internalRelayIdx] || "").trim() || "Playing";
  el.textContent = len > 1 ? `${title} (${_internalRelayIdx + 1}/${len})` : title;
  el.hidden = false;
  el.title = title;
}

function clearPlayerNowPlaying() {
  const el = $("player-now-playing");
  if (!el) return;
  el.textContent = "";
  el.hidden = true;
  el.removeAttribute("title");
}

function syncPlayerNoCoverPlaceholder(v) {
  const ph = $("player-audio-brand");
  if (!ph || !v) return;
  const hasCoverOrVideo = v.videoWidth > 0 && v.videoHeight > 0;
  if (hasCoverOrVideo) ph.classList.remove("is-visible");
  else ph.classList.add("is-visible");
}

/** @type {(() => void) | null} */
let _playerPhMetaFn = null;
/** @type {(() => void) | null} */
let _playerPhUpdateFn = null;
/** @type {(() => void) | null} */
let _playerPhLoadStartFn = null;

function attachInternalPlayerHooks() {
  const v = $("v");
  if (!v) return;
  if (_playerPhMetaFn) v.removeEventListener("loadedmetadata", _playerPhMetaFn);
  if (_playerPhUpdateFn) {
    v.removeEventListener("playing", _playerPhUpdateFn);
    v.removeEventListener("loadeddata", _playerPhUpdateFn);
  }
  if (_playerPhLoadStartFn) v.removeEventListener("loadstart", _playerPhLoadStartFn);
  _playerPhMetaFn = () => syncPlayerNoCoverPlaceholder($("v"));
  _playerPhUpdateFn = () => syncPlayerNoCoverPlaceholder($("v"));
  _playerPhLoadStartFn = () => $("player-audio-brand")?.classList.remove("is-visible");
  v.addEventListener("loadstart", _playerPhLoadStartFn);
  v.addEventListener("loadedmetadata", _playerPhMetaFn);
  v.addEventListener("loadeddata", _playerPhUpdateFn);
  v.addEventListener("playing", _playerPhUpdateFn);
}

function detachInternalPlayerHooks() {
  const v = $("v");
  if (!v) return;
  if (_playerPhMetaFn) v.removeEventListener("loadedmetadata", _playerPhMetaFn);
  if (_playerPhUpdateFn) {
    v.removeEventListener("playing", _playerPhUpdateFn);
    v.removeEventListener("loadeddata", _playerPhUpdateFn);
  }
  if (_playerPhLoadStartFn) v.removeEventListener("loadstart", _playerPhLoadStartFn);
  _playerPhMetaFn = null;
  _playerPhUpdateFn = null;
  _playerPhLoadStartFn = null;
}

function hideInternalPlayerPlaceholder() {
  $("player-audio-brand")?.classList.remove("is-visible");
}

function thumbUrl(h) {
  const t = (h.thumbnail || "").trim();
  if (t) return t;
  const id = (h.id || "").trim();
  if (id.length === 11 && !id.startsWith("UC")) return "https://i.ytimg.com/vi/" + id + "/hqdefault.jpg";
  return "";
}

function appendAppIconThumb(td) {
  const im = document.createElement("img");
  im.className = "thumb thumb-app-icon";
  im.src = appIconUrl();
  im.alt = "";
  im.setAttribute("data-themed-icon", "app");
  td.appendChild(im);
}

function makeCastIconButton() {
  const b = makeIconButton("chromecast", "", "ghost btn-cast-row");
  b.setAttribute("aria-label", "Chromecast");
  return b;
}

function updateSessionLabel() {
  const el = $("session-lbl");
  if (!el) return;
  if (sessionOutputDir) {
    el.textContent = sessionOutputDir;
    el.hidden = false;
  } else {
    el.textContent = "";
    el.hidden = true;
  }
}

function applyTheme(theme) {
  const t = theme === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", t);
  updateThemedIcons();
}

function closePresetDropdown() {
  const list = $("preset-dd-list");
  const btn = $("preset-dd-btn");
  if (list) list.hidden = true;
  if (btn) btn.setAttribute("aria-expanded", "false");
}

function openPresetDropdown() {
  const list = $("preset-dd-list");
  const btn = $("preset-dd-btn");
  if (list) list.hidden = false;
  if (btn) btn.setAttribute("aria-expanded", "true");
}

function updatePresetSelectionHighlight() {
  const hid = $("preset");
  const v = hid ? hid.value : "";
  document.querySelectorAll(".preset-dd-option").forEach((b) => {
    b.setAttribute("aria-selected", b.dataset.index === v ? "true" : "false");
  });
}

function setPresetValue(index, label) {
  const hid = $("preset");
  const txt = $("preset-dd-btn-text");
  if (hid) hid.value = String(index);
  if (txt && label != null) txt.textContent = label;
  updatePresetSelectionHighlight();
}

function buildPresetDropdown() {
  const list = $("preset-dd-list");
  if (!list) return;
  list.innerHTML = "";
  formatPresets.forEach((p) => {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.type = "button";
    b.className = "preset-dd-option";
    b.setAttribute("role", "option");
    b.dataset.index = String(p.index);
    b.textContent = p.label;
    b.addEventListener("click", (ev) => {
      ev.stopPropagation();
      setPresetValue(p.index, p.label);
      closePresetDropdown();
    });
    li.appendChild(b);
    list.appendChild(li);
  });
  if (formatPresets.length) {
    const p0 = formatPresets[0];
    setPresetValue(p0.index, p0.label);
  } else {
    const hid = $("preset");
    const txt = $("preset-dd-btn-text");
    if (hid) hid.value = "0";
    if (txt) txt.textContent = "—";
    updatePresetSelectionHighlight();
  }
}

function renderResultRows(items) {
  const tb = $("hits-body");
  tb.innerHTML = "";
  (items || []).forEach((h) => {
    const tr = document.createElement("tr");
    const thumb = thumbUrl(h);
    const tdThumb = document.createElement("td");
    if (thumb) {
      const im = document.createElement("img");
      im.className = "thumb";
      im.src = thumb;
      im.alt = "";
      im.referrerPolicy = "no-referrer";
      im.onerror = () => {
        im.onerror = null;
        im.src = appIconUrl();
        im.classList.add("thumb-app-icon");
        im.setAttribute("data-themed-icon", "app");
      };
      tdThumb.appendChild(im);
    } else {
      appendAppIconThumb(tdThumb);
    }
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "hit-cb";
    const title = h.title_display || h.title || "";
    const u = (h.url || "").trim();
    cb.setAttribute("data-url", u);
    cb.setAttribute("data-title", title);
    const td0 = document.createElement("td");
    td0.appendChild(cb);
    const td1 = document.createElement("td");
    td1.textContent = title;
    const tdAct = document.createElement("td");
    tdAct.className = "hit-actions";
    const bp = makeIconButton("play", "Play");
    bp.addEventListener("click", async () => {
      if (!u) return;
      try {
        await playHitUrlsInPlayer([u], [title]);
        setStatus($("search-status"), "Playing.", "ok");
      } catch (e) {
        setStatus($("search-status"), e.message, "error");
      }
    });
    const bCast = makeCastIconButton();
    bCast.addEventListener("click", async () => {
      if (!u) return;
      try {
        setStatus($("search-status"), "Preparing Chromecast…", "");
        await prepareSearchStreamsForCast([{ url: u, title }]);
        setStatus($("search-status"), "Ready.", "ok");
      } catch (e) {
        setStatus($("search-status"), e.message, "error");
      }
    });
    tdAct.appendChild(bp);
    tdAct.appendChild(bCast);
    tr.appendChild(tdThumb);
    tr.appendChild(td0);
    tr.appendChild(td1);
    tr.appendChild(tdAct);
    tb.appendChild(tr);
  });
  const all = $("results-sel-all");
  if (all) all.checked = false;
}

async function apiResolve(body) {
  const r = await fetch("/api/resolve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (j.ok === false) throw new Error(j.error || "Resolve failed");
  return j;
}

async function runResolve() {
  const q = $("q").value.trim();
  if (!q) {
    setStatus($("search-status"), "Enter search words or a URL.", "error");
    return;
  }
  setStatus($("search-status"), "Working…");
  try {
    const yt = $("src-yt").checked;
    const sc = $("src-sc").checked;
    const r = await apiResolve({ text: q, youtube: yt, soundcloud: sc, max_per_source: 12 });
    if (r.kind === "empty" || r.kind === "error") {
      activeResultKind = "none";
      renderResultRows([]);
      setStatus($("search-status"), r.message || r.error || "", r.ok === false ? "error" : "");
      return;
    }
    activeResultKind = r.kind === "playlist" ? "playlist" : "search";
    renderResultRows(r.items || []);
    setStatus($("search-status"), r.message || "", "ok");
  } catch (e) {
    activeResultKind = "none";
    renderResultRows([]);
    setStatus($("search-status"), e.message, "error");
  }
}

function selectedHitUrls() {
  const out = [];
  document.querySelectorAll("#hits-body input[type=checkbox]:checked").forEach((cb) => {
    const u = cb.getAttribute("data-url");
    if (u) out.push(u);
  });
  return out;
}

/** @returns {{ url: string, title: string }[]} */
function selectedSearchHits() {
  const out = [];
  document.querySelectorAll("#hits-body input.hit-cb:checked").forEach((cb) => {
    const u = cb.getAttribute("data-url");
    if (!u) return;
    out.push({ url: u, title: (cb.getAttribute("data-title") || "").trim() });
  });
  return out;
}

function switchToCastTab() {
  document.querySelector('nav.tabs button[data-tab="cast"]')?.click();
}

/** Discover Chromecasts on the LAN; updates `cc-status`, device list, LAN line, stream URLs field. */
async function runChromecastDiscoverWithUi() {
  $("cc-status").textContent = "Discovering…";
  const w = parseFloat($("set-castw").value) || 3;
  const r = await api("/api/chromecast/discover", { method: "POST", body: { wait_s: w } });
  lastCcLanIp = r.lan_ip || "";
  lastCcStreamPort = r.stream_port || 0;
  rebuildCcDeviceList(r.devices || []);
  $("cc-lan").textContent =
    (r.lan_ip || "") + (r.stream_port ? `:${r.stream_port}` : "");
  updateCcStreamUrlsField();
  $("cc-status").textContent = "Found " + (r.devices?.length || 0) + " device(s).";
  return r;
}

/**
 * Open the Chromecast tab and run device discovery (used from Player, Search, Library).
 * @param {{ rethrow?: boolean }} [opts] — if `rethrow`, API errors propagate after `cc-status` is set.
 */
async function switchToCastTabAndDiscover(opts = {}) {
  const { rethrow = false } = opts;
  switchToCastTab();
  try {
    await runChromecastDiscoverWithUi();
  } catch (e) {
    $("cc-status").textContent = e.message || String(e);
    if (rethrow) throw e;
  }
}

function formatCcHms(sec) {
  const s = Math.max(0, Math.floor(Number(sec) || 0));
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  const r = s % 60;
  if (h) return `${h}:${String(m % 60).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${m}:${String(r).padStart(2, "0")}`;
}

function ccMediaUrlFromToken(token) {
  if (!token || !lastCcLanIp || !lastCcStreamPort) return "";
  const parts = String(token)
    .replace(/\\/g, "/")
    .split("/")
    .filter(Boolean);
  return `http://${lastCcLanIp}:${lastCcStreamPort}/media/` + parts.map((p) => encodeURIComponent(p)).join("/");
}

function updateCcStreamUrlsField() {
  const ta = $("cc-stream-urls");
  if (!ta) return;
  const lines = [];
  if (lastRemoteCastItems.length) {
    lastRemoteCastItems.forEach((it) => {
      if (it.cast_stream_url) lines.push(it.cast_stream_url);
    });
  } else if (lastCastMediaToken) {
    const u = ccMediaUrlFromToken(lastCastMediaToken);
    if (u) lines.push(u);
  }
  ta.value = lines.join("\n");
}

function selectedCcIndices() {
  const out = [];
  document.querySelectorAll("#cc-dev-list input.cc-dev-cb:checked").forEach((cb) => {
    const i = parseInt(cb.getAttribute("data-index") || "", 10);
    if (!Number.isNaN(i)) out.push(i);
  });
  return out;
}

function rebuildCcDeviceList(devices) {
  const wrap = $("cc-dev-list");
  if (!wrap) return;
  wrap.innerHTML = "";
  (devices || []).forEach((d) => {
    const row = document.createElement("label");
    row.className = "cc-dev-row";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "cc-dev-cb";
    cb.setAttribute("data-index", String(d.index));
    const div = document.createElement("div");
    const t = document.createElement("div");
    t.textContent = d.name || "—";
    const sub = document.createElement("div");
    sub.className = "cc-dev-meta";
    sub.textContent = (d.model || "—") + " · #" + d.index;
    div.appendChild(t);
    div.appendChild(sub);
    row.appendChild(cb);
    row.appendChild(div);
    wrap.appendChild(row);
  });
  const all = $("cc-dev-all");
  if (all) all.checked = false;
  updateCcPickHint();
}

function updateCcPickHint() {
  const el = $("cc-pick-hint");
  if (!el) return;
  const n = document.querySelectorAll("#cc-dev-list input.cc-dev-cb:checked").length;
  const m = document.querySelectorAll("#cc-dev-list input.cc-dev-cb").length;
  if (!m || !n) {
    el.textContent = "";
    el.hidden = true;
    return;
  }
  el.textContent = `${n}/${m}`;
  el.hidden = false;
}

function ccCastBodyBase() {
  return { device_indices: selectedCcIndices() };
}

function startCcProgressPoll() {
  stopCcProgressPoll();
  ccPollTimer = setInterval(async () => {
    try {
      const r = await api("/api/chromecast/progress", { method: "POST", body: ccCastBodyBase() });
      const t = $("cc-time-lbl");
      const seek = $("cc-seek");
      if (!t || !seek) return;
      const cur = r.current || 0;
      const dur = r.duration;
      if (typeof dur === "number" && dur > 0) {
        t.textContent = `${formatCcHms(cur)} / ${formatCcHms(dur)}`;
        seek.max = dur;
        ccSeekProgrammatic = true;
        seek.value = String(Math.min(Math.max(cur, 0), dur));
        ccSeekProgrammatic = false;
      } else {
        t.textContent = `${formatCcHms(cur)} / —`;
      }
      const bpp = $("btn-cc-play-pause");
      if (bpp) setButtonIconLabel(bpp, r.paused ? "Resume" : "Pause");
    } catch (_) {
      /* ignore poll errors */
    }
  }, 1500);
}

function stopCcProgressPoll() {
  if (ccPollTimer) {
    clearInterval(ccPollTimer);
    ccPollTimer = null;
  }
}

/**
 * @param {{ url: string, title: string }[]} hits
 */
async function prepareSearchStreamsForCast(hits) {
  if (!hits.length) return;
  const urls = hits.map((h) => h.url);
  const labels = hits.map((h) => h.title);
  const r = await api("/api/chromecast/prepare_search_streams", {
    method: "POST",
    body: { urls, labels },
  });
  lastRemoteCastItems = r.prepared || [];
  lastCastMediaToken = null;
  $("cc-status").textContent =
    lastRemoteCastItems.length > 0 ? `Ready (${lastRemoteCastItems.length}).` : "";
  updateCcStreamUrlsField();
  await switchToCastTabAndDiscover();
}

function selectedLibPaths() {
  const out = [];
  document.querySelectorAll("#lib-body .lib-cb:checked").forEach((cb) => {
    const p = cb.getAttribute("data-path");
    if (p) out.push(p);
  });
  return out;
}

async function syncLibrarySession() {
  try {
    await api("/api/library/session", {
      method: "POST",
      body: { path: sessionOutputDir },
    });
    await refreshLibrary();
  } catch (e) {
    setStatus($("lib-status"), e.message, "error");
  }
}

function setLibEmptyHint(hint) {
  const box = $("lib-empty");
  if (!box) return;
  box.innerHTML = "";
  if (!hint) {
    box.style.display = "none";
    return;
  }
  box.style.display = "flex";
  box.style.alignItems = "center";
  box.style.gap = "10px";
  const icon = document.createElement("img");
  icon.className = "app-icon app-icon-sm";
  icon.src = appIconUrl();
  icon.alt = "";
  icon.setAttribute("data-themed-icon", "app");
  box.appendChild(icon);
  const t = document.createElement("strong");
  t.textContent = hint.title || "";
  box.appendChild(t);
  (hint.lines || []).forEach((ln) => {
    box.appendChild(document.createElement("br"));
    box.appendChild(document.createTextNode(String(ln)));
  });
}

function applyLibraryFilter() {
  const inp = $("lib-filter");
  const q = (inp?.value || "").trim().toLowerCase();
  document.querySelectorAll("#lib-body tr").forEach((tr) => {
    const hay = tr.dataset.filterText || "";
    tr.style.display = !q || hay.includes(q) ? "" : "none";
  });
}

document.querySelectorAll("nav.tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav.tabs button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const tab = btn.getAttribute("data-tab");
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    $(`panel-${tab}`).classList.add("active");
    if (tab === "cast") startCcProgressPoll();
    else stopCcProgressPoll();
  });
});

async function init() {
  initStaticButtonIcons();
  syncInternalQueueControlButtons();
  initShowAllFilesPreference();
  try {
    const v = await api("/api/version");
    applyBuildBadge(v);
    applyVersionPanel(v);
  } catch (_) {
    $("ver-badge").textContent = "";
  }
  await loadSettingsUi();
  try {
    const pr = await api("/api/format_presets");
    formatPresets = pr.presets || [];
    buildPresetDropdown();
  } catch (e) {
    setStatus($("search-status"), String(e.message), "error");
  }
  await checkGithub();
  void refreshLibrary().catch((e) => {
    const el = $("lib-status");
    if (el) el.textContent = e.message || String(e);
  });
  updateSessionLabel();
}

async function loadSettingsUi() {
  const s = await api("/api/settings");
  $("set-dir").value = s.download_dir || "";
  if ($("set-launch")) {
    const lm = (s.ui_launch_mode || "native").toLowerCase();
    $("set-launch").value = lm === "browser" ? "browser" : "native";
  }
  $("set-vp").value = s.video_player || "";
  $("set-ap").value = s.audio_player || "";
  $("set-mode").value = s.playback_mode || "internal";
  $("set-castw").value = String(s.cast_discovery_wait_s ?? 3);
  const par = String(s.download_parallel ?? 1);
  if ($("set-dl-parallel")) $("set-dl-parallel").value = ["1", "2", "3", "5"].includes(par) ? par : "1";
  if ($("set-dl-rate")) $("set-dl-rate").value = String(s.download_rate_limit_mbps ?? 0);
  if ($("set-aria2")) $("set-aria2").checked = !!s.use_aria2c;
  if ($("set-aria2-x")) $("set-aria2-x").value = String(s.aria2c_connections ?? 16);
  const hint = $("set-aria2-hint");
  if (hint) {
    if (s.aria2c_bundled) {
      hint.textContent = "aria2c is bundled with this build.";
    } else if (s.aria2c_available) {
      hint.textContent = "aria2c found on PATH (system install).";
    } else {
      hint.textContent =
        "aria2c not available. Install the aria2 package, or use a release build that bundles it.";
    }
  }
  const th = s.ui_theme === "light" ? "light" : "dark";
  $("set-theme").value = th;
  applyTheme(th);
  playbackMode = (s.playback_mode || "internal").toLowerCase();
  const modeHint = $("set-mode-hint");
  if (modeHint && s.linux_runtime?.packaged) {
    const lr = s.linux_runtime;
    if (!lr.in_app_video) {
      modeHint.textContent =
        "In-app video needs GStreamer (gst-plugins-base/good) or use External player with mpv.";
    } else {
      modeHint.textContent = "";
    }
  } else if (modeHint) {
    modeHint.textContent = "";
  }
}

const DEFAULT_RELEASES_URL = "https://github.com/calvarr/DLPulse-next/releases";

function applyBuildBadge(v) {
  const badge = $("ver-badge");
  if (!badge) return;
  if (v.release_tag) {
    badge.textContent = v.release_tag.startsWith("v") ? v.release_tag : `v${v.release_tag}`;
    badge.title = v.commit ? `Build ${v.commit.slice(0, 7)}` : "DLPulse Next release";
  } else if (v.commit) {
    badge.textContent = v.commit.slice(0, 7);
    badge.title = "Continuous build — Settings → Check for updates";
  } else {
    badge.textContent = "";
    badge.title = "";
  }
}

function applyVersionPanel(v) {
  const relRow = $("set-app-release-row");
  const relEl = $("set-app-release");
  if (v.release_tag && relRow && relEl) {
    relRow.hidden = false;
    relEl.textContent = v.release_tag.startsWith("v") ? v.release_tag : `v${v.release_tag}`;
  } else if (relRow) {
    relRow.hidden = true;
  }
  const buildEl = $("set-app-build");
  if (buildEl) {
    buildEl.textContent = v.commit
      ? `Build commit: ${v.commit.slice(0, 7)}`
      : "Build commit: unknown (dev install)";
  }
  const bundledEl = $("set-app-bundled");
  if (bundledEl && v.bundled) {
    const parts = [];
    if (v.bundled.ffmpeg) parts.push("ffmpeg bundled");
    if (v.bundled.aria2c_bundled) parts.push("aria2c bundled");
    else if (v.bundled.aria2c) parts.push("aria2c (system)");
    if (v.bundled.ytdlp) parts.push(`yt-dlp ${v.bundled.ytdlp}`);
    bundledEl.textContent = parts.length ? parts.join(" · ") : "";
  }
}

function showUpdateBanner(g) {
  const b = $("gh-banner");
  const openBtn = $("gh-open-releases");
  if (!b) return;
  if (g.show_banner && g.message) {
    $("gh-msg").textContent = g.message;
    b.classList.add("show");
    b.dataset.dismissKey = g.dismiss_key || g.remote_main_sha || "";
    const releasesUrl = g.releases_url || g.release_page_url || DEFAULT_RELEASES_URL;
    b.dataset.releasesUrl = releasesUrl;
    if (openBtn) {
      openBtn.hidden = false;
      openBtn.onclick = () => window.open(releasesUrl, "_blank", "noopener,noreferrer");
    }
  } else {
    b.classList.remove("show");
    if (openBtn) openBtn.hidden = true;
  }
}

async function checkGithub() {
  try {
    const g = await api("/api/github_update");
    showUpdateBanner(g);
    return g;
  } catch (_) {
    $("gh-banner")?.classList.remove("show");
    return null;
  }
}

$("gh-dismiss")?.addEventListener("click", async () => {
  const key = $("gh-banner")?.dataset.dismissKey || "";
  await api("/api/github_update/dismiss", { method: "POST", body: { dismiss_key: key, sha: key } });
  $("gh-banner").classList.remove("show");
});

$("btn-check-app-update")?.addEventListener("click", async () => {
  const st = $("set-app-update-status");
  if (st) {
    st.textContent = "Checking GitHub Releases…";
    st.className = "status";
  }
  try {
    const g = await checkGithub();
    if (!st) return;
    if (g?.show_banner) {
      st.textContent = g.message;
      st.className = "status ok";
    } else if (g?.latest_tag && g.release_tag) {
      st.textContent = `You are up to date (${g.release_tag}; latest release: ${g.latest_tag}).`;
      st.className = "status ok";
    } else if (g?.latest_tag) {
      st.textContent = `Continuous build — latest stable release: ${g.latest_tag}.`;
      st.className = "status";
    } else {
      st.textContent = "No newer release found (or GitHub is unreachable).";
      st.className = "status";
    }
  } catch (e) {
    if (st) {
      st.textContent = e.message || String(e);
      st.className = "status error";
    }
  }
});

$("btn-open-releases")?.addEventListener("click", () => {
  window.open(DEFAULT_RELEASES_URL, "_blank", "noopener,noreferrer");
});

$("set-save").addEventListener("click", async () => {
  try {
    await api("/api/settings", {
      method: "POST",
      body: {
        download_dir: $("set-dir").value,
        ui_launch_mode: $("set-launch")?.value || "native",
        video_player: $("set-vp").value,
        audio_player: $("set-ap").value,
        playback_mode: $("set-mode").value,
        cast_discovery_wait_s: parseFloat($("set-castw").value) || 3,
        ui_theme: $("set-theme").value,
        download_parallel: parseInt($("set-dl-parallel")?.value || "1", 10) || 1,
        download_rate_limit_mbps: parseFloat($("set-dl-rate")?.value || "0") || 0,
        use_aria2c: !!$("set-aria2")?.checked,
        aria2c_connections: parseInt($("set-aria2-x")?.value || "16", 10) || 16,
      },
    });
    await loadSettingsUi();
    await refreshLibrary();
    alert("Saved.");
  } catch (e) {
    alert(e.message);
  }
});

$("set-theme").addEventListener("change", () => {
  applyTheme($("set-theme").value);
});

$("btn-resolve").addEventListener("click", () => runResolve());

$("q").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey) {
    ev.preventDefault();
    runResolve();
  }
});

$("results-sel-all").addEventListener("change", (ev) => {
  const on = ev.target.checked;
  document.querySelectorAll("#hits-body .hit-cb").forEach((cb) => {
    cb.checked = on;
  });
});

$("btn-pick-session").addEventListener("click", async () => {
  try {
    const s = await api("/api/settings");
    const start = sessionOutputDir || s.download_dir || "";
    const picked = await openFolderBrowser({
      initial: start,
      title: "Choose download folder",
      pickLabel: "Use this folder",
    });
    if (picked) {
      sessionOutputDir = picked;
      updateSessionLabel();
      await syncLibrarySession();
    }
  } catch (e) {
    alert(e.message);
  }
});

$("btn-play-sel-search").addEventListener("click", async () => {
  if (activeResultKind !== "search" && activeResultKind !== "playlist") {
    setStatus($("dl-status"), "Search with keywords or open a playlist/channel URL first.", "error");
    return;
  }
  const hits = selectedSearchHits();
  if (!hits.length) {
    setStatus($("dl-status"), "Tick one or more rows in the list above.", "error");
    return;
  }
  setStatus($("dl-status"), "Resolving stream…");
  try {
    await playHitUrlsInPlayer(
      hits.map((h) => h.url),
      hits.map((h) => h.title)
    );
    setStatus($("dl-status"), "Playing.", "ok");
  } catch (e) {
    setStatus($("dl-status"), e.message, "error");
  }
});

$("btn-cc-search-selected").addEventListener("click", async () => {
  if (activeResultKind !== "search" && activeResultKind !== "playlist") {
    setStatus($("dl-status"), "Search with keywords or open a playlist/channel URL first.", "error");
    return;
  }
  const hits = selectedSearchHits();
  if (!hits.length) {
    setStatus($("dl-status"), "Tick one or more rows in the list above.", "error");
    return;
  }
  setStatus($("dl-status"), "Preparing Chromecast playlist…");
  try {
    await prepareSearchStreamsForCast(hits);
    setStatus($("dl-status"), "Ready.", "ok");
  } catch (e) {
    setStatus($("dl-status"), e.message, "error");
  }
});

async function waitForDownloadJob(jobId, onProgress) {
  let st;
  do {
    await new Promise((x) => setTimeout(x, 400));
    st = await api("/api/download/" + jobId);
    const p = st.progress || {};
    if (onProgress) onProgress(p, st);
  } while (st.status === "running");
  if (st.status === "error") throw new Error(st.error || "Download failed");
  return st;
}

async function downloadOneUrl(url, bodyBase, slotLabel) {
  const r = await api("/api/download", {
    method: "POST",
    body: { ...bodyBase, url },
  });
  return waitForDownloadJob(r.job_id, (p) => {
    setStatus($("dl-status"), slotLabel + (p.message ? " — " + p.message : ""));
  });
}

async function downloadUrlsBatch(urls, bodyBase, parallel) {
  const prog = $("dl-progress");
  const total = urls.length;
  let done = 0;
  let next = 0;
  const updateOverall = () => {
    prog.value = Math.round((done / total) * 100);
  };

  async function worker() {
    while (true) {
      const i = next++;
      if (i >= total) break;
      const slot = `[${i + 1}/${total}]`;
      await downloadOneUrl(urls[i], bodyBase, slot);
      done += 1;
      updateOverall();
    }
  }

  const n = Math.max(1, Math.min(parallel, total, 5));
  setStatus($("dl-status"), `Downloading (up to ${n} at once)…`);
  await Promise.all(Array.from({ length: n }, () => worker()));
}

$("btn-download").addEventListener("click", async () => {
  if (activeResultKind !== "search" && activeResultKind !== "playlist") {
    setStatus($("dl-status"), "Search with keywords or open a playlist/channel URL first.", "error");
    return;
  }
  const urls = selectedHitUrls();
  if (!urls.length) {
    setStatus($("dl-status"), "Tick one or more rows in the list above.", "error");
    return;
  }
  const prog = $("dl-progress");
  prog.style.display = "block";
  prog.value = 0;
  setStatus($("dl-status"), "Preparing download…");
  const bodyBase = {
    format_preset_index: parseInt($("preset").value, 10),
    no_playlist: true,
    download_cover: $("dl-cover").checked,
  };
  if (sessionOutputDir) bodyBase.output_dir = sessionOutputDir;
  let parallel = 1;
  try {
    const s = await api("/api/settings");
    parallel = parseInt(String(s.download_parallel ?? 1), 10) || 1;
  } catch (_) {
    parallel = parseInt($("set-dl-parallel")?.value || "1", 10) || 1;
  }
  try {
    await downloadUrlsBatch(urls, bodyBase, parallel);
  } catch (e) {
    setStatus($("dl-status"), e.message, "error");
    prog.style.display = "none";
    return;
  }
  prog.value = 100;
  setStatus($("dl-status"), "Done.", "ok");
  await refreshLibrary();
});

async function refreshLibrary() {
  const libSt = $("lib-status");
  const tb0 = $("lib-body");
  const showPending = tb0 && tb0.childElementCount === 0;
  if (showPending && libSt) libSt.textContent = "Loading library…";
  try {
    const libQ = showAllFilesEnabled() ? "?show_all_files=1" : "";
    const r = await api("/api/library" + libQ);
    const hintEl = $("lib-cwd");
    const line = r.browsing && r.view_dir ? r.view_dir : r.downloads_dir || "";
    if (hintEl) {
      hintEl.textContent = line;
      hintEl.hidden = !line;
    }

    const items = r.items || [];
    setLibEmptyHint(items.length ? null : r.empty_hint || null);

    const tb = $("lib-body");
    tb.innerHTML = "";
    items.forEach((it) => {
    const tr = document.createElement("tr");
    const td0 = document.createElement("td");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "lib-cb";
    cb.setAttribute("data-path", it.path || "");
    td0.appendChild(cb);

    const td1 = document.createElement("td");
    td1.className = "lib-label";
    td1.textContent = it.label || "";

    const td2 = document.createElement("td");
    td2.style.fontSize = "0.8rem";
    td2.style.color = "var(--muted)";
    td2.textContent = it.subtitle || "";

    tr.appendChild(td0);
    tr.appendChild(td1);
    tr.appendChild(td2);
    tr.dataset.filterText = `${(it.label || "").toLowerCase()} ${(it.path || "").toLowerCase()}`;
    tb.appendChild(tr);
  });
    applyLibraryFilter();
    const allLib = $("lib-sel-all-cb");
    if (allLib) allLib.checked = false;
  } catch (e) {
    if (libSt) libSt.textContent = e.message || String(e);
    throw e;
  } finally {
    if (showPending && libSt && libSt.textContent === "Loading library…") libSt.textContent = "";
  }
}

$("lib-sel-all-cb").addEventListener("change", (ev) => {
  const on = ev.target.checked;
  document.querySelectorAll("#lib-body tr").forEach((tr) => {
    if (tr.style.display === "none") return;
    const cb = tr.querySelector(".lib-cb");
    if (cb) cb.checked = on;
  });
});

$("lib-refresh").addEventListener("click", () => refreshLibrary().catch((e) => alert(e.message)));

$("lib-filter")?.addEventListener("input", () => applyLibraryFilter());

$("lib-play").addEventListener("click", async () => {
  const items = selectedLibItems();
  if (!items.length) {
    setStatus($("lib-status"), "Select one or more files.", "error");
    return;
  }
  const paths = items.map((it) => it.path);
  try {
    if (playbackMode === "internal") {
      switchToPlayerTab();
      setStatus($("player-status"), "Loading from library…", "");
      const r = await api("/api/library/internal_stream_urls", {
        method: "POST",
        body: { paths, host: "127.0.0.1" },
      });
      await playRelayUrlList(r.urls || [], r.labels || items.map((it) => it.label));
      setStatus($("lib-status"), "Playing.", "ok");
      setStatus(
        $("player-status"),
        paths.length > 1 ? `Playing queue (${paths.length} files)…` : "Playing.",
        "ok"
      );
    } else {
      await api("/api/library/play", { method: "POST", body: { paths } });
      setStatus($("lib-status"), "Playback started (external / system player).", "ok");
    }
  } catch (e) {
    setStatus($("lib-status"), e.message, "error");
  }
});

$("lib-rename").addEventListener("click", async () => {
  const paths = selectedLibPaths();
  if (paths.length !== 1) {
    setStatus($("lib-status"), "Select exactly one file to rename.", "error");
    return;
  }
  const name = window.prompt("New file name (no path):", paths[0].split(/[/\\]/).pop() || "");
  if (name == null || !String(name).trim()) return;
  try {
    await api("/api/library/rename", { method: "POST", body: { path: paths[0], new_name: String(name).trim() } });
    setStatus($("lib-status"), "Renamed.", "ok");
    await refreshLibrary();
  } catch (e) {
    setStatus($("lib-status"), e.message, "error");
  }
});

$("lib-delete").addEventListener("click", async () => {
  const paths = selectedLibPaths();
  if (!paths.length) {
    setStatus($("lib-status"), "Select file(s) to delete.", "error");
    return;
  }
  if (!window.confirm(`Delete ${paths.length} file(s)? This cannot be undone.`)) return;
  try {
    const r = await api("/api/library/delete", { method: "POST", body: { paths } });
    const extra = r.error && r.deleted < paths.length ? " " + r.error : "";
    setStatus($("lib-status"), `Deleted ${r.deleted || 0}.${extra}`, r.deleted ? "ok" : "error");
    await refreshLibrary();
  } catch (e) {
    setStatus($("lib-status"), e.message, "error");
  }
});

$("lib-browse").addEventListener("click", async () => {
  try {
    const s = await api("/api/settings");
    const lib = await api("/api/library");
    const ini =
      (lib.browsing && lib.view_dir) || lib.downloads_dir || s.download_dir || "";
    const picked = await openFolderBrowser({
      initial: ini,
      title: "Choose folder to list",
      pickLabel: "Use this folder",
    });
    if (picked) {
      await api("/api/library/view", { method: "POST", body: { path: picked } });
      await refreshLibrary();
      setStatus($("lib-status"), "Browsing selected folder.", "ok");
    }
  } catch (e) {
    setStatus($("lib-status"), e.message, "error");
  }
});

$("lib-use-save").addEventListener("click", async () => {
  try {
    await api("/api/library/view", { method: "POST", body: { path: null } });
    await refreshLibrary();
    setStatus($("lib-status"), "Showing save folder from Settings (this folder only).", "ok");
  } catch (e) {
    setStatus($("lib-status"), e.message, "error");
  }
});

$("lib-cast-prep").addEventListener("click", async () => {
  const paths = selectedLibPaths();
  if (!paths.length) {
    setStatus($("lib-status"), "Select file(s) for Chromecast, then Prepare.", "error");
    return;
  }
  try {
    const r = await api("/api/library/cast_prepare", { method: "POST", body: { paths } });
    const first = (r.prepared || [])[0];
    lastCastMediaToken = first && first.token ? first.token : null;
    lastRemoteCastItems = [];
    setStatus($("lib-status"), "Ready.", "ok");
    updateCcStreamUrlsField();
    await switchToCastTabAndDiscover();
  } catch (e) {
    setStatus($("lib-status"), e.message, "error");
  }
});

function switchToPlayerTab() {
  document.querySelector('nav.tabs button[data-tab="player"]')?.click();
}

$("btn-player-cast").addEventListener("click", async () => {
  setStatus($("player-status"), "Opening Chromecast…", "");
  try {
    await switchToCastTabAndDiscover({ rethrow: true });
    setStatus($("player-status"), "", "ok");
  } catch (e) {
    setStatus($("player-status"), e.message || String(e), "error");
  }
});

$("btn-int-repeat").addEventListener("click", () => {
  if (!_internalRelayQueue.length) {
    setStatus($("player-status"), "Start playback first.", "");
    return;
  }
  _internalRepeatCycle = /** @type {0|1|2} */ ((_internalRepeatCycle + 1) % 3);
  syncInternalQueueControlButtons();
  setStatus($("player-status"), `Repeat: ${_INTERNAL_REPEAT_LABELS[_internalRepeatCycle]}`, "ok");
});

$("btn-int-shuf").addEventListener("click", () => {
  if (_internalRelayQueue.length <= 1) {
    setStatus($("player-status"), "Shuffle needs at least 2 tracks in the queue.", "");
    return;
  }
  _internalShuffleOn = !_internalShuffleOn;
  if (_internalShuffleOn) shuffleInternalRelayTail();
  else unshuffleInternalRelayFromBase();
  syncInternalQueueControlButtons();
  setStatus($("player-status"), _internalShuffleOn ? "Shuffle: on (remaining tracks)" : "Shuffle: off", "ok");
});

/**
 * Switch to Player tab, resolve relay URL(s), play first and queue the rest on `ended`.
 * @param {string[]} urls
 */
/**
 * @param {string[]} urls
 * @param {string[]} [titles]
 */
async function playHitUrlsInPlayer(urls, titles) {
  switchToPlayerTab();
  await primeInternalPlayerFromUserGesture();
  const n = urls.filter(Boolean).length;
  setStatus(
    $("player-status"),
    n > 1 ? `Resolving ${n} streams…` : "Resolving stream…",
    ""
  );
  if (n > 1) {
    setStatus($("dl-status"), `Resolving ${n} streams (parallel)…`, "");
  }
  await relayAndPlay(urls, titles);
  setStatus($("player-status"), n > 1 ? `Playing queue (${n} tracks)…` : "Playing.", "ok");
}

/**
 * Shuffle URLs from (current index + 1) to end of the internal relay queue.
 */
function shuffleInternalRelayTail() {
  const q = _internalRelayQueue;
  const t = _internalRelayTitles;
  const from = _internalRelayIdx + 1;
  if (from >= q.length) return;
  for (let i = q.length - 1; i > from; i--) {
    const j = from + Math.floor(Math.random() * (i - from + 1));
    const u = q[i];
    q[i] = q[j];
    q[j] = u;
    if (t.length === q.length) {
      const tv = t[i];
      t[i] = t[j];
      t[j] = tv;
    }
  }
}

/**
 * Restore queue tail to original order (after played prefix), for unshuffle.
 */
function unshuffleInternalRelayFromBase() {
  const base = _internalRelayQueueBase;
  const baseT = _internalRelayTitlesBase;
  const q = _internalRelayQueue;
  const t = _internalRelayTitles;
  const idx = _internalRelayIdx;
  if (!base.length || base.length !== q.length) {
    _internalRelayQueue = base.length ? [...base] : [...q];
    _internalRelayTitles =
      baseT.length === _internalRelayQueue.length
        ? [...baseT]
        : normalizeRelayTitles(_internalRelayQueue, t);
    return;
  }
  const playedHead = q.slice(0, idx + 1);
  const playedHeadT = t.slice(0, idx + 1);
  const playedSet = new Set(playedHead);
  const tail = [];
  const tailT = [];
  for (let i = 0; i < base.length; i++) {
    const u = base[i];
    if (!playedSet.has(u)) {
      tail.push(u);
      tailT.push(baseT[i] || t[base.indexOf(u)] || "");
    }
  }
  _internalRelayQueue = playedHead.concat(tail);
  _internalRelayTitles = playedHeadT.concat(tailT);
}

function syncInternalQueueControlButtons() {
  const br = $("btn-int-repeat");
  const bs = $("btn-int-shuf");
  const len = _internalRelayQueue.length;
  if (br) {
    setButtonIconLabel(br, "Repeat: " + _INTERNAL_REPEAT_LABELS[_internalRepeatCycle]);
    br.classList.toggle("is-active", _internalRepeatCycle !== 0);
    br.setAttribute("aria-pressed", _internalRepeatCycle !== 0 ? "true" : "false");
    br.disabled = len === 0;
    br.title =
      _internalRepeatCycle === 0
        ? "Repeat: off (click for all, then one)"
        : _internalRepeatCycle === 1
          ? "Repeat all tracks in queue"
          : "Repeat current track";
  }
  if (bs) {
    setButtonIconLabel(bs, _internalShuffleOn ? "Shuffle: on" : "Shuffle: off");
    bs.classList.toggle("is-active", _internalShuffleOn);
    bs.setAttribute("aria-pressed", _internalShuffleOn ? "true" : "false");
    bs.disabled = len <= 1;
    bs.title = len <= 1 ? "Shuffle (needs 2+ tracks)" : "Shuffle order of remaining tracks";
  }
}

function updateInternalQueueControlsVisibility() {
  const row = $("player-queue-row");
  if (!row) return;
  row.hidden = _internalRelayQueue.length === 0;
  syncInternalQueueControlButtons();
}

function ensurePlayerAudible(v) {
  if (!v) return;
  v.muted = false;
  if (!v.volume || v.volume === 0) v.volume = 1;
}

/** Unlock programmatic play() after stream resolve (browser autoplay policy). */
async function primeInternalPlayerFromUserGesture() {
  const v = $("v");
  if (!v) return;
  ensurePlayerAudible(v);
  try {
    const hadSrc = !!(v.src || v.currentSrc);
    v.muted = true;
    if (!hadSrc) {
      v.src =
        "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
    }
    await v.play();
    v.pause();
    if (!hadSrc) {
      v.removeAttribute("src");
      v.load();
    }
  } catch (_) {
    /* continue — user can press play on the control bar */
  } finally {
    ensurePlayerAudible(v);
  }
}

function onInternalRelayTrackEnded() {
  const el = $("v");
  if (!el) return;
  const len = _internalRelayQueue.length;
  if (!len) return;

  if (_internalRepeatCycle === 2) {
    el.currentTime = 0;
    ensurePlayerAudible(el);
    el.play()
      .then(() => ensurePlayerAudible(el))
      .catch(() => {});
    return;
  }

  let nextIdx = _internalRelayIdx + 1;
  if (nextIdx >= len) {
    if (_internalRepeatCycle === 1) {
      nextIdx = 0;
    } else {
      el.removeEventListener("ended", _onInternalPlayerEnded);
      _onInternalPlayerEnded = null;
      setStatus($("player-status"), len > 1 ? "Queue finished." : "Finished.", "ok");
      hideInternalPlayerPlaceholder();
      clearPlayerNowPlaying();
      updateInternalQueueControlsVisibility();
      return;
    }
  }

  _internalRelayIdx = nextIdx;
  if (len === 1 && _internalRepeatCycle === 1) {
    el.currentTime = 0;
    ensurePlayerAudible(el);
    el.play()
      .then(() => ensurePlayerAudible(el))
      .catch(() => {});
    return;
  }
  el.src = _internalRelayQueue[_internalRelayIdx];
  attachInternalPlayerHooks();
  ensurePlayerAudible(el);
  el.play()
    .then(() => ensurePlayerAudible(el))
    .catch(() => {});
  updatePlayerNowPlaying();
  setStatus(
    $("player-status"),
    len > 1 ? `Playing ${_internalRelayIdx + 1} of ${len}…` : "Playing.",
    ""
  );
}

/**
 * Play already-resolved relay HTTP URLs (local stream server).
 * @param {string[]} list
 * @param {string[]} [titles]
 */
async function playRelayUrlList(list, titles) {
  const clean = (list || []).map((u) => String(u).trim()).filter(Boolean);
  if (!clean.length) throw new Error("No stream URL");
  const labels = normalizeRelayTitles(clean, titles);

  hideInternalPlayerPlaceholder();
  const v = $("v");
  const a = $("a");
  if (_onInternalPlayerEnded) {
    v.removeEventListener("ended", _onInternalPlayerEnded);
    _onInternalPlayerEnded = null;
  }

  a.removeAttribute("src");
  a.style.display = "none";
  v.style.display = "block";

  _internalRelayQueueBase = [...clean];
  _internalRelayTitlesBase = [...labels];
  _internalRelayQueue = [...clean];
  _internalRelayTitles = [...labels];
  _internalRelayIdx = 0;
  _internalShuffleOn = false;
  _internalRepeatCycle = 0;
  v.src = _internalRelayQueue[0];
  v.load();
  attachInternalPlayerHooks();
  await new Promise((resolve) => {
    if (v.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      resolve();
      return;
    }
    const done = () => {
      v.removeEventListener("canplay", done);
      v.removeEventListener("error", done);
      resolve();
    };
    v.addEventListener("canplay", done, { once: true });
    v.addEventListener("error", done, { once: true });
    setTimeout(done, 12000);
  });
  ensurePlayerAudible(v);
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      await v.play();
      if (!v.paused) break;
    } catch (_) {
      if (attempt === 2) {
        try {
          v.muted = true;
          await v.play();
          ensurePlayerAudible(v);
          if (!v.paused) break;
        } catch (_2) {
          /* retry loop */
        }
      }
      await new Promise((r) => setTimeout(r, 300 * (attempt + 1)));
    }
  }
  ensurePlayerAudible(v);

  _onInternalPlayerEnded = onInternalRelayTrackEnded;
  v.addEventListener("ended", _onInternalPlayerEnded);
  updatePlayerNowPlaying();
  updateInternalQueueControlsVisibility();
}

/**
 * @param {string[]} urls
 * @param {string[]} [titles]
 */
async function relayAndPlay(urls, titles) {
  const clean = (urls || []).map((u) => String(u).trim()).filter(Boolean);
  if (!clean.length) throw new Error("No URLs to play");
  const titleList = normalizeRelayTitles(clean, titles);
  setStatus($("player-status"), clean.length > 1 ? `Resolving ${clean.length} streams…` : "Resolving stream…", "");
  const r = await api("/api/stream_urls", { method: "POST", body: { urls: clean, host: "127.0.0.1" } });
  const list = r.urls || [];
  if (!list.length) throw new Error("No stream URL");
  await playRelayUrlList(list, titleList);
}

/**
 * @returns {{ path: string, label: string }[]}
 */
function selectedLibItems() {
  const out = [];
  document.querySelectorAll("#lib-body tr").forEach((tr) => {
    const cb = tr.querySelector(".lib-cb:checked");
    if (!cb) return;
    const p = cb.getAttribute("data-path");
    if (!p) return;
    const label = (tr.querySelector(".lib-label")?.textContent || "").trim();
    out.push({ path: p, label });
  });
  return out;
}

/** Stop the in-app video/audio player (e.g. when the same stream is sent to Chromecast). */
function stopLocalInternalPlayback() {
  const v = $("v");
  const a = $("a");
  const hadQueue = _internalRelayQueue.length > 0;
  const hadSrc = !!(v && (v.src || v.currentSrc));
  if (v) {
    if (_onInternalPlayerEnded) {
      v.removeEventListener("ended", _onInternalPlayerEnded);
      _onInternalPlayerEnded = null;
    }
    _internalRelayQueue = [];
    _internalRelayQueueBase = [];
    _internalRelayTitles = [];
    _internalRelayTitlesBase = [];
    _internalRelayIdx = 0;
    _internalShuffleOn = false;
    _internalRepeatCycle = 0;
    updateInternalQueueControlsVisibility();
    detachInternalPlayerHooks();
    try {
      v.pause();
    } catch (_) {}
    v.removeAttribute("src");
    try {
      v.load();
    } catch (_) {}
  }
  if (a) {
    try {
      a.pause();
    } catch (_) {}
    a.removeAttribute("src");
    try {
      a.load();
    } catch (_) {}
    a.style.display = "none";
  }
  if (v) v.style.display = "block";
  hideInternalPlayerPlaceholder();
  clearPlayerNowPlaying();
  if (hadQueue || hadSrc) {
    setStatus($("player-status"), "Local playback stopped (Chromecast).", "ok");
  }
}

$("btn-cc-disc").addEventListener("click", async () => {
  try {
    await runChromecastDiscoverWithUi();
  } catch (e) {
    $("cc-status").textContent = e.message || String(e);
  }
});

$("cc-dev-all").addEventListener("change", (ev) => {
  const on = ev.target.checked;
  document.querySelectorAll("#cc-dev-list .cc-dev-cb").forEach((cb) => {
    cb.checked = on;
  });
  updateCcPickHint();
});

const _ccDevList = $("cc-dev-list");
if (_ccDevList) _ccDevList.addEventListener("change", () => updateCcPickHint());

$("btn-cc-stop-last").addEventListener("click", async () => {
  try {
    const r = await api("/api/chromecast/stop_last", { method: "POST", body: {} });
    $("cc-status").textContent = r.message || "OK";
  } catch (e) {
    $("cc-status").textContent = e.message;
  }
});

$("btn-cc-file").addEventListener("click", async () => {
  const body = { ...ccCastBodyBase() };

  if (lastRemoteCastItems.length > 1) {
    try {
      await api("/api/chromecast/cast_stream_queue", {
        method: "POST",
        body: { ...body, items: lastRemoteCastItems },
      });
      stopLocalInternalPlayback();
      $("cc-status").textContent = "Cast queue started on selected device(s).";
    } catch (e) {
      $("cc-status").textContent = e.message;
    }
    return;
  }
  if (lastRemoteCastItems.length === 1) {
    const it = lastRemoteCastItems[0];
    try {
      await api("/api/chromecast/cast_file", {
        method: "POST",
        body: {
          ...body,
          cast_stream_url: it.cast_stream_url,
          stream_title: it.label || "",
        },
      });
      stopLocalInternalPlayback();
      $("cc-status").textContent = "Cast started.";
    } catch (e) {
      $("cc-status").textContent = e.message;
    }
    return;
  }

  const paths = selectedLibPaths();
  if (paths.length) {
    body.abs_path = paths[0];
  } else if (lastCastMediaToken) {
    body.media_token = lastCastMediaToken;
  } else {
    $("cc-status").textContent =
      "Prepare streams from Search (Chromecast selected / row icon), or Library → Prepare for Chromecast.";
    return;
  }
  try {
    await api("/api/chromecast/cast_file", { method: "POST", body });
    stopLocalInternalPlayback();
    $("cc-status").textContent = "Cast started on selected device(s).";
  } catch (e) {
    $("cc-status").textContent = e.message;
  }
});

$("btn-cc-play-pause").addEventListener("click", async () => {
  try {
    await api("/api/chromecast/play_pause", { method: "POST", body: ccCastBodyBase() });
  } catch (e) {
    $("cc-status").textContent = e.message;
  }
});

$("btn-cc-stop-proj").addEventListener("click", async () => {
  try {
    await api("/api/chromecast/stop_projection", { method: "POST", body: ccCastBodyBase() });
    $("cc-status").textContent = "Stop sent.";
  } catch (e) {
    $("cc-status").textContent = e.message;
  }
});

$("btn-cc-repeat").addEventListener("click", async () => {
  try {
    const r = await api("/api/chromecast/repeat", { method: "POST", body: ccCastBodyBase() });
    const b = $("btn-cc-repeat");
    if (b && r.repeat) setButtonIconLabel(b, "Repeat: " + r.repeat);
  } catch (e) {
    $("cc-status").textContent = e.message;
  }
});

$("btn-cc-shuf").addEventListener("click", async () => {
  ccShuffleOn = !ccShuffleOn;
  try {
    await api("/api/chromecast/shuffle", {
      method: "POST",
      body: { ...ccCastBodyBase(), shuffle: ccShuffleOn },
    });
    const b = $("btn-cc-shuf");
    if (b) setButtonIconLabel(b, ccShuffleOn ? "Shuffle: on" : "Shuffle: off");
  } catch (e) {
    $("cc-status").textContent = e.message;
  }
});

$("cc-seek").addEventListener("change", async () => {
  if (ccSeekProgrammatic) return;
  const seek = $("cc-seek");
  const pos = parseFloat(seek.value);
  try {
    await api("/api/chromecast/seek", {
      method: "POST",
      body: { ...ccCastBodyBase(), position_sec: pos },
    });
  } catch (e) {
    $("cc-status").textContent = e.message;
  }
});

$("cc-vol").addEventListener("change", async () => {
  const v = parseFloat($("cc-vol").value) / 100.0;
  try {
    await api("/api/chromecast/volume", {
      method: "POST",
      body: { ...ccCastBodyBase(), level: v },
    });
  } catch (e) {
    $("cc-status").textContent = e.message;
  }
});

$("btn-ytdlp").addEventListener("click", async () => {
  try {
    const r = await api("/api/ytdlp");
    $("ytdlp-out").textContent = JSON.stringify(r, null, 2);
  } catch (e) {
    $("ytdlp-out").textContent = e.message;
  }
});

$("btn-ytdlp-up").addEventListener("click", async () => {
  $("ytdlp-out").textContent = "Running pip…";
  try {
    const r = await api("/api/ytdlp/upgrade", { method: "POST", body: {} });
    $("ytdlp-out").textContent = (r.log_tail || "") + "\nversion: " + (r.version || "");
  } catch (e) {
    $("ytdlp-out").textContent = e.message;
  }
});

$("preset-dd-btn")?.addEventListener("click", () => {
  const list = $("preset-dd-list");
  if (!list) return;
  if (list.hidden) openPresetDropdown();
  else closePresetDropdown();
});

document.addEventListener("click", (ev) => {
  const dd = $("preset-dd");
  if (!dd || dd.contains(ev.target)) return;
  closePresetDropdown();
});

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape") closePresetDropdown();
});

const fsBrowserState = {
  initial: "",
  currentPath: "",
  listingPaths: [],
  selectedPaths: new Set(),
  pendingDeletePaths: null,
  resolve: null,
};

function fsDeleteConfirmOpen() {
  const confirm = $("fs-browser-delete-confirm");
  return !!(confirm && !confirm.hidden);
}

function fsSubrowOpen() {
  const mk = $("fs-browser-mkdir-row");
  return (mk && !mk.hidden) || fsDeleteConfirmOpen();
}

function fsSetDeleteConfirmUi(visible) {
  const pick = $("fs-browser-delete-pick");
  const confirm = $("fs-browser-delete-confirm");
  const countEl = $("fs-browser-selection-count");
  if (pick) {
    if (visible) {
      pick.hidden = true;
      pick.setAttribute("hidden", "");
    } else {
      pick.hidden = false;
      pick.removeAttribute("hidden");
    }
  }
  if (confirm) {
    if (visible) {
      confirm.hidden = false;
      confirm.removeAttribute("hidden");
    } else {
      confirm.hidden = true;
      confirm.setAttribute("hidden", "");
    }
  }
  if (countEl && visible) {
    countEl.hidden = true;
    countEl.setAttribute("hidden", "");
  }
}

function fsHideSubrows() {
  const mk = $("fs-browser-mkdir-row");
  if (mk) {
    mk.hidden = true;
    mk.setAttribute("hidden", "");
  }
  fsBrowserState.pendingDeletePaths = null;
  fsSetDeleteConfirmUi(false);
  fsUpdateSelectionUI();
}

function fsBrowserCancel() {
  if (fsSubrowOpen()) {
    fsHideSubrows();
    fsSetError("");
    return;
  }
  closeFolderBrowser(null);
}

function fsListingPaths(data) {
  const out = [];
  for (const e of data.dirs || []) {
    if (e.path) out.push(e.path);
  }
  for (const e of data.files || []) {
    if (e.path) out.push(e.path);
  }
  return out;
}

function fsPathSelected(path) {
  return fsBrowserState.selectedPaths.has(path);
}

function fsTogglePath(path, on) {
  if (!path) return;
  if (on) fsBrowserState.selectedPaths.add(path);
  else fsBrowserState.selectedPaths.delete(path);
  fsUpdateSelectionUI();
}

function fsUpdateSelectionUI() {
  const n = fsBrowserState.selectedPaths.size;
  const listing = fsBrowserState.listingPaths;
  const all = listing.length;
  const countEl = $("fs-browser-selection-count");
  if (countEl && !fsBrowserState.pendingDeletePaths?.length) {
    if (n > 0) {
      countEl.textContent = n === 1 ? "1 selected" : `${n} selected`;
      countEl.hidden = false;
      countEl.removeAttribute("hidden");
    } else {
      countEl.textContent = "";
      countEl.hidden = true;
      countEl.setAttribute("hidden", "");
    }
  }
  const delBtn = $("fs-browser-delete-selected");
  if (delBtn && !fsBrowserState.pendingDeletePaths?.length) {
    delBtn.disabled = n === 0;
    setButtonIconLabel(delBtn, n > 0 ? `Delete selected (${n})` : "Delete selected");
  }
  const selectAll = $("fs-browser-select-all");
  if (selectAll) {
    selectAll.indeterminate = n > 0 && n < all;
    selectAll.checked = all > 0 && n === all;
  }
  const list = $("fs-browser-list");
  if (!list) return;
  list.querySelectorAll(".fs-browser-item").forEach((li) => {
    const p = li.dataset.path;
    const sel = p && fsPathSelected(p);
    li.classList.toggle("selected", !!sel);
    const cb = li.querySelector(".fs-browser-item-check");
    if (cb) cb.checked = !!sel;
  });
}

function fsDeleteConfirmMessage(paths) {
  const names = paths.map((p) => {
    const parts = p.replace(/\\/g, "/").split("/");
    return parts[parts.length - 1] || p;
  });
  if (names.length === 1) {
    return `Delete “${names[0]}”? This cannot be undone.`;
  }
  const preview = names.slice(0, 5).map((n) => `• ${n}`).join("\n");
  const more = names.length > 5 ? `\n… and ${names.length - 5} more` : "";
  return `Delete ${names.length} items? This cannot be undone.\n${preview}${more}`;
}

function fsShowDeleteConfirm(paths) {
  const unique = [...new Set(paths.filter(Boolean))];
  if (!unique.length) return;
  fsBrowserState.pendingDeletePaths = unique;
  const mk = $("fs-browser-mkdir-row");
  if (mk) {
    mk.hidden = true;
    mk.setAttribute("hidden", "");
  }
  const msg = $("fs-browser-delete-msg");
  if (msg) msg.textContent = fsDeleteConfirmMessage(unique);
  fsSetDeleteConfirmUi(true);
  fsSetError("");
}

function fsSetError(msg) {
  const el = $("fs-browser-err");
  if (!el) return;
  if (msg) {
    el.textContent = msg;
    el.hidden = false;
  } else {
    el.textContent = "";
    el.hidden = true;
  }
}

function fsEntryIcon(kind) {
  const im = document.createElement("img");
  im.className = "btn-icon";
  im.alt = "";
  im.src = themedIconUrl(kind === "dir" ? "folder" : "file");
  return im;
}

function fsRenderBrowse(data, { clearSelection = true } = {}) {
  fsHideSubrows();
  fsBrowserState.currentPath = data.path;
  fsBrowserState.listingPaths = fsListingPaths(data);
  if (clearSelection) {
    fsBrowserState.selectedPaths = new Set();
  } else {
    const keep = new Set();
    for (const p of fsBrowserState.selectedPaths) {
      if (fsBrowserState.listingPaths.includes(p)) keep.add(p);
    }
    fsBrowserState.selectedPaths = keep;
  }
  const pathInp = $("fs-browser-path");
  if (pathInp) pathInp.value = data.path || "";
  const list = $("fs-browser-list");
  if (!list) return;
  list.innerHTML = "";

  const addRow = (entry, { isDir, kind, onOpen, selectable }) => {
    const li = document.createElement("li");
    li.className = "fs-browser-item";
    if (entry.path) li.dataset.path = entry.path;

    if (selectable && entry.path) {
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "fs-browser-item-check";
      cb.checked = fsPathSelected(entry.path);
      cb.addEventListener("click", (ev) => ev.stopPropagation());
      cb.addEventListener("change", () => fsTogglePath(entry.path, cb.checked));
      li.appendChild(cb);
    }

    const main = document.createElement("button");
    main.type = "button";
    main.className = "fs-browser-item-main";
    main.appendChild(fsEntryIcon(isDir ? "dir" : "file"));
    const name = document.createElement("span");
    name.className = "fs-browser-item-name";
    name.textContent = entry.name || entry.path || "";
    main.appendChild(name);
    main.addEventListener("click", () => onOpen(li, entry));

    li.appendChild(main);

    if (selectable && entry.path && fsPathSelected(entry.path)) {
      li.classList.add("selected");
    }

    list.appendChild(li);
  };

  for (const d of data.drives || []) {
    addRow({ name: d, path: d }, {
      isDir: true,
      kind: "drive",
      onOpen: () => fsLoadBrowse(d),
    });
  }

  if (data.can_go_up && data.parent) {
    addRow({ name: "..", path: data.parent }, {
      isDir: true,
      kind: "parent",
      onOpen: () => fsLoadBrowse(data.parent),
    });
  }

  for (const e of data.dirs || []) {
    const p = e.path;
    addRow(e, {
      isDir: true,
      kind: "dir",
      selectable: true,
      onOpen: () => fsLoadBrowse(p),
    });
  }

  for (const e of data.files || []) {
    const p = e.path;
    addRow(e, {
      isDir: false,
      kind: "file",
      selectable: true,
      onOpen: (_li, entry) => {
        const on = !fsPathSelected(p);
        fsTogglePath(p, on);
      },
    });
  }

  fsUpdateSelectionUI();
}

async function fsLoadBrowse(pathOrInitial) {
  fsSetError("");
  const prevPath = fsBrowserState.currentPath;
  const body =
    typeof pathOrInitial === "string" && pathOrInitial.length > 0
      ? { path: pathOrInitial }
      : { initial: pathOrInitial || fsBrowserState.initial };
  body.show_all_files = showAllFilesEnabled();
  const r = await api("/api/fs/browse", { method: "POST", body });
  const clearSelection = !prevPath || r.path !== prevPath;
  fsRenderBrowse(r, { clearSelection });
}

function openFolderBrowser({ initial, title, pickLabel }) {
  return new Promise((resolve) => {
    fsBrowserState.initial = initial || "";
    fsBrowserState.selectedPaths = new Set();
    fsBrowserState.listingPaths = [];
    fsBrowserState.resolve = resolve;
    const overlay = $("fs-browser");
    const titleEl = $("fs-browser-title");
    if (titleEl) titleEl.textContent = title || "Choose folder";
    setButtonIconLabel($("fs-browser-pick"), pickLabel || "Use this folder");
    fsHideSubrows();
    fsSetError("");
    syncShowAllFilesCheckboxes();
    if (overlay) {
      overlay.hidden = false;
      overlay.setAttribute("aria-hidden", "false");
    }
    fsLoadBrowse(initial || "").catch((e) => fsSetError(e.message));
  });
}

function closeFolderBrowser(result) {
  const overlay = $("fs-browser");
  if (overlay) {
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
  }
  const fn = fsBrowserState.resolve;
  fsBrowserState.resolve = null;
  if (fn) fn(result);
}

function setupFolderBrowser() {
  $("fs-browser-cancel")?.addEventListener("click", () => fsBrowserCancel());
  $("fs-browser-close")?.addEventListener("click", () => fsBrowserCancel());
  $("fs-browser-pick")?.addEventListener("click", () => {
    if (fsBrowserState.currentPath) closeFolderBrowser(fsBrowserState.currentPath);
  });
  $("fs-browser-go")?.addEventListener("click", () => {
    const p = ($("fs-browser-path")?.value || "").trim();
    fsLoadBrowse(p).catch((e) => fsSetError(e.message));
  });
  $("fs-browser-path")?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") $("fs-browser-go")?.click();
  });
  $("fs-browser-up")?.addEventListener("click", async () => {
    try {
      const r = await api("/api/fs/browse", {
        method: "POST",
        body: { path: fsBrowserState.currentPath },
      });
      if (r.parent) await fsLoadBrowse(r.parent);
    } catch (e) {
      fsSetError(e.message);
    }
  });
  $("fs-browser-refresh")?.addEventListener("click", () => {
    fsLoadBrowse(fsBrowserState.currentPath).catch((e) => fsSetError(e.message));
  });
  $("fs-browser-new-btn")?.addEventListener("click", () => {
    fsHideSubrows();
    const row = $("fs-browser-mkdir-row");
    const inp = $("fs-browser-mkdir-name");
    if (row) {
      row.hidden = false;
      row.removeAttribute("hidden");
    }
    if (inp) {
      inp.value = "";
      inp.focus();
    }
    fsSetError("");
  });
  $("fs-browser-mkdir-ok")?.addEventListener("click", async () => {
    const name = ($("fs-browser-mkdir-name")?.value || "").trim();
    if (!name) return;
    try {
      await api("/api/fs/mkdir", {
        method: "POST",
        body: { parent: fsBrowserState.currentPath, name },
      });
      fsHideSubrows();
      await fsLoadBrowse(fsBrowserState.currentPath);
    } catch (e) {
      fsSetError(e.message);
    }
  });
  $("fs-browser-select-all")?.addEventListener("change", (ev) => {
    const on = ev.target.checked;
    if (on) {
      for (const p of fsBrowserState.listingPaths) fsBrowserState.selectedPaths.add(p);
    } else {
      fsBrowserState.selectedPaths.clear();
    }
    fsUpdateSelectionUI();
  });
  $("fs-browser-delete-selected")?.addEventListener("click", () => {
    const paths = [...fsBrowserState.selectedPaths];
    if (!paths.length) return;
    fsShowDeleteConfirm(paths);
  });
  $("fs-browser-delete-ok")?.addEventListener("click", async () => {
    const paths = fsBrowserState.pendingDeletePaths;
    if (!paths?.length) return;
    try {
      const r = await api("/api/fs/delete_batch", {
        method: "POST",
        body: { paths },
      });
      fsHideSubrows();
      for (const p of paths) fsBrowserState.selectedPaths.delete(p);
      if (r.errors?.length) {
        fsSetError(r.errors.join("; "));
      } else {
        fsSetError("");
      }
      await fsLoadBrowse(fsBrowserState.currentPath);
    } catch (e) {
      fsSetError(e.message);
    }
  });
  $("fs-browser")?.addEventListener("click", (ev) => {
    if (ev.target === $("fs-browser")) fsBrowserCancel();
  });
  document.addEventListener("keydown", (ev) => {
    const overlay = $("fs-browser");
    if (ev.key === "Escape" && overlay && !overlay.hidden) fsBrowserCancel();
  });
}

function setupDonateTab() {
  const BMC = "https://buymeacoffee.com/medcodex";
  const BTC = "bc1q8gv3zue7wtem279rqz7rj405qftpu9855k2l2s";
  const imgBmc = $("donate-qr-bmc");
  if (imgBmc) {
    imgBmc.src = "/api/donate/asset/cofe";
    imgBmc.onerror = () => {
      imgBmc.onerror = null;
      imgBmc.src = "/api/donate/qr.svg?kind=bmc";
    };
  }
  const imgBtc = $("donate-qr-btc");
  if (imgBtc) {
    imgBtc.src = "/api/donate/asset/btc";
    imgBtc.onerror = () => {
      imgBtc.onerror = null;
      imgBtc.src = "/api/donate/qr.svg?kind=btc";
    };
  }
  const urlEl = $("donate-bmc-url");
  if (urlEl) urlEl.textContent = BMC;
  const btcEl = $("donate-btc-addr");
  if (btcEl) btcEl.textContent = BTC;
  $("donate-open-bmc")?.addEventListener("click", () => {
    window.open(BMC, "_blank", "noopener,noreferrer");
  });
  $("donate-copy-btc")?.addEventListener("click", async () => {
    const st = $("donate-status");
    try {
      await navigator.clipboard.writeText(BTC);
      if (st) {
        st.textContent = "BTC address copied to clipboard.";
        st.className = "status ok";
      }
    } catch (e) {
      if (st) {
        st.textContent = e.message || String(e);
        st.className = "status error";
      }
    }
  });
}

function setupAboutTab() {
  const SITE = "https://calvarr.github.io/";
  const REPO = "https://github.com/calvarr/DLPulse-next";
  const siteEl = $("about-site-url");
  if (siteEl) siteEl.textContent = SITE;
  const repoEl = $("about-repo-url");
  if (repoEl) repoEl.textContent = REPO;
  $("about-open-site")?.addEventListener("click", () => {
    window.open(SITE, "_blank", "noopener,noreferrer");
  });
  $("about-open-repo")?.addEventListener("click", () => {
    window.open(REPO, "_blank", "noopener,noreferrer");
  });
  $("about-open-releases")?.addEventListener("click", () => {
    window.open(`${REPO}/releases`, "_blank", "noopener,noreferrer");
  });
}

setupFolderBrowser();
setupDonateTab();
setupAboutTab();
init();

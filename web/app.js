// lingua-bridge web UI. No build step, no external requests: it only talks to this server's API.
"use strict";
const $ = (id) => document.getElementById(id);

const EXAMPLES = {
  translate: [
    ["धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः", "sa"],
    ["मुझे चाय पसंद है।", "hi"],
    ["Knowledge is power.", "en"],
    ["我喜欢喝茶。", "zh"],
  ],
  convert: { transliterate: ["धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः", "devanagari", "iast"],
             hinglish_to_devanagari: ["mera naam Vinay hai, aap kaise ho?"],
             pinyin: ["我喜欢喝茶，银行行长。"], chinese_script: ["我喜欢喝茶，软件开发。"] },
  detect: ["रामः वनं गच्छति", "वह कल दिल्ली जाएगा।", "mujhe chai pasand hai", "dharmakSetre kurukSetre", "我喜歡喝茶"],
};

async function api(path, body) {
  let res;
  try {
    res = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : undefined);
  } catch (e) {
    throw new Error("Cannot reach the server. Is `lingua serve` still running?");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data.message || (Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("; ") : data.detail) || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

function show(el, on) { el.hidden = !on; }
function showError(id, msg) { const el = $(id); el.textContent = msg || ""; show(el, !!msg); }
function pill(text, cls = "") { const s = document.createElement("span"); s.className = "pill " + cls; s.textContent = text; return s; }
function copyButton(btnId, outId) {
  $(btnId).addEventListener("click", async () => {
    const text = $(outId).textContent;
    try { await navigator.clipboard.writeText(text); $(btnId).textContent = "Copied"; }
    catch { const r = document.createRange(); r.selectNodeContents($(outId)); getSelection().removeAllRanges(); getSelection().addRange(r); $(btnId).textContent = "Selected"; }
    setTimeout(() => ($(btnId).textContent = "Copy"), 1500);
  });
}

// ---- tabs
for (const name of ["translate", "convert", "detect"]) {
  $("tab-" + name).addEventListener("click", () => {
    for (const n of ["translate", "convert", "detect"]) {
      $("tab-" + n).setAttribute("aria-selected", String(n === name));
      show($("panel-" + n), n === name);
    }
  });
}

// ---- status line
(async function status() {
  try {
    const m = await api("/models");
    $("status").textContent = `Ready · device: ${m.device} · model profile: ${m.profile}`;
  } catch (e) { $("status").textContent = e.message; }
})();

// ---- translate
const LANG_DIR = { sa: "ltr", hi: "ltr", en: "ltr", zh: "ltr" };
function syncZh() { show($("t-zh-wrap"), $("t-tgt").value === "zh"); }
$("t-tgt").addEventListener("change", syncZh);
$("t-swap").addEventListener("click", () => {
  const s = $("t-src").value, t = $("t-tgt").value;
  if (s === "auto") return;
  $("t-src").value = t; $("t-tgt").value = s; syncZh();
  const out = $("t-out").textContent; if (out) $("t-in").value = out;
});
EXAMPLES.translate.forEach(([text, lang]) => {
  const b = document.createElement("button"); b.textContent = text.length > 18 ? text.slice(0, 18) + "…" : text;
  b.addEventListener("click", () => { $("t-in").value = text; $("t-src").value = lang; if ($("t-tgt").value === lang) $("t-tgt").value = lang === "en" ? "hi" : "en"; syncZh(); });
  $("t-examples").append(b);
});

async function translate() {
  const text = $("t-in").value.trim();
  if (!text) { showError("t-err", "Enter some text first."); return; }
  showError("t-err", ""); show($("t-out-wrap"), false); show($("t-busy"), true); $("t-go").disabled = true;
  try {
    const r = await api("/translate", { text, src: $("t-src").value, tgt: $("t-tgt").value, zh_variant: $("t-zh").value });
    $("t-out").textContent = r.text; $("t-out").lang = r.tgt;
    const meta = $("t-meta"); meta.replaceChildren();
    if (r.via === "pivot") meta.append(pill("pivot through English: errors can compound", "pivot"));
    else meta.append(pill(r.via === "identity" ? "no translation needed" : "direct", "ok"));
    r.route.forEach((h) => meta.append(pill(`${h.src}→${h.tgt} · ${h.backend} · ${h.model.split("/").pop()} · ${Math.round(h.ms)} ms`)));
    if (r.detected) meta.append(pill(`detected ${r.detected.language} (${Math.round(r.detected.confidence * 100)}%)`));
    const w = $("t-warn"); w.replaceChildren();
    r.warnings.forEach((x) => { const li = document.createElement("li"); li.textContent = x; w.append(li); });
    show($("t-out-wrap"), true);
  } catch (e) { showError("t-err", e.message); }
  finally { show($("t-busy"), false); $("t-go").disabled = false; }
}
$("t-go").addEventListener("click", translate);
$("t-in").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) translate(); });
copyButton("t-copy", "t-out");

// ---- convert
function syncConvert() {
  const op = $("c-op").value;
  show($("c-opts-transliterate"), op === "transliterate");
  show($("c-opts-pinyin"), op === "pinyin");
  show($("c-opts-script"), op === "chinese_script");
  $("c-examples").replaceChildren();
  const ex = EXAMPLES.convert[op];
  const b = document.createElement("button"); b.textContent = "Use an example";
  b.addEventListener("click", () => { $("c-in").value = ex[0]; if (ex[1]) { $("c-from").value = ex[1]; $("c-to").value = ex[2]; } });
  $("c-examples").append(b);
}
$("c-op").addEventListener("change", syncConvert); syncConvert();
$("c-go").addEventListener("click", async () => {
  const text = $("c-in").value.trim();
  if (!text) { showError("c-err", "Enter some text first."); return; }
  showError("c-err", ""); show($("c-out-wrap"), false);
  try {
    const r = await api("/convert", { text, op: $("c-op").value, source_scheme: $("c-from").value, target_scheme: $("c-to").value,
      pinyin_style: $("c-style").value, chinese_target: $("c-target").value, chinese_variant: $("c-variant").value });
    $("c-out").textContent = r.text;
    const meta = $("c-meta"); meta.replaceChildren();
    meta.append(pill(r.fidelity === "lossless" ? "lossless: reversible" : r.fidelity === "lossy" ? "lossy: cannot be reversed exactly" : "best effort", r.fidelity === "lossless" ? "ok" : ""));
    if (r.backend) meta.append(pill("engine: " + r.backend));
    if (r.note) meta.append(pill(r.note));
    show($("c-out-wrap"), true);
  } catch (e) { showError("c-err", e.message); }
});
copyButton("c-copy", "c-out");

// ---- detect
EXAMPLES.detect.forEach((text) => {
  const b = document.createElement("button"); b.textContent = text.length > 16 ? text.slice(0, 16) + "…" : text;
  b.addEventListener("click", () => { $("d-in").value = text; });
  $("d-examples").append(b);
});
$("d-go").addEventListener("click", async () => {
  const text = $("d-in").value.trim();
  if (!text) { showError("d-err", "Enter some text first."); return; }
  showError("d-err", ""); show($("d-out"), false);
  try {
    const r = await api("/detect", { text });
    const lang = r.language ? r.language : "unknown";
    $("d-summary").textContent = `Script: ${r.script} · Language: ${lang} · Confidence: ${Math.round(r.confidence * 100)}%` +
      (r.ambiguous ? " · ambiguous" : "") + (r.latin_scheme ? ` · Latin scheme: ${r.latin_scheme}` : "");
    const bars = $("d-bars"); bars.replaceChildren();
    r.candidates.forEach((c) => {
      const row = document.createElement("div"); row.className = "bar";
      const name = document.createElement("b"); name.textContent = c.language;
      const track = document.createElement("span"); const fill = document.createElement("i"); fill.style.width = Math.round(c.score * 100) + "%"; track.append(fill);
      const val = document.createElement("em"); val.textContent = Math.round(c.score * 100) + "%"; val.style.fontStyle = "normal";
      row.append(name, track, val); bars.append(row);
    });
    $("d-note").textContent = r.note || "";
    show($("d-out"), true);
  } catch (e) { showError("d-err", e.message); }
});

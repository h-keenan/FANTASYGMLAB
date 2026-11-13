// DOM checks shared by the UI audit harnesses (ui_audit.mjs for Fantasy Sim, app_audit.mjs for the main app). Runs in the page.
export /** Runs in the page: returns findings for the current DOM. */
const CHECKS = () => {
  const W = document.documentElement.clientWidth;
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && cs.opacity !== "0"; };
  const label = (el) => (el.getAttribute("data-testid") ? `[${el.getAttribute("data-testid")}]` : "") + el.tagName.toLowerCase() + (el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).slice(0, 2).join(".") : "");
  const text = (el) => (el.getAttribute("aria-label") || el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 48);
  const out = { overflow: null, smallTargets: [], unnamed: [], truncated: [], tinyText: [], lowContrast: [], dialogsUnnamed: [], heights: {} };
  if (document.documentElement.scrollWidth > W + 1) out.overflow = { scrollWidth: document.documentElement.scrollWidth, width: W };
  const targets = [...document.querySelectorAll("button, a[href], [role=button], [role=tab], [role=checkbox], [role=switch], input:not([type=hidden]), select, textarea")].filter(vis);
  for (const el of targets) {
    const r = el.getBoundingClientRect();
    const h = Math.round(r.height);
    if (el.tagName === "BUTTON" || el.getAttribute("role") === "button") out.heights[h] = (out.heights[h] || 0) + 1;
    if ((r.height < 43.5 || r.width < 43.5) && !(el.tagName === "A" && el.closest("p, li") && r.height < 43.5 && el.textContent.trim().length > 12)) {
      out.smallTargets.push({ el: label(el), text: text(el), w: Math.round(r.width), h });
    }
    const name = (el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || el.getAttribute("title") || el.textContent || "").trim();
    if (!name && el.tagName !== "INPUT") out.unnamed.push({ el: label(el) });
    if (el.tagName === "INPUT" && !(el.getAttribute("aria-label") || el.id && document.querySelector(`label[for="${el.id}"]`) || el.getAttribute("placeholder") || el.closest("label"))) out.unnamed.push({ el: label(el) });
  }
  for (const el of document.querySelectorAll("*")) {
    if (!vis(el)) continue;
    const cs = getComputedStyle(el);
    if (el.children.length === 0 && el.textContent.trim()) {
      const size = parseFloat(cs.fontSize);
      if (size < 11.5) out.tinyText.push({ el: label(el), text: text(el), size });
      if ((cs.textOverflow === "ellipsis" || cs.webkitLineClamp !== "none") && el.scrollWidth > el.clientWidth + 1) out.truncated.push({ el: label(el), text: text(el) });
      if (el.scrollHeight > el.clientHeight + 2 && cs.webkitLineClamp && cs.webkitLineClamp !== "none") out.truncated.push({ el: label(el), text: text(el) });
    }
  }
  // contrast of leaf text vs the nearest composited background (page bg is the base)
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(",").map((x) => parseFloat(x)); return { r: p[0], g: p[1], b: p[2], a: p[3] === undefined ? 1 : p[3] }; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const over = (top, base) => ({ r: top.r * top.a + base.r * (1 - top.a), g: top.g * top.a + base.g * (1 - top.a), b: top.b * top.a + base.b * (1 - top.a), a: 1 });
  const bgOf = (el) => { const chain = []; for (let n = el; n; n = n.parentElement) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c.a > 0) chain.push(c); if (c && c.a === 1) break; } let base = parse(getComputedStyle(document.body).backgroundColor) || { r: 0, g: 0, b: 0, a: 1 }; if (base.a < 1) base = { r: 12, g: 14, b: 18, a: 1 }; for (const c of chain.reverse()) base = over(c, base); return base; };
  const seen = new Set();
  for (const el of document.querySelectorAll("p, span, a, button, h1, h2, h3, h4, li, label, div")) {
    if (!vis(el) || el.children.length > 0 || !el.textContent.trim()) continue;
    const cs = getComputedStyle(el);
    const fg = parse(cs.color); if (!fg) continue;
    const bg = bgOf(el);
    const f = over(fg, bg);
    const l1 = lum(f), l2 = lum(bg);
    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight, 10) >= 700;
    const need = size >= 24 || (size >= 18.66 && bold) ? 3 : 4.5;
    const key = text(el) + ratio.toFixed(1);
    if (ratio < need && !seen.has(key)) { seen.add(key); out.lowContrast.push({ el: label(el), text: text(el), ratio: Math.round(ratio * 100) / 100, need }); }
  }
  for (const d of document.querySelectorAll("[role=dialog]")) if (vis(d) && !(d.getAttribute("aria-label") || d.getAttribute("aria-labelledby"))) out.dialogsUnnamed.push({ el: label(d) });
  return out;
};
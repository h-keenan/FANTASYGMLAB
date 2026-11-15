// THE layout guard: one in-page check shared by module_scan.mjs (Desk) and layout_guard.mjs (Fantasy Sim), docs/ui-patterns.md "Layout guard".
// Runs in the page and returns violations (an empty list is clean):
//   h-scroll   the document scrolls sideways
//   offscreen  a visible element's box crosses the viewport edge (outside any deliberate horizontal scroller)
//   clipped    an element's box crosses the right/left edge of its card or clipping container
//   ellipsis   text-overflow: ellipsis / line-clamp that is actually cutting text (player / team names, stat lines never truncate)
//   text-clip  text wider than its overflow:hidden box without an ellipsis (a silently cut badge or label)
//   hit-target an interactive control under 44px in either axis (inline prose links and [data-guard-ok] excepted)
export const GUARD = (opts) => {
  const W = document.documentElement.clientWidth;
  const MIN = 44;
  const out = [];
  const seen = new Set();
  const label = (el) => {
    const id = el.getAttribute("data-testid");
    const cls = typeof el.className === "string" ? el.className.trim().split(/\s+/).slice(0, 2).join(".") : "";
    return `${el.tagName.toLowerCase()}${id ? `[${id}]` : ""}${cls ? "." + cls : ""}`;
  };
  const text = (el) => (el.getAttribute("aria-label") || el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 40);
  const push = (kind, el, detail) => {
    const key = kind + label(el) + text(el);
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ kind, el: label(el), text: text(el), detail });
  };
  const cs = (el) => getComputedStyle(el);
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const s = cs(n);
      if (s.display === "none" || s.visibility === "hidden" || s.opacity === "0") return false;
      if (n.getAttribute("aria-hidden") === "true" && n !== el && !el.closest("button,a")) { /* decorative layers still count when they paint outside */ }
    }
    return true;
  };
  // A deliberate horizontal scroller (pill rows, carousels): its children may leave the viewport. Its own box is still checked.
  const scroller = (el) => { for (let n = el.parentElement; n && n !== document.body; n = n.parentElement) { const o = cs(n).overflowX; if ((o === "auto" || o === "scroll") && n.scrollWidth > n.clientWidth + 1) return n; } return null; };
  // Parked or animating layers: an off-canvas sheet / toast translated away, or anything inside an inert / closed Presence.
  const parked = (el) => { for (let n = el; n && n !== document.body; n = n.parentElement) { if (n.hasAttribute("inert") || n.getAttribute("data-state") === "closed" || n.getAttribute("data-guard-skip") != null) return true; } return false; };
  if (document.documentElement.scrollWidth > W + 1) out.push({ kind: "h-scroll", el: "html", text: "", detail: `scrollWidth ${document.documentElement.scrollWidth} > ${W}` });
  const cardOf = (el) => {
    for (let n = el.parentElement; n && n !== document.body; n = n.parentElement) {
      const s = cs(n);
      const clip = s.overflowX !== "visible";
      const box = parseFloat(s.borderTopWidth) + parseFloat(s.borderLeftWidth) + parseFloat(s.borderRightWidth) > 0 && parseFloat(s.borderTopLeftRadius) >= 6;
      const r = n.getBoundingClientRect();
      if ((clip || box) && r.width < W + 1 && r.width > 0) return n;
    }
    return null;
  };
  for (const el of document.querySelectorAll("body *")) {
    if (["SCRIPT", "STYLE", "NEXTJS-PORTAL", "svg", "path", "g", "circle", "rect", "line", "use", "defs", "clipPath"].includes(el.tagName) || el.tagName.toLowerCase().includes("nextjs")) continue;
    if (el.closest("nextjs-portal,[data-nextjs-toast]")) continue;
    if (!vis(el) || parked(el)) continue;
    const r = el.getBoundingClientRect();
    if (el.closest(".sr-only") || (r.width <= 1.5 && r.height <= 1.5)) continue; // visually hidden text for screen readers
    const pos = cs(el).position;
    const sc = scroller(el);
    // Only report the outermost offender: skip when the parent is already out in the same direction.
    if (!sc && (r.right > W + 0.5 || r.left < -0.5) && !(pos === "fixed" && r.width > W)) {
      const p = el.parentElement;
      const pr = p && p.getBoundingClientRect();
      if (!(pr && (pr.right > W + 0.5 || pr.left < -0.5))) push("offscreen", el, `x ${Math.round(r.left)}..${Math.round(r.right)} of ${W}`);
    }
    // Card containment for leaf-ish content (controls, text, badges), not for backgrounds / decorative layers.
    const leafy = el.matches("button,a,input,select,textarea,[role=img],[role=tab],[role=button]") || (el.children.length === 0 && el.textContent.trim().length > 0);
    if (leafy && !sc && pos !== "fixed") {
      const card = cardOf(el);
      // A deliberate overlay (a count badge overhanging its button) is not clipped unless its container actually clips it.
      if (card && !(pos === "absolute" && cs(card).overflowX === "visible")) {
        const c = card.getBoundingClientRect();
        if (r.right > c.right + 1 || r.left < c.left - 1) {
          const p = el.parentElement;
          const pr = p.getBoundingClientRect();
          if (!(pr.right > c.right + 1 || pr.left < c.left - 1) || p === card) push("clipped", el, `box ${Math.round(r.left)}..${Math.round(r.right)} vs ${label(card)} ${Math.round(c.left)}..${Math.round(c.right)}`);
        }
      }
    }
    // Text cut: ellipsis in action, or silently clipped in an overflow box.
    const s = cs(el);
    if (el.children.length === 0 && el.textContent.trim() && !opts?.allowEllipsis?.some((q) => el.closest(q))) {
      const ell = s.textOverflow === "ellipsis";
      const clamp = s.webkitLineClamp && s.webkitLineClamp !== "none";
      if (ell && el.scrollWidth > el.clientWidth + 1) push("ellipsis", el, `"${text(el)}" scroll ${el.scrollWidth} > ${el.clientWidth}`);
      else if (clamp && el.scrollHeight > el.clientHeight + 2) push("ellipsis", el, `line-clamp cuts "${text(el)}"`);
      else if (!ell && s.overflowX !== "visible" && el.scrollWidth > el.clientWidth + 1) push("text-clip", el, `scroll ${el.scrollWidth} > ${el.clientWidth}`);
    }
    // Ellipsis on a wrapper whose descendants are the text (a truncate span holding nested spans).
    if (el.children.length > 0 && s.textOverflow === "ellipsis" && el.scrollWidth > el.clientWidth + 1 && !opts?.allowEllipsis?.some((q) => el.closest(q))) push("ellipsis", el, `"${text(el)}" scroll ${el.scrollWidth} > ${el.clientWidth}`);
    if (el.children.length > 0 && s.webkitLineClamp && s.webkitLineClamp !== "none" && el.scrollHeight > el.clientHeight + 2 && !opts?.allowEllipsis?.some((q) => el.closest(q))) push("ellipsis", el, `line-clamp cuts "${text(el)}"`);
    // Hit target.
    if (el.matches("button,a[href],[role=button],[role=tab],[role=switch],[role=checkbox],select,input:not([type=hidden]):not([type=checkbox]):not([type=radio]),textarea") && !el.closest("[data-guard-ok]")) {
      // A link or term button inside a sentence (display: inline, with prose around it) is read as text, not a stand-alone control.
      const inProse = (el.tagName === "A" && el.closest("p,li") && el.textContent.trim().length > 12) || (s.display === "inline" && el.parentElement && (el.parentElement.textContent || "").trim().length > el.textContent.trim().length + 8);
      if ((r.width < MIN - 0.5 || r.height < MIN - 0.5) && !inProse && !(el.closest("label") && el.matches("input"))) push("hit-target", el, `${Math.round(r.width)}x${Math.round(r.height)}`);
    }
  }
  return out;
};

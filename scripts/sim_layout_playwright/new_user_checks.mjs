// Elements whose box ends past the viewport (outside a deliberate horizontal scroller): the culprits when the document scrolls sideways. Innermost first.
export const OFFENDERS = () => {
  const W = document.documentElement.clientWidth;
  const sel = (el) => { const id = el.getAttribute("data-testid"); const cls = typeof el.className === "string" ? el.className.trim().split(/\s+/).slice(0, 3).join(".") : ""; return `${el.tagName.toLowerCase()}${id ? `[data-testid=${id}]` : ""}${cls ? "." + cls : ""}`; };
  const inScroller = (el) => { for (let n = el.parentElement; n && n !== document.body; n = n.parentElement) { const o = getComputedStyle(n).overflowX; if (o === "auto" || o === "scroll" || o === "hidden" || o === "clip") return true; } return false; };
  const bad = [];
  for (const el of document.querySelectorAll("body *")) {
    if (el.closest("nextjs-portal,[data-nextjs-toast]") || ["SCRIPT", "STYLE"].includes(el.tagName)) continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0 || (r.right <= W + 1 && r.left >= -1) || inScroller(el)) continue;
    bad.push(el);
  }
  // Innermost offenders (no offending descendant) are the elements that actually hold the too-wide content; each is listed with its ancestor chain's widths so a wide wrapper is visible too.
  const set = new Set(bad);
  const leaves = bad.filter((el) => ![...el.querySelectorAll("*")].some((d) => set.has(d)));
  return leaves.slice(0, 8).map((el) => {
    const r = el.getBoundingClientRect();
    const chain = []; for (let n = el.parentElement; n && n !== document.documentElement && chain.length < 12; n = n.parentElement) chain.push(`${sel(n)} w=${Math.round(n.getBoundingClientRect().width)}`);
    return `${sel(el)} right=${Math.round(r.right)} w=${Math.round(r.width)} "${(el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 30)}" <- ${chain.join(" < ")}`;
  });
};

// First-module offset (docs/audits/2026-11-ui-audit-e2e.md P0-2, batch B): how far below the sticky nav (shell header + page tab strip) the first
// piece of page content starts. Walks into layout wrappers (no background/border/shadow) until it reaches a card, a control row or a heading.
export const FIRST_MODULE = () => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 4 && r.height > 4 && cs.display !== "none" && cs.visibility !== "hidden" && cs.position !== "absolute" && !el.classList.contains("sr-only"); };
  const sticky = [...document.querySelectorAll(".shell-header, .pill-row-glass, body > header, [data-testid=sim-game-header]")].filter((el) => { const r = el.getBoundingClientRect(); return r.height > 0 && r.top < 140; });
  const navBottom = Math.max(0, ...sticky.map((el) => el.getBoundingClientRect().bottom));
  const isChrome = (el) => el.matches(".pill-row-glass, [data-testid=page-tab-bar]") || Boolean(el.querySelector(":scope > .pill-row-glass"));
  const isCard = (el) => { const cs = getComputedStyle(el); const bg = cs.backgroundColor; return (bg && bg !== "rgba(0, 0, 0, 0)" && bg !== "transparent") || cs.boxShadow !== "none" || parseFloat(cs.borderTopWidth) > 0 || cs.backdropFilter !== "none" && cs.backdropFilter !== undefined || el.matches("button,input,select,h1,h2,h3,p,[role=tablist]"); };
  let node = document.querySelector("main");
  if (!node) return null;
  for (let depth = 0; depth < 8; depth += 1) {
    const kids = [...node.children].filter((el) => vis(el) && !isChrome(el) && !el.matches("nextjs-portal,script,style"));
    if (!kids.length) break;
    const k = kids[0];
    if (isCard(k) || !k.children.length) { node = k; break; }
    node = k;
  }
  // First card/row: the first visible surface (shadow, backdrop blur or a list row) at least 48px tall that is not a control or the tab strip; what the owner means by "the first module".
  const cardEl = [...document.querySelectorAll("main *")].find((el) => {
    if (!vis(el) || isChrome(el) || el.closest(".pill-row-glass, [data-testid=sim-game-header]") || el.matches("button,input,select,a,[role=tab],[role=tablist]")) return false;
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.height >= 48 && r.width >= 200 && (cs.boxShadow !== "none" || (cs.backdropFilter && cs.backdropFilter !== "none") || el.matches("[data-testid$=-row],[data-testid=player-accordion-row]"));
  });
  const cardGap = cardEl ? Math.round(cardEl.getBoundingClientRect().top + scrollY - navBottom) : null;
  const r = node.getBoundingClientRect();
  const id = node.getAttribute("data-testid");
  const cid = cardEl && cardEl.getAttribute("data-testid");
  return { cardGap, card: cardEl ? `${cardEl.tagName.toLowerCase()}${cid ? `[${cid}]` : ""}` : null, top: Math.round(r.top + scrollY), navBottom: Math.round(navBottom), gap: Math.round(r.top + scrollY - navBottom), el: `${node.tagName.toLowerCase()}${id ? `[${id}]` : ""}`, text: (node.textContent || "").replace(/\s+/g, " ").trim().slice(0, 40) };
};

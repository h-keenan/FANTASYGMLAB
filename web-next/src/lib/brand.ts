// Single source of truth for the product's display name — mirrors
// modules/brand_identity.py's PRODUCT_NAME on the Python side. Added during
// the FantasyGM Lab -> FantasyDesk rebrand (2026-10-17): the name was
// previously a literal string duplicated in Header.tsx, GmOrb.tsx,
// LoadingScreen.tsx, and layout.tsx's metadata, so a future rename needs
// one edit instead of four.
export const BRAND_NAME = "FantasyDesk";

// Public site domain — mirrors modules/brand_identity.py's PRODUCT_DOMAIN
// (the URL modules/share_card_qr.py encodes in every share-card QR, and
// the one mobile's ShareCardChrome QR points at). Shown on share cards.
export const BRAND_DOMAIN = "fantasygmlab.com";

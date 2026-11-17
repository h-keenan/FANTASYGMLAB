/**
 * Account page section titles and their order, one definition for web and app (byte-identical lib twin). The app's
 * settings hub carries extra sections (saved leagues, notifications, about, legal) between Preferences and
 * Account actions; the shared ones must keep this relative order.
 */

export const ACCOUNT_SECTION_ORDER = ["identity", "billing", "preferences", "actions", "danger"] as const;

export type AccountSectionKey = (typeof ACCOUNT_SECTION_ORDER)[number];

export const ACCOUNT_SECTION_TITLE: Record<AccountSectionKey, string> = {
  identity: "Identity",
  billing: "Billing",
  preferences: "Preferences",
  actions: "Account actions",
  danger: "Delete account",
};

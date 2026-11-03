import type { ReactNode } from "react";

import { pageMetadata } from "@/lib/pageMetadata";

export const metadata = pageMetadata("live-draft");

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}

import type { ReactNode } from "react";

import { pageMetadata } from "@/lib/pageMetadata";

export const metadata = pageMetadata("my-team");

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}

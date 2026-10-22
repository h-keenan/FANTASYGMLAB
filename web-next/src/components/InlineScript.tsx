/**
 * A synchronous inline <script> that runs while the browser parses the
 * server HTML, before first paint. Taken from Next's own "Preventing flash
 * before hydration" guide (node_modules/next/dist/docs/01-app/02-guides/
 * preventing-flash-before-hydration.md). Rendered as `text/javascript` on
 * the server, and as inert `text/plain` on the client. Scripts inserted by
 * a client-side render never execute anyway, and the type swap avoids
 * React's dev warning about rendering <script> tags. `suppressHydrationWarning`
 * covers that server/client type mismatch.
 */
export function InlineScript({ html }: { html: string }) {
  return (
    <script
      type={typeof window === "undefined" ? "text/javascript" : "text/plain"}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

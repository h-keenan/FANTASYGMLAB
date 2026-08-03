# Streamlit chrome removal

DynastyGM removes the production Streamlit toolbar in two layers:

1. `.streamlit/config.toml` uses Streamlit's supported `client.toolbarMode = "minimal"` setting. This removes developer, rerun, cache, deploy, share, and menu actions before rendering.
2. The remaining empty 60-pixel Streamlit header shell is hidden by the shared production style layer, along with Streamlit menu, decoration, status, fullscreen-element toolbar, and collapsed-sidebar controls. Streamlit 1.58 does not expose a supported configuration setting that removes this empty header container itself. The `stScreencast` node is deliberately retained because in Streamlit 1.58 it is the application root, not a disposable toolbar control.

Global styles use Streamlit's public `st.html` API. A style-only `st.html` body does not create the empty flex rows produced by Markdown-based style injection, so the application workspace begins at the normal content safe area without a blank strip.

## Compatibility boundary

The `toolbarMode` setting and `st.html` call are supported APIs. The final header-shell removal uses stable `data-testid` selectors because Streamlit exposes no public header-removal API. Those selectors are an intentional compatibility boundary and are covered by deterministic Chromium validation. A future Streamlit upgrade must pass the chrome visibility and reclaimed-space assertions before deployment.

Streamlit dialogs, error messages, and runtime accessibility semantics remain available. They are application functionality, not navigation chrome.

## Navigation recommendation

The existing GM Orb should remain the primary Founder navigation for now. A custom top command bar is technically feasible inside the DynastyGM application shell, but it should be evaluated as a separate navigation product change rather than coupled to framework-chrome removal.

from __future__ import annotations

import secrets
import time
from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from modules import account_store
from modules import auth_restore_lifecycle
from modules import auth_storage_handshake
from modules import auth_supabase
from modules import startup_coordinator
from modules import startup_critical_path
from modules import user_preferences

AUTH_STORAGE_COMPONENT = st.components.v2.component(
    "supabase_auth_storage",
    html="""<div id="supabase-auth-storage-root" aria-hidden="true"></div>""",
    js="""
    export default function(component) {
      const { data, setTriggerValue } = component
      const storageKey = (data && data.storageKey) || "dynastygm_supabase_auth_v2"
      const legacyKeys = (data && data.legacyStorageKeys) || ["dynastygm_supabase_auth"]
      const command = (data && data.command) || "read"
      const hasSession = Boolean(data && data.hasSession)
      const requestId = String((data && data.requestId) || "")
      const deadlineMs = Math.max(
        500,
        Math.min(5000, Number((data && data.deadlineMs) || 3000) || 3000)
      )
      window.__dynastyGmSupabaseAuthHasSession = hasSession
      const jsEntryMs = (typeof performance !== "undefined" && performance.now)
        ? performance.now()
        : 0
      const jsEntryWallMs = Date.now()

      const browserInstanceId = (() => {
        try {
          const key = "__fgl_browser_instance_id"
          let id = window.sessionStorage.getItem(key)
          if (!id) {
            id = "b" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4)
            window.sessionStorage.setItem(key, id)
          }
          return id
        } catch (error) {
          return ""
        }
      })()

      const parentDoc = (() => {
        try {
          if (window.parent && window.parent !== window && window.parent.document) {
            return window.parent.document
          }
        } catch (error) {}
        return document
      })()

      const handshakeBase = (reason) => ({
        reason: reason || "",
        request_id: requestId,
        browser_instance_id: browserInstanceId,
        js_entry_ms: Math.round(jsEntryMs * 10) / 10,
        js_entry_wall_ms: jsEntryWallMs,
        visibility: (parentDoc && parentDoc.visibilityState)
          ? parentDoc.visibilityState
          : ((typeof document !== "undefined" && document.visibilityState) || ""),
        hidden: Boolean(
          parentDoc
            ? parentDoc.hidden
            : (typeof document !== "undefined" && document.hidden)
        ),
        ready_state: (parentDoc && parentDoc.readyState) || "",
        probe_document: (parentDoc === document) ? "same" : "parent",
        emit_wall_ms: Date.now(),
      })

      let emitted = false
      const emit = (name, payload) => {
        if (emitted) return
        emitted = true
        const body = { ...(payload || {}) }
        const diag = {
          ...handshakeBase(body._resume_reason || body.reason || name),
          localStorage_read_ms: body._localStorage_read_ms,
          js_emit_ms: (typeof performance !== "undefined" && performance.now)
            ? Math.round((performance.now() - jsEntryMs) * 10) / 10
            : null,
          deadline_ms: deadlineMs,
        }
        delete body._localStorage_read_ms
        setTriggerValue(name, {
          ...body,
          ts: Date.now(),
          request_id: requestId,
          browser_instance_id: browserInstanceId,
          _handshake: diag,
        })
      }

      const readRaw = () => {
        const t0 = (typeof performance !== "undefined" && performance.now)
          ? performance.now()
          : 0
        let raw = window.localStorage.getItem(storageKey)
        if (!raw) {
          for (const legacy of legacyKeys) {
            raw = window.localStorage.getItem(legacy)
            if (raw) {
              try {
                window.localStorage.setItem(storageKey, raw)
                window.localStorage.removeItem(legacy)
              } catch (error) {}
              break
            }
          }
        }
        const readMs = (typeof performance !== "undefined" && performance.now)
          ? Math.round((performance.now() - t0) * 10) / 10
          : 0
        return { raw, readMs }
      }

      const readStoredAuth = (reason) => {
        const { raw, readMs } = readRaw()
        if (!raw) {
          emit("status", {
            action: "read",
            ok: true,
            reason,
            durableAuthPresent: false,
            _localStorage_read_ms: readMs,
          })
          return
        }
        try {
          const stored = JSON.parse(raw)
          emit(
            "stored",
            stored && typeof stored === "object"
              ? { ...stored, _resume_reason: reason, _localStorage_read_ms: readMs }
              : { _localStorage_read_ms: readMs, _resume_reason: reason }
          )
        } catch (error) {
          emit("status", {
            action: "read",
            ok: false,
            reason: "parse_error",
            durableAuthPresent: false,
            _localStorage_read_ms: readMs,
          })
        }
      }

      const parentLocation = () => {
        try {
          if (window.parent && window.parent !== window && window.parent.location) {
            return window.parent.location
          }
        } catch (error) {}
        return window.location
      }

      const clearAuthParamsFromUrl = (loc) => {
        try {
          const url = new URL(loc.href)
          ;["token_hash", "token", "type", "code", "error", "error_description", "error_code"].forEach((key) => {
            url.searchParams.delete(key)
          })
          const clean = url.pathname + (url.searchParams.toString() ? "?" + url.searchParams.toString() : "")
          const win = (window.parent && window.parent !== window) ? window.parent : window
          win.history.replaceState(null, "", clean)
        } catch (error) {}
      }

      // Email confirmation return: hash tokens (implicit) or token_hash query.
      const consumeAuthCallback = () => {
        if (hasSession || command !== "read") return false
        try {
          const loc = parentLocation()
          let access = ""
          let refresh = ""
          let expiresIn = ""
          let type = ""
          if (loc.hash && loc.hash.indexOf("access_token") >= 0) {
            const params = new URLSearchParams(String(loc.hash || "").replace(/^#/, ""))
            access = params.get("access_token") || ""
            refresh = params.get("refresh_token") || ""
            expiresIn = params.get("expires_in") || ""
            type = params.get("type") || "signup"
            try {
              const win = (window.parent && window.parent !== window) ? window.parent : window
              win.history.replaceState(null, "", loc.pathname + loc.search)
            } catch (error) {}
          }
          const query = new URLSearchParams(loc.search || "")
          const tokenHash = query.get("token_hash") || query.get("token") || ""
          const queryType = query.get("type") || type || "signup"
          if (tokenHash) {
            clearAuthParamsFromUrl(loc)
            emit("auth_callback", {
              flow: "token_hash",
              token_hash: tokenHash,
              type: queryType,
              _resume_reason: "email_confirm_callback",
            })
            return true
          }
          if (access && refresh) {
            emit("auth_callback", {
              flow: "implicit",
              access_token: access,
              refresh_token: refresh,
              expires_in: expiresIn,
              type: type || "signup",
              _resume_reason: "email_confirm_callback",
            })
            return true
          }
        } catch (error) {}
        return false
      }

      const installResumeHooks = () => {
        const hookKey = "__dynastyGmSupabaseAuthResumeInstalled"
        if (window[hookKey]) return
        window[hookKey] = true
        const resumeRead = (reason) => {
          if (emitted) return
          try {
            readStoredAuth(reason)
          } catch (error) {
            emit("status", { action: "resume_read", ok: false, reason })
          }
        }
        window.addEventListener("pageshow", (event) => {
          if (window.__dynastyGmSupabaseAuthHasSession) return
          resumeRead(event && event.persisted ? "pageshow_persisted" : "pageshow")
        })
        window.addEventListener("focus", () => {
          if (!window.__dynastyGmSupabaseAuthHasSession) resumeRead("focus")
        })
        document.addEventListener("visibilitychange", () => {
          if (!window.__dynastyGmSupabaseAuthHasSession && document.visibilityState === "visible") {
            resumeRead("visibilitychange")
          }
        })
      }

      // #242: Wake Streamlit within deadline even if initial_read is starved
      // (iframe mount delay, tab backgrounding, websocket queue). Without this,
      // a single Python st.stop() waits indefinitely for setTriggerValue.
      const installStartupDeadline = () => {
        if (hasSession || command !== "read") return
        const timerKey = "__dynastyGmAuthStorageDeadline_" + (requestId || "na")
        if (window[timerKey]) return
        window[timerKey] = true
        try {
          setTimeout(() => {
            if (emitted) return
            try {
              const { raw, readMs } = readRaw()
              if (raw) {
                try {
                  const stored = JSON.parse(raw)
                  emit(
                    "stored",
                    stored && typeof stored === "object"
                      ? {
                          ...stored,
                          _resume_reason: "startup_deadline",
                          _localStorage_read_ms: readMs,
                        }
                      : {
                          _resume_reason: "startup_deadline",
                          _localStorage_read_ms: readMs,
                        }
                  )
                  return
                } catch (error) {}
              }
              emit("status", {
                action: "read",
                ok: true,
                reason: "startup_deadline",
                durableAuthPresent: Boolean(raw),
                _localStorage_read_ms: readMs,
              })
            } catch (error) {
              emit("status", {
                action: "read",
                ok: true,
                reason: "startup_deadline",
                durableAuthPresent: false,
              })
            }
          }, deadlineMs)
        } catch (error) {}
      }

      try {
        if (command === "save") {
          const session = (data && data.session) || {}
          window.localStorage.setItem(storageKey, JSON.stringify(session))
          for (const legacy of legacyKeys) {
            try { window.localStorage.removeItem(legacy) } catch (error) {}
          }
          // #240: do not setTriggerValue on save — timestamped emits remount
          // Streamlit and can erase a just-painted Dashboard.
          return
        }
        if (command === "clear") {
          window.localStorage.removeItem(storageKey)
          for (const legacy of legacyKeys) {
            try { window.localStorage.removeItem(legacy) } catch (error) {}
          }
          // #240: clear without Streamlit remount trigger.
          return
        }
        installResumeHooks()
        installStartupDeadline()
        if (hasSession) {
          // Settled authenticated session (reason: session_present):
          // skip timestamped status emit every run — setTriggerValue remounts
          // Streamlit and can erase a just-painted Dashboard (#240).
          return
        }
        if (consumeAuthCallback()) {
          return
        }
        readStoredAuth("initial_read")
      } catch (error) {
        emit("status", { action: command, ok: false, reason: "js_error" })
      }
    }
    """,
    isolate_styles=False,
)


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _auth_email(session_state) -> str:
    return _safe_text(session_state.get(auth_supabase.AUTH_EMAIL_KEY))


def _confirmation_email(session_state) -> str:
    return _safe_text(
        session_state.get(auth_supabase.CONFIRMATION_EMAIL_KEY)
        or session_state.get("launch_account_login_email")
        or session_state.get("launch_account_signup_email")
        or _auth_email(session_state)
    )


def render_confirmation_required_card(*, config: dict, email: str = "", key_prefix: str = "account") -> None:
    st.markdown(
        "<div class='account-confirm-card' data-fgl-confirm='1'>"
        "<div class='account-confirm-title'>Check your email</div>"
        "<div class='account-confirm-copy'>"
        "We sent a confirmation link. Click it to finish creating your account. "
        "Your account is not active yet — you are not signed in."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    clean_email = _safe_text(email)
    if clean_email:
        st.caption(f"Sent to {clean_email}")
    else:
        st.info("Enter your email address, then request another confirmation email.")
        return
    now = int(time.time())
    last_sent = int(st.session_state.get(auth_supabase.CONFIRMATION_RESEND_TS_KEY) or 0)
    cooldown_remaining = max(0, auth_supabase.CONFIRMATION_RESEND_COOLDOWN_SECONDS - (now - last_sent))
    if cooldown_remaining > 0:
        st.caption("You can request another email in a moment.")
    elif st.button(
        "Resend confirmation",
        key=f"{key_prefix}_resend_confirmation_email",
        use_container_width=True,
    ):
        sent, error = auth_supabase.resend_signup_confirmation(config, clean_email)
        st.session_state[auth_supabase.CONFIRMATION_RESEND_TS_KEY] = now
        if sent:
            st.success("Confirmation email sent. Check your inbox and spam folder.")
        else:
            st.warning(
                auth_supabase.signup_user_message(error)
                if error
                else "We could not send another confirmation email right now. Please try again in a moment."
            )


def flush_durable_auth_persistence(
    session_state: MutableMapping[str, Any] | None = None,
    *,
    config: dict | None = None,
) -> dict[str, Any]:
    """Persist durable auth to localStorage on the current run — no st.rerun().

    #240: Post-Dashboard remounts were erasing visible content. The save/clear
    command is executed via the auth storage component without setTriggerValue
    (see component JS) so Streamlit does not tear down the painted Dashboard.
    """

    state = session_state if session_state is not None else st.session_state
    result = {
        "flushed": False,
        "command": "",
        "error": "",
    }
    cfg = config if isinstance(config, dict) else {}
    if cfg and not auth_supabase.is_configured(cfg):
        result["error"] = "auth_not_configured"
        return result

    command = ""
    session_payload = None
    if state.pop(auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY, False):
        command = "clear"
    elif auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY in state:
        command = "save"
        session_payload = state.pop(auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY, None)
    if not command:
        return result

    try:
        AUTH_STORAGE_COMPONENT(
            key="supabase_auth_storage_flush",
            data={
                "command": command,
                "storageKey": auth_supabase.DURABLE_AUTH_STORAGE_KEY,
                "legacyStorageKeys": list(auth_supabase.DURABLE_AUTH_LEGACY_STORAGE_KEYS),
                "session": session_payload or {},
                "hasSession": True,
            },
            width=1,
            height=1,
        )
    except ValueError as exc:
        if "is not registered" not in str(exc):
            raise
        result["error"] = "component_unavailable"
        # Re-queue so a later opportunity can retry without forcing remount loops.
        if command == "save" and session_payload:
            state[auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY] = session_payload
        elif command == "clear":
            state[auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY] = True
        return result
    except Exception as exc:
        result["error"] = type(exc).__name__
        return result

    result["flushed"] = True
    result["command"] = command
    return result


def render_durable_auth_bridge(*, config: dict) -> dict:
    actions = {
        "restored": False,
        "refreshed": False,
        "cleared": False,
        "pending": False,
        "identical": False,
        "storage_available": False,
        "storage_requested": False,
        "timed_out": False,
        "late_reconcile": False,
        "error": "",
        "resume_reason": "",
        "request_id": "",
    }
    if not auth_supabase.is_configured(config):
        auth_restore_lifecycle.advance_phase(
            st.session_state,
            auth_restore_lifecycle.RestorePhase.AUTH_RESOLVED,
        )
        return actions

    command = "read"
    session_payload = None
    if st.session_state.pop(auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY, False):
        command = "clear"
        actions["cleared"] = True
    elif auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY in st.session_state:
        command = "save"
        session_payload = st.session_state.pop(auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY, None)

    already_authenticated = bool(auth_supabase.current_user_id(st.session_state))
    if command == "read" and already_authenticated:
        # Returning run with settled auth: do not re-issue a storage restore request.
        auth_restore_lifecycle.advance_phase(
            st.session_state,
            auth_restore_lifecycle.RestorePhase.AUTH_RESOLVED,
        )
        startup_critical_path.clear_late_auth_reconcile(st.session_state)

    request_id = ""
    if command == "read" and not already_authenticated:
        actions["storage_requested"] = auth_restore_lifecycle.mark_storage_requested(
            st.session_state
        )
        request_id = str(st.session_state.get(auth_storage_handshake.REQUEST_ID_KEY) or "")
        if actions["storage_requested"] or not request_id:
            request_id = secrets.token_hex(4)
            st.session_state[auth_storage_handshake.REQUEST_ID_KEY] = request_id
            auth_storage_handshake.mark_request_emitted(
                st.session_state,
                request_id=request_id,
            )
        if actions["storage_requested"]:
            startup_coordinator.log_startup_milestone(
                st.session_state,
                "auth_storage_requested",
                once=True,
                detail={
                    "request_id": request_id,
                    "deadline_ms": startup_critical_path.AUTH_STORAGE_CLIENT_DEADLINE_MS,
                },
            )
    actions["request_id"] = request_id

    try:
        auth_storage_handshake.mark_component_mount_start(st.session_state)
        result = AUTH_STORAGE_COMPONENT(
            key="supabase_auth_storage_bridge",
            data={
                "command": command,
                "storageKey": auth_supabase.DURABLE_AUTH_STORAGE_KEY,
                "legacyStorageKeys": list(auth_supabase.DURABLE_AUTH_LEGACY_STORAGE_KEYS),
                "session": session_payload or {},
                "hasSession": already_authenticated,
                "requestId": request_id,
                "deadlineMs": int(startup_critical_path.AUTH_STORAGE_CLIENT_DEADLINE_MS),
            },
            width=1,
            height=1,
        )
    except ValueError as exc:
        if "is not registered" not in str(exc):
            raise
        actions["error"] = "Browser auth storage is unavailable; using session-only login."
        auth_restore_lifecycle.advance_phase(
            st.session_state,
            auth_restore_lifecycle.RestorePhase.AUTH_RESOLVED,
        )
        return actions

    actions["storage_available"] = True
    status = getattr(result, "status", None)
    auth_callback = getattr(result, "auth_callback", None)
    if isinstance(auth_callback, dict) and auth_callback:
        actions["resume_reason"] = _safe_text(
            auth_callback.get("_resume_reason"), "email_confirm_callback"
        )
        payload = None
        error = ""
        flow = _safe_text(auth_callback.get("flow"))
        if flow == "token_hash":
            payload, error = auth_supabase.verify_email_token_hash(
                config,
                token_hash=_safe_text(auth_callback.get("token_hash")),
                token_type=_safe_text(auth_callback.get("type"), "signup"),
            )
        else:
            # Implicit hash tokens from Supabase verify redirect.
            candidate = {
                "access_token": _safe_text(auth_callback.get("access_token")),
                "refresh_token": _safe_text(auth_callback.get("refresh_token")),
                "expires_in": auth_callback.get("expires_in"),
                "token_type": "bearer",
                "user": auth_callback.get("user")
                if isinstance(auth_callback.get("user"), dict)
                else {},
            }
            if auth_supabase.durable_payload_valid(candidate) or candidate["access_token"]:
                # Fetch user if missing so confirmation + profile bootstrap can run.
                if not candidate["user"]:
                    user_payload, user_error = auth_supabase.fetch_auth_user(
                        config, candidate["access_token"]
                    )
                    if user_error:
                        error = user_error
                    elif isinstance(user_payload, dict):
                        candidate["user"] = user_payload
                if not error:
                    payload = candidate
            else:
                error = "Confirmation link did not include a usable session."
        if payload and not error:
            if auth_supabase.signup_requires_email_confirmation(payload):
                auth_supabase.mark_confirmation_required(
                    st.session_state,
                    _safe_text((payload.get("user") or {}).get("email")),
                )
                st.session_state["account_signup_check_email"] = True
                actions["error"] = "Email is not confirmed yet."
            else:
                auth_supabase.apply_auth_payload(st.session_state, payload)
                auth_supabase.queue_durable_auth_save(st.session_state, payload)
                actions["restored"] = True
                st.session_state["auth_restore_last_result"] = "email_confirm_callback"
                st.session_state["account_resume_notice"] = (
                    "Email confirmed. Your account is ready."
                )
                auth_restore_lifecycle.advance_phase(
                    st.session_state,
                    auth_restore_lifecycle.RestorePhase.AUTH_RESOLVED,
                )
                startup_critical_path.clear_late_auth_reconcile(st.session_state)
                return actions
        if error:
            actions["error"] = error
            auth_supabase.mark_confirmation_required(st.session_state)
            st.session_state["account_signup_check_email"] = True
        auth_restore_lifecycle.advance_phase(
            st.session_state,
            auth_restore_lifecycle.RestorePhase.AUTH_RESOLVED,
        )
        return actions
    if isinstance(status, dict):
        st.session_state["auth_restore_last_status"] = {
            "action": _safe_text(status.get("action")),
            "ok": bool(status.get("ok", True)),
            "reason": _safe_text(status.get("reason")),
            "durable_auth_present": bool(status.get("durableAuthPresent")),
            "request_id": _safe_text(status.get("request_id") or request_id),
            "browser_instance_id": _safe_text(status.get("browser_instance_id")),
        }
        if command == "read" and not already_authenticated:
            auth_storage_handshake.record_payload_received(
                st.session_state,
                payload=status,
                source="status",
            )
            # Client deadline woke us without a stored session — continue guest,
            # keep late-reconcile armed so a later stored emit can restore.
            if _safe_text(status.get("reason")) == "startup_deadline":
                actions["timed_out"] = True
                startup_critical_path.arm_late_auth_reconcile(st.session_state)
                auth_restore_lifecycle.advance_phase(
                    st.session_state,
                    auth_restore_lifecycle.RestorePhase.AUTH_RESOLVED,
                )
                startup_coordinator.log_startup_milestone(
                    st.session_state,
                    "auth_storage_deadline",
                    once=True,
                    detail={
                        "request_id": request_id,
                        "durable_auth_present": bool(status.get("durableAuthPresent")),
                    },
                )
                return actions
    if isinstance(status, dict) and status.get("ok") is False:
        actions["error"] = "Browser auth storage is unavailable; using session-only login."
        st.session_state["auth_restore_last_result"] = "storage_error"
        auth_restore_lifecycle.advance_phase(
            st.session_state,
            auth_restore_lifecycle.RestorePhase.AUTH_RESOLVED,
        )
        return actions
    if command != "read" or already_authenticated:
        if already_authenticated:
            auth_restore_lifecycle.advance_phase(
                st.session_state,
                auth_restore_lifecycle.RestorePhase.AUTH_RESOLVED,
            )
        return actions

    stored = getattr(result, "stored", None)
    if command == "read" and status is None and stored is None:
        actions["pending"] = True
        auth_storage_handshake.record_pending_return(st.session_state)
        auth_restore_lifecycle.advance_phase(
            st.session_state,
            auth_restore_lifecycle.RestorePhase.STORAGE_PENDING,
        )
        return actions
    if not isinstance(stored, dict) or not stored:
        # Empty storage → guest. Auth is resolved (as signed-out).
        auth_restore_lifecycle.advance_phase(
            st.session_state,
            auth_restore_lifecycle.RestorePhase.AUTH_RESOLVED,
        )
        return actions

    auth_storage_handshake.record_payload_received(
        st.session_state,
        payload=stored,
        source="stored",
    )
    if auth_restore_lifecycle.mark_storage_received(st.session_state):
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "auth_storage_received",
            once=True,
            detail={
                "request_id": _safe_text(stored.get("request_id") or request_id),
                "browser_instance_id": _safe_text(stored.get("browser_instance_id")),
                "resume_reason": _safe_text(stored.get("_resume_reason"), "stored_auth")[:32],
            },
        )

    resume_reason = _safe_text(stored.get("_resume_reason"), "stored_auth")
    actions["resume_reason"] = resume_reason
    st.session_state["auth_restore_last_reason"] = resume_reason
    if startup_critical_path.late_auth_reconcile_armed(st.session_state):
        actions["late_reconcile"] = True

    normalized = auth_supabase.durable_auth_payload(stored)
    if auth_restore_lifecycle.is_identical_auth_payload(st.session_state, normalized):
        actions["identical"] = True
        st.session_state["auth_restore_last_result"] = "identical"
        auth_restore_lifecycle.advance_phase(
            st.session_state,
            auth_restore_lifecycle.RestorePhase.AUTH_RESOLVED,
        )
        startup_critical_path.clear_late_auth_reconcile(st.session_state)
        return actions

    apply_started = time.perf_counter()
    restored, error, refreshed = auth_supabase.restore_auth_payload(
        config,
        st.session_state,
        stored,
    )
    auth_storage_handshake.record_python_apply(
        st.session_state,
        apply_ms=(time.perf_counter() - apply_started) * 1000,
        refreshed=bool(refreshed),
    )
    actions["restored"] = restored
    actions["refreshed"] = refreshed
    actions["error"] = error
    st.session_state["auth_restore_last_result"] = "restored" if restored else "restore_failed"
    st.session_state["auth_restore_last_refreshed"] = bool(refreshed)
    if restored:
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "auth_payload_applied",
            once=True,
            detail={
                "late_reconcile": bool(actions["late_reconcile"]),
                "request_id": request_id,
            },
        )
        auth_restore_lifecycle.advance_phase(
            st.session_state,
            auth_restore_lifecycle.RestorePhase.AUTH_RESOLVED,
        )
        startup_critical_path.clear_late_auth_reconcile(st.session_state)
    if not restored and error:
        # Never clear a potentially valid durable session solely because the
        # bridge was late — only clear on explicit restore failure with error.
        auth_supabase.queue_durable_auth_clear(st.session_state)
        auth_restore_lifecycle.clear_restore_lifecycle(st.session_state)
    return actions


def render_account_panel(
    *,
    config: dict,
    username: str = "",
    selected_league_id: str = "",
    selected_league_name: str = "",
    my_roster_id=None,
) -> dict:
    actions = {
        "resume_league": None,
        "saved": False,
        "logged_in": False,
    }
    st.markdown("---")
    st.subheader("Account")
    if not auth_supabase.is_configured(config):
        st.caption("Accounts are unavailable in this environment. Guest mode is active.")
        st.session_state.setdefault(auth_supabase.ACCOUNT_MODE_KEY, "guest")
        return actions

    session = auth_supabase.current_auth_session(st.session_state)
    user_id = auth_supabase.current_user_id(st.session_state)
    access_token = auth_supabase.current_access_token(st.session_state)
    if user_id and access_token:
        actions["logged_in"] = True
        email = _auth_email(st.session_state)
        st.caption(f"Signed in as {email or 'account user'}")
        button_cols = st.columns(2)
        with button_cols[0]:
            if st.button("Save league", key="account_save_current_league", use_container_width=True):
                saved, error = save_current_context(
                    config=config,
                    access_token=access_token,
                    user_id=user_id,
                    email=email,
                    username=username,
                    selected_league_id=selected_league_id,
                    selected_league_name=selected_league_name,
                    my_roster_id=my_roster_id,
                )
                actions["saved"] = saved
                if saved:
                    st.success("Saved.")
                    st.session_state.pop("account_saved_leagues_cache", None)
                else:
                    st.warning("Could not save this league right now. Please try again.")
        with button_cols[1]:
            if st.button("Log out", key="account_logout", use_container_width=True):
                error = auth_supabase.sign_out(config, access_token)
                auth_supabase.queue_durable_auth_clear(st.session_state)
                auth_supabase.clear_auth_session(st.session_state)
                st.session_state.pop("account_saved_leagues_cache", None)
                startup_coordinator.reset_startup_coordinator(st.session_state)
                if error:
                    st.warning(error)
                st.rerun()

        saved_rows = st.session_state.get("account_saved_leagues_cache")
        if not isinstance(saved_rows, list):
            saved_rows, error = account_store.fetch_saved_leagues(
                config,
                access_token,
                user_id=user_id,
            )
            if error:
                st.caption("Saved leagues could not be loaded right now.")
                saved_rows = []
            st.session_state["account_saved_leagues_cache"] = saved_rows
        if saved_rows:
            option_labels = {
                saved_league_label(row): row
                for row in saved_rows
                if _safe_text(row.get("league_id"))
            }
            selected_label = st.selectbox(
                "Saved league",
                list(option_labels.keys()),
                key="account_saved_league_select",
            )
            if st.button("Resume saved league", key="account_resume_saved_league", use_container_width=True):
                actions["resume_league"] = option_labels.get(selected_label)
        else:
            st.caption("No saved leagues yet.")

        with st.expander("Profile preferences", expanded=False):
            settings_row = st.session_state.get("account_user_settings")
            onboarding_hidden = user_preferences.onboarding_is_dismissed(settings_row)
            st.caption(
                "League Orientation is hidden on every device."
                if onboarding_hidden
                else "Reset League Orientation to show it again on the Dashboard."
            )
            if st.button(
                "Reset onboarding",
                key="account_reset_onboarding",
                use_container_width=True,
                help="Show League Orientation again on the Dashboard.",
            ):
                error = user_preferences.persist_authenticated_onboarding(
                    config=config,
                    session_state=st.session_state,
                    dismissed=False,
                )
                if error:
                    st.warning("Onboarding could not be reset right now. Please try again.")
                else:
                    st.success("League Orientation will appear again.")
        return actions

    st.caption("Use the main launch screen to create an account or sign in. Guest mode remains available.")
    return actions


def render_mobile_auth_entry(
    *,
    config: dict,
    username: str = "",
    selected_league_id: str = "",
    selected_league_name: str = "",
    my_roster_id=None,
) -> dict:
    actions = {
        "resume_league": None,
        "continue_guest": False,
        "logged_in": bool(auth_supabase.current_user_id(st.session_state)),
    }
    st.markdown(
        "<div class='launch-section-intro launch-account-intro'>"
        "<div class='launch-section-eyebrow'>Optional account</div>"
        "<div class='launch-section-title'>Save leagues across devices</div>"
        "<div class='launch-section-copy'>"
        "Create a free account when you want leagues saved for next time. "
        "You can import a Sleeper league as a guest without signing up."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    if not auth_supabase.is_configured(config):
        st.info("Accounts are not configured yet. Continue as a guest and import your Sleeper league below.")
        actions["continue_guest"] = True
        return actions

    if auth_supabase.current_user_id(st.session_state):
        email = _auth_email(st.session_state)
        st.success(f"Signed in as {email or 'account user'}.")
        saved_rows = st.session_state.get("account_saved_leagues_cache")
        if not isinstance(saved_rows, list):
            saved_rows, error = account_store.fetch_saved_leagues(
                config,
                auth_supabase.current_access_token(st.session_state),
                user_id=auth_supabase.current_user_id(st.session_state),
            )
            if error:
                st.warning(account_store.customer_safe_error(error, context="saved_leagues"))
                saved_rows = []
            st.session_state["account_saved_leagues_cache"] = saved_rows
        default_league = account_store.default_saved_league(saved_rows, require_default=True)
        if default_league:
            st.caption(f"Default saved league: {saved_league_label(default_league)}")
            auto_resume_key = f"_supabase_launch_auto_resume_attempted_{auth_supabase.current_user_id(st.session_state)}"
            if (
                not _safe_text(selected_league_id)
                and not st.session_state.get("supabase_auto_resume_suppressed")
                and not st.session_state.get(auto_resume_key)
            ):
                st.session_state[auto_resume_key] = True
                actions["resume_league"] = default_league
                return actions
            if st.button("Resume saved league", key="launch_resume_saved_league", use_container_width=True, type="primary"):
                actions["resume_league"] = default_league
        elif saved_rows:
            st.caption("Choose a saved league or add another Sleeper league.")
            option_labels = {
                saved_league_label(row): row
                for row in saved_rows
                if _safe_text(row.get("league_id"))
            }
            if option_labels:
                selected_label = st.selectbox(
                    "Saved league",
                    list(option_labels.keys()),
                    key="launch_saved_league_select",
                )
                if st.button("Open saved league", key="launch_open_saved_league", use_container_width=True, type="primary"):
                    actions["resume_league"] = option_labels.get(selected_label)
        else:
            st.info("Add your Sleeper leagues to save a default league to this account.")
        if st.button("Continue with Sleeper username", key="launch_continue_guest_signed_in", use_container_width=True):
            actions["continue_guest"] = True
        return actions

    if st.session_state.get("account_signup_check_email") or st.session_state.get(auth_supabase.CONFIRMATION_REQUIRED_KEY):
        render_confirmation_required_card(
            config=config,
            email=_confirmation_email(st.session_state),
            key_prefix="launch",
        )
        if st.button("Use a different email", key="launch_use_different_email", use_container_width=True):
            st.session_state["account_signup_check_email"] = False
            auth_supabase.clear_confirmation_required(st.session_state)
            st.session_state["launch_auth_mode"] = "account"
            st.rerun()
        if st.button("Continue as guest", key="launch_continue_guest_after_signup", use_container_width=True):
            st.session_state["account_signup_check_email"] = False
            auth_supabase.clear_confirmation_required(st.session_state)
            st.session_state["launch_auth_mode"] = "guest"
            actions["continue_guest"] = True
            return actions
        return actions

    launch_mode = _safe_text(st.session_state.get("launch_auth_mode")).strip().lower()
    if launch_mode not in {"account", "guest"}:
        choice_cols = st.columns(2)
        with choice_cols[0]:
            if st.button(
                "Create account / Sign in",
                key="launch_choose_account",
                use_container_width=True,
            ):
                st.session_state["launch_auth_mode"] = "account"
                st.rerun()
        with choice_cols[1]:
            if st.button(
                "Continue as guest",
                key="launch_choose_guest",
                use_container_width=True,
                type="primary",
            ):
                st.session_state["launch_auth_mode"] = "guest"
                actions["continue_guest"] = True
        st.caption("Guest browsing is fully usable. A free account remembers your leagues for next time.")
        return actions

    if launch_mode == "guest":
        actions["continue_guest"] = True
        st.caption("Browsing as guest. Import a league below — create a free account anytime to save it.")
        if st.button("Sign in instead", key="launch_guest_to_account", use_container_width=True):
            st.session_state["launch_auth_mode"] = "account"
            st.rerun()
        return actions

    if st.button("Continue as guest instead", key="launch_account_to_guest", use_container_width=True):
        st.session_state["launch_auth_mode"] = "guest"
        actions["continue_guest"] = True
        return actions

    st.markdown("#### Create account / Sign in")
    tabs = st.tabs(["Log in", "Create account"])
    with tabs[0]:
        login_email = st.text_input("Email", key="launch_account_login_email")
        login_password = st.text_input("Password", type="password", key="launch_account_login_password")
        if st.button("Log in", key="launch_account_login_button", use_container_width=True, type="primary"):
            payload, error = auth_supabase.sign_in(config, login_email, login_password)
            if error:
                if auth_supabase.auth_error_requires_email_confirmation(error):
                    auth_supabase.mark_confirmation_required(st.session_state, login_email)
                    render_confirmation_required_card(
                        config=config,
                        email=login_email,
                        key_prefix="login",
                    )
                else:
                    st.warning(auth_supabase.signin_user_message(error))
            else:
                from modules import guest_conversion

                guest_conversion.capture_guest_resume(
                    prompt_surface="launch", intended_action="signin"
                )
                auth_supabase.apply_auth_payload(st.session_state, payload or {})
                auth_supabase.queue_durable_auth_save(st.session_state, payload or {})
                guest_conversion.finish_auth_from_guest(
                    config=config, mode="signin", surface="launch"
                )
                try:
                    from modules import launch_analytics

                    launch_analytics.track_event(
                        "login_completed",
                        props=launch_analytics.build_context_props(
                            st.session_state, source_surface="account_login"
                        ),
                        once_key="session",
                        state=st.session_state,
                    )
                except Exception:
                    pass
                st.success("Logged in.")
                st.rerun()
    with tabs[1]:
        signup_email = st.text_input("Email", key="launch_account_signup_email")
        signup_password = st.text_input("Password", type="password", key="launch_account_signup_password")
        st.caption("We'll email a confirmation link. Your account stays inactive until you confirm.")
        if st.button(
            "Create account",
            key="launch_account_signup_button",
            use_container_width=True,
            type="primary",
            disabled=bool(st.session_state.get("_auth_signup_in_flight")),
        ):
            try:
                from modules import launch_analytics

                launch_analytics.track_event(
                    "signup_started",
                    props=launch_analytics.build_context_props(
                        st.session_state, source_surface="account_signup"
                    ),
                    once_key="session",
                    state=st.session_state,
                )
            except Exception:
                pass
            st.session_state["_auth_signup_in_flight"] = True
            with st.spinner("Creating your account…"):
                payload, error = auth_supabase.sign_up(config, signup_email, signup_password)
            st.session_state.pop("_auth_signup_in_flight", None)
            if error:
                if auth_supabase.auth_error_requires_email_confirmation(error):
                    auth_supabase.mark_confirmation_required(st.session_state, signup_email)
                    render_confirmation_required_card(
                        config=config,
                        email=signup_email,
                        key_prefix="signup",
                    )
                else:
                    st.warning(auth_supabase.signup_user_message(error))
            elif auth_supabase.signup_requires_email_confirmation(payload):
                auth_supabase.mark_confirmation_required(st.session_state, signup_email)
                st.session_state["account_signup_check_email"] = True
                try:
                    from modules import launch_analytics

                    launch_analytics.track_event(
                        "signup_completed",
                        props=launch_analytics.build_context_props(
                            st.session_state,
                            source_surface="account_signup",
                            extra={"confirmation_required": True},
                        ),
                        once_key="session",
                        state=st.session_state,
                    )
                except Exception:
                    pass
                st.rerun()
            else:
                from modules import guest_conversion

                guest_conversion.capture_guest_resume(
                    prompt_surface="launch",
                    intended_action="signup",
                )
                auth_supabase.apply_auth_payload(st.session_state, payload or {})
                auth_supabase.queue_durable_auth_save(st.session_state, payload or {})
                guest_conversion.finish_auth_from_guest(
                    config=config, mode="signup", surface="launch"
                )
                # finish_auth_from_guest already save_current_context when resume has league.
                # Preserve prior launch args path when resume empty but form args present.
                session = auth_supabase.current_auth_session(st.session_state)
                if (
                    session.get("access_token")
                    and session.get("user_id")
                    and username
                    and selected_league_id
                    and not st.session_state.get("selected_league_id")
                ):
                    save_current_context(
                        config=config,
                        access_token=session.get("access_token"),
                        user_id=session.get("user_id"),
                        email=session.get("email"),
                        username=username,
                        selected_league_id=selected_league_id,
                        selected_league_name=selected_league_name,
                        my_roster_id=my_roster_id,
                    )
                try:
                    from modules import launch_analytics

                    launch_analytics.track_event(
                        "signup_completed",
                        props=launch_analytics.build_context_props(
                            st.session_state,
                            source_surface="account_signup",
                            extra={"confirmation_required": False},
                        ),
                        once_key="session",
                        state=st.session_state,
                    )
                except Exception:
                    pass
                st.success("Account created.")
                st.rerun()
    st.caption("Free accounts remember your Sleeper username and leagues. Guest browsing stays available.")
    return actions


def save_current_context(
    *,
    config: dict,
    access_token: str,
    user_id: str,
    email: str = "",
    username: str = "",
    selected_league_id: str = "",
    selected_league_name: str = "",
    my_roster_id=None,
) -> tuple[bool, str]:
    if not user_id:
        return False, "No logged-in account found."
    profile_payload = account_store.build_profile_payload(
        user_id=user_id,
        email=email,
        sleeper_username=username,
    )
    profile_saved, profile_error = account_store.upsert_profile(
        config,
        access_token,
        profile_payload,
    )
    if not profile_saved:
        return False, profile_error
    if not username or not selected_league_id:
        return True, ""
    league_payload = account_store.build_saved_league_payload(
        user_id=user_id,
        sleeper_username=username,
        league_id=selected_league_id,
        league_name=selected_league_name,
        roster_id=my_roster_id,
        team_id=my_roster_id,
        is_default=True,
    )
    return account_store.upsert_saved_league(
        config,
        access_token,
        league_payload,
    )


def saved_league_label(row: dict) -> str:
    league_name = _safe_text(row.get("league_name"), "Saved league")
    sleeper_username = _safe_text(row.get("sleeper_username"))
    league_id = _safe_text(row.get("league_id"))
    suffix = f" | {sleeper_username}" if sleeper_username else ""
    id_suffix = f" | {league_id[-6:]}" if league_id else ""
    return f"{league_name}{suffix}{id_suffix}"

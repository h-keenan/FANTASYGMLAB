"use client";

/**
 * Activation-safe share-card flow shared by the Trade Hub idea card, the
 * Analyzer and the Player profile.
 *
 * iOS Safari only lets navigator.share run inside the tap's user-activation
 * window. Building the PNG (server route, or Satori + canvas in the browser)
 * takes seconds, so awaiting it after the tap makes share() reject with
 * NotAllowedError and the old flow silently degraded to text. Here the PNG is
 * built ahead of time (card visible / result on screen, idle), cached by
 * key, and the tap calls navigator.share({files}) synchronously with the
 * ready File. If the tap beats the build, we show "Preparing image..." and
 * then a second-step "Share image" button (a fresh tap = fresh activation).
 * Failures are shown inline and recorded as feature_use share/image_failed.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { trackUse } from "@/lib/analytics";
import { canShareFiles, shareErrorName, shareImageOrText, type ShareOutcome } from "@/lib/shareImage";

const MAX_CACHED = 16;
const MAX_CONCURRENT = 2;

const ready = new Map<string, Blob>();
const inflight = new Map<string, Promise<Blob>>();
const queue: Array<() => void> = [];
let active = 0;

/** Test helper. */
export function resetShareBlobCache(): void {
  ready.clear();
  inflight.clear();
  queue.length = 0;
  active = 0;
}

/** The prepared PNG for this key, if its build already finished. Sync on purpose. */
export function getReadyShareBlob(key: string): Blob | undefined {
  return ready.get(key);
}

/** Build (once, 2 at a time) and cache a share PNG. Failures are not cached. */
export function prepareShareBlob(key: string, build: () => Promise<Blob>): Promise<Blob> {
  const hit = ready.get(key);
  if (hit) return Promise.resolve(hit);
  const existing = inflight.get(key);
  if (existing) return existing;
  const promise = new Promise<Blob>((resolve, reject) => {
    const run = () => {
      active += 1;
      let started: Promise<Blob>;
      try {
        started = build();
      } catch (error) {
        started = Promise.reject(error);
      }
      started.then(resolve, reject).finally(() => {
        active -= 1;
        queue.shift()?.();
      });
    };
    if (active < MAX_CONCURRENT) run();
    else queue.push(run);
  })
    .then((blob) => {
      if (!blob || !blob.size) throw new Error("Empty share image");
      ready.set(key, blob);
      while (ready.size > MAX_CACHED) {
        const oldest = ready.keys().next().value;
        if (oldest === undefined) break;
        ready.delete(oldest);
      }
      return blob;
    })
    .finally(() => {
      inflight.delete(key);
    });
  inflight.set(key, promise);
  return promise;
}

type IdleWindow = {
  requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number;
  cancelIdleCallback?: (id: number) => void;
};

function whenIdle(fn: () => void): () => void {
  const w = typeof window !== "undefined" ? (window as unknown as IdleWindow) : undefined;
  if (w?.requestIdleCallback) {
    const id = w.requestIdleCallback(fn, { timeout: 2000 });
    return () => w.cancelIdleCallback?.(id);
  }
  const id = setTimeout(fn, 150);
  return () => clearTimeout(id);
}

export type ShareStage = "idle" | "preparing" | "confirm" | "sharing";

export interface UseShareImageOptions {
  /** Identifies the inputs of the image; null/omitted `build` = text-only. */
  cacheKey: string | null;
  build?: () => Promise<Blob>;
  filename: string;
  text: string;
  title: string;
  /** item_kind prop on the analytics event. */
  itemKind: string;
  leagueId?: string;
  /** Wait until the observed element scrolls into view before building. */
  lazy?: boolean;
  onOutcome?: (outcome: ShareOutcome) => void;
}

export function useShareImage(options: UseShareImageOptions) {
  const { cacheKey, lazy } = options;
  const hasBuild = Boolean(options.build);
  const [stage, setStage] = useState<ShareStage>("idle");
  const [status, setStatus] = useState<string | null>(null);
  const [visible, setVisible] = useState(!lazy);
  const [element, setElement] = useState<Element | null>(null);
  const latest = useRef(options);
  latest.current = options;
  const statusTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (statusTimer.current) clearTimeout(statusTimer.current);
    },
    [],
  );

  // Lazy: flip `visible` once the element is on screen.
  useEffect(() => {
    if (!lazy || visible) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    if (!element) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [lazy, visible, element]);

  // Pre-render once visible, when idle.
  useEffect(() => {
    if (!visible || !cacheKey || !hasBuild) return;
    return whenIdle(() => {
      const current = latest.current.build;
      if (current) void prepareShareBlob(cacheKey, current).catch(() => {});
    });
  }, [visible, cacheKey, hasBuild]);

  const showStatus = useCallback((message: string) => {
    setStatus(message);
    if (statusTimer.current) clearTimeout(statusTimer.current);
    statusTimer.current = setTimeout(() => setStatus(null), 8000);
  }, []);

  const reportFailure = useCallback(
    (error: unknown, stageName: "build" | "share") => {
      const name = shareErrorName(error);
      const message = error instanceof Error && error.message ? error.message.slice(0, 80) : name;
      trackUse("share", "image_failed", {
        leagueId: latest.current.leagueId,
        props: { result: name, item_kind: latest.current.itemKind, reason: stageName },
      });
      showStatus(
        stageName === "build"
          ? `Couldn't build the image on this device: ${message}. Sharing text instead.`
          : `Couldn't attach the image in the share sheet: ${message}.`,
      );
    },
    [showStatus],
  );

  const run = useCallback(
    async (preparedBlob: Blob | undefined) => {
      const o = latest.current;
      // Nothing is awaited before shareImageOrText reaches navigator.share
      // when preparedBlob is set, so the tap's activation is still live.
      setStage("sharing");
      let outcome: ShareOutcome = "failed";
      try {
        outcome = await shareImageOrText({
          preparedBlob,
          filename: o.filename,
          text: o.text,
          title: o.title,
          onImageFailed: reportFailure,
        });
      } finally {
        setStage("idle");
      }
      o.onOutcome?.(outcome);
      return outcome;
    },
    [reportFailure],
  );

  const onClick = useCallback(() => {
    const o = latest.current;
    setStatus(null);
    if (!o.build || !o.cacheKey) {
      void run(undefined);
      return;
    }
    const prepared = getReadyShareBlob(o.cacheKey);
    if (prepared) {
      void run(prepared);
      return;
    }
    // The build has not finished: do NOT await it and then call share (the
    // activation would be gone). Wait, then ask for a second tap.
    setStage("preparing");
    prepareShareBlob(o.cacheKey, o.build).then(
      (blob) => {
        if (canShareFiles(blob)) setStage("confirm");
        else void run(blob);
      },
      (error) => {
        reportFailure(error, "build");
        void run(undefined);
      },
    );
  }, [run, reportFailure]);

  const label = (idle: string) => (stage === "preparing" ? "Preparing image…" : stage === "confirm" ? "Share image" : idle);
  return { stage, status, onClick, label, observe: setElement, busy: stage === "preparing" || stage === "sharing" };
}

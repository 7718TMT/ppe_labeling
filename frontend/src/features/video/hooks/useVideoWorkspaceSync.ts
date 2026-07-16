/**
 * Event-driven synchronization for the video labeling workspace.
 *
 * The hook intentionally owns only transport concerns. Screens remain in
 * control of normalized state by applying snapshots and event payloads through
 * the supplied callbacks. This keeps it safe to adopt incrementally alongside
 * existing REST mutations.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  getVideoWorkspaceChanges,
  getVideoWorkspaceSnapshot,
  videoWorkspaceEventsUrl,
} from '../../../api/client';
import type {
  VideoWorkspaceChanges,
  VideoWorkspaceEvent,
  VideoWorkspaceSnapshot,
} from '../../../types';

/** States exposed to the workspace for unobtrusive connection feedback. */
export type VideoWorkspaceSyncStatus =
  | 'idle'
  | 'loading'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'offline';

/** Minimal EventSource shape so tests do not need to replace global browser APIs. */
export interface VideoWorkspaceEventSource {
  onopen: ((event: Event) => void) | null;
  onerror: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent<string>) => void) | null;
  addEventListener(type: string, listener: (event: Event) => void): void;
  close(): void;
}

/** Creates the project-scoped EventSource connection. */
export type VideoWorkspaceEventSourceFactory = (url: string) => VideoWorkspaceEventSource;

/** Minimal document contract used for visibility-aware streaming. */
export interface VisibilityTarget {
  visibilityState: DocumentVisibilityState;
  addEventListener(type: 'visibilitychange', listener: () => void): void;
  removeEventListener(type: 'visibilitychange', listener: () => void): void;
}

export interface UseVideoWorkspaceSyncOptions {
  /** The current video project. An empty ID disables all network activity. */
  projectId: string;
  /** Allows callers to pause synchronization while the workspace is hidden. */
  enabled?: boolean;
  /** Applies the one-time initial state, or a full resynchronization state. */
  onSnapshot: (snapshot: VideoWorkspaceSnapshot) => void;
  /** Applies one small, durable workspace update. */
  onEvent: (event: VideoWorkspaceEvent) => void;
  /**
   * Optional ordered batch callback for a delta response. Use this to coalesce
   * one active-video reload after a suggestion materializes many annotations.
   * SSE messages still use onEvent because each arrives independently.
   */
  onEvents?: (events: VideoWorkspaceEvent[]) => void;
  /** Reports recoverable transport and parsing problems without throwing. */
  onError?: (error: Error) => void;
  /** Test seam and compatibility seam for environments without EventSource. */
  eventSourceFactory?: VideoWorkspaceEventSourceFactory;
  /** Test seam for browser visibility changes. Defaults to document. */
  visibilityTarget?: VisibilityTarget;
  /** Initial cursor when a parent already has a matching snapshot. */
  initialEventId?: number | null;
  /** Optional deterministic backoff used by tests or host applications. */
  reconnectDelayMs?: (attempt: number) => number;
}

export interface VideoWorkspaceSyncController {
  status: VideoWorkspaceSyncStatus;
  lastEventId: number | null;
  /** Explicitly reload a compact snapshot and replace the current stream. */
  refresh: () => Promise<void>;
}

interface EventFallback {
  eventType?: string;
  lastEventId?: string;
  projectId: string;
}

const NAMED_EVENT_TYPES = [
  'job.changed',
  'video.changed',
  'annotation.changed',
  'tracks.changed',
  'export.changed',
  'resync.required',
];
const MAX_RECONNECT_DELAY_MS = 30_000;
const INITIAL_RECONNECT_DELAY_MS = 1_000;

const defaultEventSourceFactory: VideoWorkspaceEventSourceFactory = (url) => {
  if (typeof EventSource === 'undefined') {
    throw new Error('Live workspace updates are unavailable in this browser.');
  }
  return new EventSource(url) as unknown as VideoWorkspaceEventSource;
};

/** Turn arbitrary transport failures into a stable callback value. */
function asError(reason: unknown): Error {
  return reason instanceof Error ? reason : new Error(String(reason));
}

function parseEventId(value: unknown): number | null {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null;
}

function isEventRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

/**
 * Parse both the durable envelope returned by the delta endpoint and an SSE
 * message carrying that envelope. Returns null for malformed messages so a
 * bad transient event cannot take the workspace down.
 */
export function parseVideoWorkspaceEvent(
  data: string,
  fallback: EventFallback,
): VideoWorkspaceEvent | null {
  let raw: unknown;
  try {
    raw = JSON.parse(data);
  } catch {
    return null;
  }
  if (!isEventRecord(raw)) return null;

  const eventId = parseEventId(raw.event_id ?? fallback.lastEventId);
  const eventType = raw.event_type ?? fallback.eventType;
  const projectId = raw.project_id ?? fallback.projectId;
  if (eventId === null || typeof eventType !== 'string' || typeof projectId !== 'string') {
    return null;
  }

  return {
    event_id: eventId,
    event_type: eventType,
    project_id: projectId,
    video_id: typeof raw.video_id === 'string' || raw.video_id === null ? raw.video_id : undefined,
    payload: raw.payload,
    created_at: typeof raw.created_at === 'string' ? raw.created_at : undefined,
  };
}

/** Return a bounded, jittered reconnect delay to avoid synchronized retries. */
export function workspaceSyncReconnectDelay(attempt: number): number {
  const cappedAttempt = Math.max(0, Math.min(attempt, 5));
  const exponential = Math.min(
    MAX_RECONNECT_DELAY_MS,
    INITIAL_RECONNECT_DELAY_MS * 2 ** cappedAttempt,
  );
  return Math.round(exponential * (0.8 + Math.random() * 0.4));
}

/**
 * Keep one SSE connection open while the workspace is visible.
 *
 * On a connection loss or a restored browser tab, the hook first asks for a
 * cursor-based delta. Full snapshots are fetched only on startup, explicit
 * refresh, or when the server says the event cursor is no longer retained.
 */
export function useVideoWorkspaceSync({
  projectId,
  enabled = true,
  onSnapshot,
  onEvent,
  onEvents,
  onError,
  eventSourceFactory = defaultEventSourceFactory,
  visibilityTarget,
  initialEventId = null,
  reconnectDelayMs = workspaceSyncReconnectDelay,
}: UseVideoWorkspaceSyncOptions): VideoWorkspaceSyncController {
  const callbacksRef = useRef({ onSnapshot, onEvent, onEvents, onError, reconnectDelayMs });
  callbacksRef.current = { onSnapshot, onEvent, onEvents, onError, reconnectDelayMs };
  const refreshRef = useRef<() => Promise<void>>(async () => undefined);
  const lastEventIdRef = useRef<number | null>(initialEventId);
  const [status, setStatus] = useState<VideoWorkspaceSyncStatus>('idle');
  const [lastEventId, setLastEventId] = useState<number | null>(initialEventId);

  const refresh = useCallback(() => refreshRef.current(), []);

  useEffect(() => {
    const target = visibilityTarget ?? (
      typeof document === 'undefined' ? undefined : document as VisibilityTarget
    );
    let disposed = false;
    let request: AbortController | undefined;
    let reconnectTimer: number | undefined;
    let source: VideoWorkspaceEventSource | undefined;
    let reconnectAttempt = 0;

    const isVisible = () => !target || target.visibilityState !== 'hidden';
    const isCurrent = () => !disposed && enabled && Boolean(projectId);
    const setSyncStatus = (next: VideoWorkspaceSyncStatus) => {
      if (!disposed) setStatus(next);
    };
    const reportError = (reason: unknown) => {
      if (!disposed) callbacksRef.current.onError?.(asError(reason));
    };
    const clearReconnectTimer = () => {
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      reconnectTimer = undefined;
    };
    const closeSource = () => {
      if (!source) return;
      source.onopen = null;
      source.onerror = null;
      source.onmessage = null;
      source.close();
      source = undefined;
    };
    const updateCursor = (next: number) => {
      if (next <= (lastEventIdRef.current ?? -1)) return;
      lastEventIdRef.current = next;
      if (!disposed) setLastEventId(next);
    };
    const resetCursor = (next: number) => {
      lastEventIdRef.current = next;
      if (!disposed) setLastEventId(next);
    };

    const applyEvent = (event: VideoWorkspaceEvent): boolean => {
      if (event.project_id !== projectId) return false;
      if (event.event_type === 'resync.required') return true;
      if (event.event_id <= (lastEventIdRef.current ?? -1)) return false;
      updateCursor(event.event_id);
      try {
        callbacksRef.current.onEvent(event);
      } catch (reason) {
        reportError(reason);
      }
      return false;
    };

    const applyEventBatch = (events: VideoWorkspaceEvent[]): boolean => {
      const pending: VideoWorkspaceEvent[] = [];
      for (const event of events) {
        if (event.project_id !== projectId) continue;
        if (event.event_type === 'resync.required') return true;
        if (event.event_id <= (lastEventIdRef.current ?? -1)) continue;
        updateCursor(event.event_id);
        pending.push(event);
      }
      if (pending.length === 0) return false;
      try {
        if (callbacksRef.current.onEvents) {
          callbacksRef.current.onEvents(pending);
        } else {
          pending.forEach((event) => callbacksRef.current.onEvent(event));
        }
      } catch (reason) {
        reportError(reason);
      }
      return false;
    };

    const loadSnapshot = async (): Promise<boolean> => {
      if (!isCurrent() || !isVisible()) return false;
      clearReconnectTimer();
      request?.abort();
      const controller = new AbortController();
      request = controller;
      setSyncStatus('loading');
      try {
        const snapshot = await getVideoWorkspaceSnapshot(projectId, controller.signal);
        if (!isCurrent() || controller.signal.aborted) return false;
        resetCursor(snapshot.last_event_id);
        callbacksRef.current.onSnapshot(snapshot);
        reconnectAttempt = 0;
        return true;
      } catch (reason) {
        if (!controller.signal.aborted && isCurrent()) {
          reportError(reason);
          setSyncStatus('offline');
        }
        return false;
      }
    };

    const catchUp = async (): Promise<boolean> => {
      const cursor = lastEventIdRef.current;
      if (cursor === null) return loadSnapshot();
      if (!isCurrent() || !isVisible()) return false;
      request?.abort();
      const controller = new AbortController();
      request = controller;
      try {
        const changes: VideoWorkspaceChanges = await getVideoWorkspaceChanges(
          projectId,
          cursor,
          controller.signal,
        );
        if (!isCurrent() || controller.signal.aborted) return false;
        if (changes.resync_required) return loadSnapshot();

        const orderedEvents = [...changes.events].sort((left, right) => left.event_id - right.event_id);
        if (applyEventBatch(orderedEvents)) return loadSnapshot();
        updateCursor(changes.last_event_id);
        return true;
      } catch (reason) {
        if (!controller.signal.aborted && isCurrent()) {
          reportError(reason);
          setSyncStatus('offline');
        }
        return false;
      }
    };

    const scheduleReconnect = (): void => {
      if (!isCurrent() || !isVisible() || reconnectTimer !== undefined) return;
      closeSource();
      setSyncStatus('reconnecting');
      const delay = Math.max(0, callbacksRef.current.reconnectDelayMs(reconnectAttempt));
      reconnectAttempt += 1;
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = undefined;
        void (async () => {
          const recovered = await catchUp();
          if (!isCurrent() || !isVisible()) return;
          if (recovered) openStream();
          else scheduleReconnect();
        })();
      }, delay);
    };

    const openStream = (): void => {
      if (!isCurrent() || !isVisible() || source) return;
      clearReconnectTimer();
      setSyncStatus('connecting');
      try {
        const nextSource = eventSourceFactory(
          videoWorkspaceEventsUrl(projectId, lastEventIdRef.current ?? undefined),
        );
        source = nextSource;
        const receive = (nativeEvent: Event, namedType?: string) => {
          if (!isCurrent() || source !== nextSource) return;
          const message = nativeEvent as MessageEvent<string>;
          const parsed = parseVideoWorkspaceEvent(String(message.data ?? ''), {
            eventType: namedType ?? (nativeEvent.type === 'message' ? undefined : nativeEvent.type),
            lastEventId: message.lastEventId,
            projectId,
          });
          if (!parsed) {
            reportError(new Error('Received an invalid live workspace update.'));
            return;
          }
          if (applyEvent(parsed)) {
            closeSource();
            void (async () => {
              const recovered = await loadSnapshot();
              if (recovered) openStream();
              else scheduleReconnect();
            })();
          }
        };
        nextSource.onopen = () => {
          if (!isCurrent() || source !== nextSource) return;
          reconnectAttempt = 0;
          setSyncStatus('connected');
        };
        nextSource.onerror = () => {
          if (!isCurrent() || source !== nextSource) return;
          scheduleReconnect();
        };
        nextSource.onmessage = (event) => receive(event);
        NAMED_EVENT_TYPES.forEach((eventType) => {
          nextSource.addEventListener(eventType, (event) => receive(event, eventType));
        });
      } catch (reason) {
        reportError(reason);
        scheduleReconnect();
      }
    };

    const start = async (forceSnapshot: boolean): Promise<void> => {
      if (!isCurrent() || !isVisible()) return;
      closeSource();
      clearReconnectTimer();
      const ready = forceSnapshot ? await loadSnapshot() : await catchUp();
      if (ready && isCurrent() && isVisible()) openStream();
      else if (isCurrent() && isVisible()) scheduleReconnect();
    };

    const handleVisibilityChange = () => {
      if (isVisible()) {
        void start(lastEventIdRef.current === null);
      } else {
        clearReconnectTimer();
        request?.abort();
        closeSource();
        setSyncStatus('idle');
      }
    };

    refreshRef.current = () => start(true);
    lastEventIdRef.current = initialEventId;
    setLastEventId(initialEventId);
    if (!enabled || !projectId) {
      setSyncStatus('idle');
      return () => {
        refreshRef.current = async () => undefined;
      };
    }

    target?.addEventListener('visibilitychange', handleVisibilityChange);
    void start(true);
    return () => {
      disposed = true;
      clearReconnectTimer();
      request?.abort();
      closeSource();
      target?.removeEventListener('visibilitychange', handleVisibilityChange);
      refreshRef.current = async () => undefined;
    };
  }, [enabled, eventSourceFactory, initialEventId, projectId, visibilityTarget]);

  return { status, lastEventId, refresh };
}

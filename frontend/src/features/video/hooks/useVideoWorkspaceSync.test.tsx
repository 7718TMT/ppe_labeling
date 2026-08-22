import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../../../api/client';
import type {
  VideoWorkspaceChanges,
  VideoWorkspaceEvent,
  VideoWorkspaceSnapshot,
} from '../../../types';
import {
  parseVideoWorkspaceEvent,
  type VideoWorkspaceEventSource,
  type VisibilityTarget,
  useVideoWorkspaceSync,
} from './useVideoWorkspaceSync';

vi.mock('../../../api/client', () => ({
  getVideoWorkspaceChanges: vi.fn(),
  getVideoWorkspaceSnapshot: vi.fn(),
  videoWorkspaceEventsUrl: vi.fn((projectId: string, after?: number) => (
    `/api/v1/video-projects/${projectId}/events${after === undefined ? '' : `?after=${after}`}`
  )),
}));

const snapshot: VideoWorkspaceSnapshot = {
  project: {
    project_id: 'project-1',
    name: 'Factory',
    config: {},
    created_at: '2026-07-16T00:00:00Z',
    updated_at: '2026-07-16T00:00:00Z',
  },
  videos: [],
  jobs: [],
  processing_options: {
    threshold_available: true,
    model_available: false,
  },
  last_event_id: 4,
};

function event(eventId: number, eventType = 'video.changed'): VideoWorkspaceEvent {
  return {
    event_id: eventId,
    project_id: 'project-1',
    video_id: 'video-1',
    event_type: eventType,
    payload: { processing_status: 'ready' },
    created_at: '2026-07-16T00:00:00Z',
  };
}

class FakeEventSource implements VideoWorkspaceEventSource {
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  readonly close = vi.fn();
  private readonly listeners = new Map<string, Array<(nativeEvent: Event) => void>>();

  addEventListener(type: string, listener: (nativeEvent: Event) => void): void {
    const existing = this.listeners.get(type) ?? [];
    existing.push(listener);
    this.listeners.set(type, existing);
  }

  emitOpen(): void {
    this.onopen?.(new Event('open'));
  }

  emitError(): void {
    this.onerror?.(new Event('error'));
  }

  emit(eventType: string, payload: unknown, lastEventId = ''): void {
    const nativeEvent = {
      type: eventType,
      data: JSON.stringify(payload),
      lastEventId,
    } as MessageEvent<string>;
    if (eventType === 'message') {
      this.onmessage?.(nativeEvent);
      return;
    }
    this.listeners.get(eventType)?.forEach((listener) => listener(nativeEvent));
  }
}

class FakeVisibilityTarget implements VisibilityTarget {
  visibilityState: DocumentVisibilityState = 'visible';
  private readonly listeners = new Set<() => void>();

  addEventListener(_type: 'visibilitychange', listener: () => void): void {
    this.listeners.add(listener);
  }

  removeEventListener(_type: 'visibilitychange', listener: () => void): void {
    this.listeners.delete(listener);
  }

  setVisibility(next: DocumentVisibilityState): void {
    this.visibilityState = next;
    this.listeners.forEach((listener) => listener());
  }
}

describe('parseVideoWorkspaceEvent', () => {
  it('accepts the durable event envelope sent through SSE', () => {
    const parsed = parseVideoWorkspaceEvent(JSON.stringify(event(8, 'job.changed')), {
      projectId: 'project-1',
    });

    expect(parsed).toMatchObject({ event_id: 8, event_type: 'job.changed', project_id: 'project-1' });
  });

  it('rejects malformed messages instead of applying an ambiguous update', () => {
    expect(parseVideoWorkspaceEvent('{not-json}', { projectId: 'project-1' })).toBeNull();
    expect(parseVideoWorkspaceEvent(JSON.stringify({ event_type: 'job.changed' }), {
      projectId: 'project-1',
    })).toBeNull();
  });
});

describe('useVideoWorkspaceSync', () => {
  let streams: FakeEventSource[];
  let visibility: FakeVisibilityTarget;

  beforeEach(() => {
    streams = [];
    visibility = new FakeVisibilityTarget();
    vi.mocked(api.getVideoWorkspaceSnapshot).mockResolvedValue(snapshot);
    vi.mocked(api.getVideoWorkspaceChanges).mockResolvedValue({
      events: [], last_event_id: snapshot.last_event_id, resync_required: false,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  function renderSync(overrides: Partial<Parameters<typeof useVideoWorkspaceSync>[0]> = {}) {
    const onSnapshot = vi.fn();
    const onEvent = vi.fn();
    const onError = vi.fn();
    const eventSourceFactory = vi.fn(() => {
      const stream = new FakeEventSource();
      streams.push(stream);
      return stream;
    });
    const result = renderHook(() => useVideoWorkspaceSync({
      projectId: 'project-1',
      onSnapshot,
      onEvent,
      onError,
      eventSourceFactory,
      visibilityTarget: visibility,
      reconnectDelayMs: () => 0,
      ...overrides,
    }));
    return { ...result, onSnapshot, onEvent, onError, eventSourceFactory };
  }

  it('loads one snapshot, receives named SSE events, then catches up before reconnecting', async () => {
    const { result, onSnapshot, onEvent, eventSourceFactory } = renderSync();

    await waitFor(() => expect(onSnapshot).toHaveBeenCalledWith(snapshot));
    expect(eventSourceFactory).toHaveBeenCalledWith('/api/v1/video-projects/project-1/events?after=4');
    act(() => streams[0].emitOpen());
    expect(result.current.status).toBe('connected');

    act(() => streams[0].emit('video.changed', event(5)));
    expect(onEvent).toHaveBeenCalledWith(event(5));
    expect(result.current.lastEventId).toBe(5);

    vi.mocked(api.getVideoWorkspaceChanges).mockResolvedValueOnce({
      events: [event(6, 'job.changed')], last_event_id: 6, resync_required: false,
    });
    act(() => streams[0].emitError());

    await waitFor(() => expect(api.getVideoWorkspaceChanges).toHaveBeenCalledWith(
      'project-1', 5, expect.any(AbortSignal),
    ));
    expect(onEvent).toHaveBeenCalledWith(event(6, 'job.changed'));
    expect(eventSourceFactory).toHaveBeenLastCalledWith('/api/v1/video-projects/project-1/events?after=6');
  });

  it('closes the stream while hidden and requests only a delta when visible again', async () => {
    const { onEvent, eventSourceFactory } = renderSync();
    await waitFor(() => expect(eventSourceFactory).toHaveBeenCalledTimes(1));

    act(() => visibility.setVisibility('hidden'));
    expect(streams[0].close).toHaveBeenCalledTimes(1);
    expect(api.getVideoWorkspaceChanges).not.toHaveBeenCalled();

    vi.mocked(api.getVideoWorkspaceChanges).mockResolvedValueOnce({
      events: [event(5)], last_event_id: 5, resync_required: false,
    });
    act(() => visibility.setVisibility('visible'));
    await waitFor(() => expect(api.getVideoWorkspaceChanges).toHaveBeenCalledWith(
      'project-1', 4, expect.any(AbortSignal),
    ));
    expect(onEvent).toHaveBeenCalledWith(event(5));
    expect(eventSourceFactory).toHaveBeenLastCalledWith('/api/v1/video-projects/project-1/events?after=5');
  });

  it('delivers a reconnect delta as one ordered batch when requested', async () => {
    const onEvents = vi.fn();
    const { onEvent, eventSourceFactory } = renderSync({ onEvents });
    await waitFor(() => expect(eventSourceFactory).toHaveBeenCalledTimes(1));
    vi.mocked(api.getVideoWorkspaceChanges).mockResolvedValueOnce({
      events: [event(6, 'annotation.changed'), event(5, 'annotation.changed')],
      last_event_id: 6,
      resync_required: false,
    });

    act(() => streams[0].emitError());

    await waitFor(() => expect(onEvents).toHaveBeenCalledWith([
      event(5, 'annotation.changed'), event(6, 'annotation.changed'),
    ]));
    expect(onEvent).not.toHaveBeenCalled();
  });

  it('uses a full snapshot when the server says the event cursor has expired', async () => {
    const { onSnapshot, eventSourceFactory } = renderSync();
    await waitFor(() => expect(eventSourceFactory).toHaveBeenCalledTimes(1));
    vi.mocked(api.getVideoWorkspaceChanges).mockResolvedValueOnce({
      events: [], last_event_id: 0, resync_required: true,
    } satisfies VideoWorkspaceChanges);

    act(() => streams[0].emitError());

    await waitFor(() => expect(onSnapshot).toHaveBeenCalledTimes(2));
    expect(eventSourceFactory).toHaveBeenLastCalledWith('/api/v1/video-projects/project-1/events?after=4');
  });
});

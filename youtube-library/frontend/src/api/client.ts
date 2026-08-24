import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || ''

export const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Types
export interface Channel {
  id: string
  name: string
  url: string
  youtube_id: string | null
  created_at: string
  last_checked: string | null
  video_count: number
}

export interface Video {
  id: string
  channel_id: string
  channel_name: string
  youtube_id: string
  title: string
  status: 'pending' | 'downloading' | 'transcribing' | 'refining' | 'summarizing' | 'embedding' | 'done' | 'error'
  error_message: string | null
  video_path: string | null
  audio_path: string | null
  transcript_path: string | null
  refined_transcript_path: string | null
  thumbnail_path: string | null
  summary: string | null
  created_at: string
  processed_at: string | null
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface VideoSearchResult {
  id: string
  channel_id: string
  channel_name: string
  youtube_id: string
  title: string
  thumbnail_path: string | null
  summary: string | null
  score: number
  matching_text: string
}

export interface ChatSource {
  video_id: string
  youtube_id: string
  title: string
  score: number
}

// API functions
export const channelsApi = {
  list: () => api.get<{ channels: Channel[]; total: number }>('/channels'),
  get: (id: string) => api.get<Channel>(`/channels/${id}`),
  create: (data: { url: string; name?: string; max_videos?: number }) =>
    api.post<Channel>('/channels', data),
  delete: (id: string) => api.delete(`/channels/${id}`),
  refresh: (id: string) => api.post(`/channels/${id}/refresh`),
}

const getApiBaseUrl = () => API_URL || window.location.origin

export interface ProcessingStatus {
  is_processing: boolean
  current_step: string | null
  current_video: {
    id: string
    title: string
    channel_name: string | null
    youtube_id: string
  } | null
}

export const videosApi = {
  list: (params?: { channel_id?: string; status?: string; page?: number; per_page?: number }) =>
    api.get<{ videos: Video[]; total: number; page: number; per_page: number }>('/videos', { params }),
  get: (id: string) => api.get<Video>(`/videos/${id}`),
  getTranscript: (id: string, refined = true) =>
    api.get<{ transcript: string; refined: boolean }>(`/videos/${id}/transcript`, { params: { refined } }),
  reprocess: (id: string) => api.post(`/videos/${id}/reprocess`),
  delete: (id: string) => api.delete(`/videos/${id}`),
  stats: () => api.get<{ total_videos: number; by_status: Record<string, number> }>('/videos/stats/summary'),
  processingStatus: () => api.get<ProcessingStatus>('/videos/process/status'),
  search: (q: string, channel_id?: string, limit = 20) =>
    api.get<{ results: VideoSearchResult[]; query: string; total: number }>('/videos/search', {
      params: { q, channel_id, limit },
    }),
  startProcessing: (channel_id?: string) =>
    api.post<{ message: string; pending: number }>('/videos/process/start', null, {
      params: channel_id ? { channel_id } : {},
    }),
  // URL builders for media endpoints
  getThumbnailUrl: (id: string) => `${getApiBaseUrl()}/api/videos/${id}/thumbnail`,
  getStreamUrl: (id: string) => `${getApiBaseUrl()}/api/videos/${id}/stream`,
}

export interface ChatStreamHandlers {
  onSources: (sources: ChatSource[]) => void
  onContent: (chunk: string) => void
}

export const chatApi = {
  send: (message: string, history: ChatMessage[] = [], channel_id?: string) =>
    api.post<{ response: string; sources: ChatSource[] }>('/chat', {
      message,
      history,
      channel_id,
    }),

  // Streams the answer via SSE so tokens appear as they are generated
  stream: async (
    message: string,
    history: ChatMessage[],
    channel_id: string | undefined,
    handlers: ChatStreamHandlers,
    signal?: AbortSignal
  ): Promise<void> => {
    const response = await fetch(`${getApiBaseUrl()}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history, channel_id }),
      signal,
    })

    if (!response.ok || !response.body) {
      throw new Error(`Chat request failed: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const events = buffer.split('\n\n')
      buffer = events.pop() ?? ''

      for (const event of events) {
        const dataLine = event.split('\n').find((line) => line.startsWith('data: '))
        if (!dataLine) continue
        try {
          const payload = JSON.parse(dataLine.slice(6))
          if (payload.type === 'sources') {
            handlers.onSources(payload.sources)
          } else if (payload.type === 'content') {
            handlers.onContent(payload.content)
          }
        } catch {
          // Ignore malformed SSE frames; the stream continues
        }
      }
    }
  },
}

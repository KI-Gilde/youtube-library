import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  RefreshCw,
  Trash2,
  Loader2,
  X,
  Play,
} from 'lucide-react'
import { channelsApi, videosApi, Video as VideoType } from '../api/client'
import VideoCard from '../components/VideoCard'
import VideoModal from '../components/VideoModal'
import { t } from '../i18n'

// Pipeline steps in processing order, with short technical codes
const PIPELINE_STEPS = [
  { key: 'downloading', code: 'DL', label: t.stepLabels.downloading },
  { key: 'transcribing', code: 'ASR', label: t.stepLabels.transcribing },
  { key: 'refining', code: 'REF', label: t.stepLabels.refining },
  { key: 'summarizing', code: 'SUM', label: t.stepLabels.summarizing },
  { key: 'embedding', code: 'EMB', label: t.stepLabels.embedding },
]

function Import() {
  const [showAddModal, setShowAddModal] = useState(false)
  const [newChannelUrl, setNewChannelUrl] = useState('')
  const [newChannelMaxVideos, setNewChannelMaxVideos] = useState('')
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null)
  const [selectedVideo, setSelectedVideo] = useState<VideoType | null>(null)
  const queryClient = useQueryClient()

  // Queries
  const { data: channelsData, isLoading: channelsLoading } = useQuery({
    queryKey: ['channels'],
    queryFn: () => channelsApi.list(),
  })

  // The pipeline lock status is the single source of truth for "something is
  // running" — it also catches runs started by the scheduler in the background.
  // Poll fast while active, slow while idle.
  const { data: processingStatusData } = useQuery({
    queryKey: ['processingStatus'],
    queryFn: () => videosApi.processingStatus(),
    refetchInterval: (query) => (query.state.data?.data.is_processing ? 2000 : 8000),
  })

  const isPipelineActive = processingStatusData?.data.is_processing ?? false

  const { data: statsData } = useQuery({
    queryKey: ['stats'],
    queryFn: () => videosApi.stats(),
    refetchInterval: isPipelineActive ? 3000 : false,
  })

  const { data: videosData, isLoading: videosLoading } = useQuery({
    queryKey: ['videos', selectedChannel],
    queryFn: () => videosApi.list({ channel_id: selectedChannel || undefined, per_page: 50 }),
    refetchInterval: isPipelineActive ? 3000 : false,
  })

  // Mutations
  const addChannelMutation = useMutation({
    mutationFn: (data: { url: string; max_videos?: number }) => channelsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] })
      setShowAddModal(false)
      setNewChannelUrl('')
      setNewChannelMaxVideos('')
    },
  })

  const deleteChannelMutation = useMutation({
    mutationFn: (id: string) => channelsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] })
      if (selectedChannel) setSelectedChannel(null)
    },
  })

  const refreshChannelMutation = useMutation({
    mutationFn: (id: string) => channelsApi.refresh(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['videos'] })
    },
  })

  const startProcessingMutation = useMutation({
    mutationFn: (channelId?: string) => videosApi.startProcessing(channelId || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['videos'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  // When a run finishes, refresh everything once so the final DONE states land
  const wasActiveRef = useRef(false)
  useEffect(() => {
    if (wasActiveRef.current && !isPipelineActive) {
      queryClient.invalidateQueries({ queryKey: ['videos'] })
      queryClient.invalidateQueries({ queryKey: ['videos-done'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    }
    wasActiveRef.current = isPipelineActive
  }, [isPipelineActive, queryClient])

  const channels = channelsData?.data.channels || []
  const videos = videosData?.data.videos || []
  const stats = statsData?.data
  const processingStatus = processingStatusData?.data

  // Calculate processing stats
  const processingCount = stats
    ? (stats.by_status.downloading || 0) +
      (stats.by_status.transcribing || 0) +
      (stats.by_status.refining || 0) +
      (stats.by_status.summarizing || 0) +
      (stats.by_status.embedding || 0)
    : 0

  const currentStepIndex = PIPELINE_STEPS.findIndex(
    (s) => s.key === processingStatus?.current_step
  )

  return (
    <div className="p-4 md:p-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl mb-1">{t.importTitle}</h1>
          <p className="mono text-xs text-[var(--text-muted)]">
            {t.importSubtitle}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {stats && (stats.by_status.pending || 0) > 0 && (
            <button
              onClick={() => startProcessingMutation.mutate(selectedChannel || undefined)}
              disabled={startProcessingMutation.isPending}
              className="btn-secondary"
            >
              {startProcessingMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {t.starting}
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  {t.startProcessing} ({stats.by_status.pending})
                </>
              )}
            </button>
          )}
          <button onClick={() => setShowAddModal(true)} className="btn-primary">
            <Plus className="w-4 h-4" />
            {t.addChannel}
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          <div className="stat-card">
            <div className="stat-label mb-2">{t.statTotal}</div>
            <div className="stat-value text-[var(--text-primary)]">{stats.total_videos}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label mb-2">{t.statDone}</div>
            <div className="stat-value text-[var(--ok)]">{stats.by_status.done || 0}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label mb-2">{t.statProcessing}</div>
            <div className="stat-value text-[var(--info)]">{processingCount}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label mb-2">{t.statQueued}</div>
            <div className="stat-value text-[var(--warn)]">{stats.by_status.pending || 0}</div>
          </div>
        </div>
      )}

      {/* Current Processing Status */}
      {processingStatus?.is_processing && processingStatus.current_video && (
        <div className="panel border-l-2 border-l-[var(--accent)] p-4 mb-6 animate-fade-in">
          <div className="flex flex-col lg:flex-row lg:items-center gap-4">
            {/* Video info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="relative flex w-2 h-2">
                  <span className="absolute inline-flex h-full w-full rounded-full bg-[var(--accent)] opacity-60 animate-ping" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--accent)]" />
                </span>
                <span className="t-label text-[var(--accent)]">
                  {currentStepIndex >= 0 ? PIPELINE_STEPS[currentStepIndex].label : t.processingFallback}
                </span>
                <span className="mono text-[11px] text-[var(--text-muted)]">
                  {processingStatus.current_video.channel_name}
                </span>
              </div>
              <p className="text-sm font-medium text-[var(--text-primary)] truncate">
                {processingStatus.current_video.title}
              </p>
            </div>

            {/* Pipeline step indicator */}
            <div className="flex items-center gap-1 mono text-[11px]">
              {PIPELINE_STEPS.map((step, index) => {
                const isCurrent = index === currentStepIndex
                const isComplete = currentStepIndex >= 0 && index < currentStepIndex
                return (
                  <div key={step.key} className="flex items-center gap-1">
                    <span
                      className={`px-1.5 py-0.5 rounded border ${
                        isCurrent
                          ? 'border-[var(--accent)] text-[var(--accent)] bg-[var(--accent-dim)]'
                          : isComplete
                            ? 'border-[var(--border)] text-[var(--ok)]'
                            : 'border-[var(--border)] text-[var(--text-muted)]'
                      }`}
                    >
                      {step.code}
                    </span>
                    {index < PIPELINE_STEPS.length - 1 && (
                      <span className="text-[var(--text-muted)]">→</span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Channels List */}
        <div className="panel">
          <div className="px-4 py-3 border-b border-[var(--border)]">
            <h2 className="t-label">{t.channels}</h2>
          </div>
          <div className="p-3">
            {channelsLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="w-5 h-5 animate-spin text-[var(--accent)]" />
              </div>
            ) : channels.length === 0 ? (
              <div className="text-center py-12">
                <p className="mono text-xs text-[var(--text-muted)] mb-4">{t.noChannels}</p>
                <button onClick={() => setShowAddModal(true)} className="btn-secondary text-xs">
                  {t.addChannel}
                </button>
              </div>
            ) : (
              <div className="space-y-1.5">
                {channels.map((channel) => (
                  <div
                    key={channel.id}
                    className={`p-3 rounded border cursor-pointer transition-colors ${
                      selectedChannel === channel.id
                        ? 'bg-[var(--bg-2)] border-[var(--accent)]'
                        : 'bg-[var(--bg-0)] border-[var(--border)] hover:border-[var(--border-strong)] hover:bg-[var(--bg-2)]'
                    }`}
                    onClick={() => setSelectedChannel(selectedChannel === channel.id ? null : channel.id)}
                  >
                    <div className="flex justify-between items-start gap-2">
                      <div className="min-w-0">
                        <div className="font-medium text-[13px] text-[var(--text-primary)] truncate">
                          {channel.name}
                        </div>
                        <div className="mono text-[11px] text-[var(--text-muted)] mt-0.5">
                          {channel.video_count} videos
                        </div>
                      </div>
                      <div className="flex gap-0.5 flex-shrink-0">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            refreshChannelMutation.mutate(channel.id)
                          }}
                          className="p-1.5 rounded hover:bg-[var(--bg-3)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                          title={t.refresh}
                        >
                          <RefreshCw className={`w-3.5 h-3.5 ${refreshChannelMutation.isPending ? 'animate-spin' : ''}`} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            if (confirm(t.confirmDeleteChannel)) {
                              deleteChannelMutation.mutate(channel.id)
                            }
                          }}
                          className="p-1.5 rounded hover:bg-[var(--bg-3)] text-[var(--text-muted)] hover:text-[var(--err)] transition-colors"
                          title={t.delete}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Videos List - Import Queue */}
        <div className="lg:col-span-2 panel">
          <div className="flex justify-between items-center px-4 py-3 border-b border-[var(--border)]">
            <h2 className="t-label">
              {t.importQueue}
              {selectedChannel && (
                <span className="text-[var(--accent)] ml-2 normal-case">
                  / {channels.find(c => c.id === selectedChannel)?.name}
                </span>
              )}
            </h2>
            {selectedChannel && (
              <button onClick={() => setSelectedChannel(null)} className="btn-ghost text-xs">
                {t.showAll}
              </button>
            )}
          </div>
          <div className="p-3">
            {videosLoading ? (
              <div className="flex justify-center py-16">
                <Loader2 className="w-5 h-5 animate-spin text-[var(--accent)]" />
              </div>
            ) : videos.length === 0 ? (
              <div className="text-center py-16">
                <p className="mono text-xs text-[var(--text-muted)]">{t.noVideos}</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 max-h-[600px] overflow-y-auto p-1">
                {videos.map((video) => (
                  <VideoCard
                    key={video.id}
                    video={video}
                    onClick={() => setSelectedVideo(video)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Add Channel Modal */}
      {showAddModal && (
        <div className="fixed inset-0 modal-backdrop flex items-center justify-center z-50 animate-fade-in p-4">
          <div className="panel w-full max-w-[420px]" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] bg-[var(--bg-2)]">
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t.addChannel}</h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="p-1.5 rounded hover:bg-[var(--bg-3)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4">
              <div className="mb-4">
                <label className="t-label block mb-2">{t.channelUrlLabel}</label>
                <input
                  type="text"
                  placeholder={t.channelUrlPlaceholder}
                  value={newChannelUrl}
                  onChange={(e) => setNewChannelUrl(e.target.value)}
                  className="input-field w-full"
                  autoFocus
                />
              </div>

              <div className="mb-5">
                <label className="t-label block mb-2">{t.latestNLabel}</label>
                <input
                  type="number"
                  min={1}
                  placeholder={t.latestNPlaceholder}
                  value={newChannelMaxVideos}
                  onChange={(e) => setNewChannelMaxVideos(e.target.value)}
                  className="input-field w-full"
                />
              </div>

              <div className="flex justify-end gap-2">
                <button onClick={() => setShowAddModal(false)} className="btn-ghost">
                  {t.cancel}
                </button>
                <button
                  onClick={() =>
                    addChannelMutation.mutate({
                      url: newChannelUrl,
                      max_videos: newChannelMaxVideos ? Number(newChannelMaxVideos) : undefined,
                    })
                  }
                  disabled={!newChannelUrl || addChannelMutation.isPending}
                  className="btn-primary"
                >
                  {addChannelMutation.isPending ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      {t.adding}
                    </>
                  ) : (
                    t.add
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Video Modal */}
      {selectedVideo && (
        <VideoModal
          video={selectedVideo}
          onClose={() => setSelectedVideo(null)}
        />
      )}
    </div>
  )
}

export default Import

import { Play, Loader2 } from 'lucide-react'
import { Video, videosApi } from '../api/client'

interface VideoCardProps {
  video: Video
  onClick: () => void
}

const STATUS_LABELS: Record<string, string> = {
  done: 'done',
  error: 'error',
  pending: 'queued',
  downloading: 'download',
  transcribing: 'whisper',
  refining: 'refine',
  summarizing: 'summary',
  embedding: 'embed',
}

function VideoCard({ video, onClick }: VideoCardProps) {
  const isCompleted = video.status === 'done'
  const isProcessing = !['done', 'error', 'pending'].includes(video.status)

  const badgeClass =
    video.status === 'done' ? 'badge-success'
    : video.status === 'error' ? 'badge-error'
    : video.status === 'pending' ? 'badge-warning'
    : 'badge-info'

  return (
    <div
      className={`panel overflow-hidden ${
        isCompleted ? 'panel-hover cursor-pointer' : 'opacity-70'
      }`}
      onClick={isCompleted ? onClick : undefined}
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-[var(--bg-0)] border-b border-[var(--border)]">
        {video.thumbnail_path ? (
          <img
            src={videosApi.getThumbnailUrl(video.id)}
            alt={video.title}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Play className="w-6 h-6 text-[var(--text-muted)]" />
          </div>
        )}

        {/* Play overlay for completed videos */}
        {isCompleted && video.video_path && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 hover:opacity-100 transition-opacity">
            <div className="w-11 h-11 rounded border border-[var(--border-strong)] bg-[var(--bg-1)] flex items-center justify-center">
              <Play className="w-5 h-5 text-[var(--accent)] ml-0.5" />
            </div>
          </div>
        )}

        {/* Processing indicator overlay */}
        {isProcessing && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-[var(--border-strong)] bg-[var(--bg-1)]">
              <Loader2 className="w-3.5 h-3.5 text-[var(--info)] animate-spin" />
              <span className="mono text-[11px] uppercase tracking-wider text-[var(--info)]">
                {STATUS_LABELS[video.status] ?? video.status}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-3">
        <h3 className="font-medium text-[13px] text-[var(--text-primary)] line-clamp-2 mb-2 leading-snug" title={video.title}>
          {video.title}
        </h3>

        {/* Channel + Status */}
        <div className="flex items-center justify-between gap-2 mb-2">
          <p className="mono text-[11px] text-[var(--text-muted)] truncate">{video.channel_name}</p>
          <span className={`badge ${badgeClass}`}>{STATUS_LABELS[video.status] ?? video.status}</span>
        </div>

        {/* Summary preview */}
        {video.summary && (
          <p className="text-xs text-[var(--text-secondary)] line-clamp-2 leading-relaxed">
            {video.summary}
          </p>
        )}
      </div>
    </div>
  )
}

export default VideoCard

import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X, ExternalLink, FileText, Loader2 } from 'lucide-react'
import { Video, videosApi } from '../api/client'
import { t } from '../i18n'

interface VideoModalProps {
  video: Video
  onClose: () => void
}

function VideoModal({ video, onClose }: VideoModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [showTranscript, setShowTranscript] = useState(false)

  // Fetch transcript when needed
  const { data: transcriptData, isLoading: transcriptLoading } = useQuery({
    queryKey: ['transcript', video.id],
    queryFn: () => videosApi.getTranscript(video.id),
    enabled: showTranscript,
  })

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose])

  // Prevent body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center modal-backdrop animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-5xl max-h-[90vh] panel overflow-hidden flex flex-col mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] bg-[var(--bg-2)]">
          <h2 className="text-sm font-semibold text-[var(--text-primary)] truncate pr-4">{video.title}</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-[var(--bg-3)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors flex-shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Video Player */}
        <div className="relative bg-black aspect-video flex-shrink-0">
          {video.video_path ? (
            <video
              ref={videoRef}
              className="w-full h-full"
              controls
              autoPlay
              src={videosApi.getStreamUrl(video.id)}
            >
              Your browser does not support the video tag.
            </video>
          ) : (
            <div className="w-full h-full flex items-center justify-center mono text-sm text-[var(--text-muted)]">
              {t.videoUnavailable}
            </div>
          )}
        </div>

        {/* Info Section */}
        <div className="p-4 overflow-y-auto flex-1">
          {/* Channel and actions */}
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <span className="mono text-xs text-[var(--text-secondary)]">{video.channel_name}</span>
            <div className="flex gap-2">
              <a
                href={`https://youtube.com/watch?v=${video.youtube_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-ghost text-xs border border-[var(--border)]"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                YouTube
              </a>
              <button
                onClick={() => setShowTranscript(!showTranscript)}
                className={`text-xs inline-flex items-center gap-1.5 px-3 py-1.5 rounded border transition-colors ${
                  showTranscript
                    ? 'bg-[var(--bg-2)] border-[var(--accent)] text-[var(--accent)]'
                    : 'border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-2)]'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                {t.transcript}
              </button>
            </div>
          </div>

          {/* Summary */}
          {video.summary && (
            <div className="mb-4">
              <h3 className="t-label mb-2">{t.summary}</h3>
              <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{video.summary}</p>
            </div>
          )}

          {/* Transcript */}
          {showTranscript && (
            <div className="mt-4 p-4 rounded border border-[var(--border)] bg-[var(--bg-0)]">
              <h3 className="t-label mb-3">{t.transcript}</h3>
              {transcriptLoading ? (
                <div className="flex items-center gap-2 mono text-xs text-[var(--text-secondary)]">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  {t.loading}
                </div>
              ) : transcriptData?.data.transcript ? (
                <div className="mono text-xs text-[var(--text-secondary)] whitespace-pre-wrap max-h-64 overflow-y-auto leading-relaxed">
                  {transcriptData.data.transcript}
                </div>
              ) : (
                <p className="mono text-xs text-[var(--text-muted)]">{t.noTranscript}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default VideoModal

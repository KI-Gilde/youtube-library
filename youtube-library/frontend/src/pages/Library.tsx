import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Loader2, Play, X } from 'lucide-react'
import { channelsApi, videosApi, Video as VideoType, VideoSearchResult } from '../api/client'
import VideoCard from '../components/VideoCard'
import VideoModal from '../components/VideoModal'
import { t } from '../i18n'


// Search Result Card Component
function SearchResultCard({ result, onClick }: { result: VideoSearchResult; onClick: () => void }) {
  const scoreColor =
    result.score >= 0.7 ? 'var(--ok)' : result.score >= 0.5 ? 'var(--warn)' : 'var(--text-muted)'

  return (
    <div className="panel panel-hover p-4 cursor-pointer" onClick={onClick}>
      <div className="flex gap-4">
        {/* Thumbnail */}
        <div className="relative w-40 h-24 flex-shrink-0 rounded overflow-hidden bg-[var(--bg-0)] border border-[var(--border)] hidden sm:block">
          {result.thumbnail_path ? (
            <img
              src={videosApi.getThumbnailUrl(result.id)}
              alt={result.title}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Play className="w-6 h-6 text-[var(--text-muted)]" />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3 mb-1">
            <h3 className="font-medium text-[var(--text-primary)] line-clamp-1 text-sm">{result.title}</h3>
            <span
              className="mono text-[11px] font-semibold flex-shrink-0 px-1.5 py-0.5 rounded border border-[var(--border)] bg-[var(--bg-0)]"
              style={{ color: scoreColor }}
              title={t.similarityScore}
            >
              {result.score.toFixed(2)}
            </span>
          </div>
          <p className="mono text-[11px] text-[var(--text-muted)] mb-2">{result.channel_name}</p>
          <p className="text-xs text-[var(--text-secondary)] line-clamp-2 leading-relaxed">
            {result.matching_text}
          </p>
        </div>
      </div>
    </div>
  )
}


function Library() {
  const [selectedVideo, setSelectedVideo] = useState<VideoType | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedChannel, setSelectedChannel] = useState<string>('')

  // Debounce search input
  useEffect(() => {
    const timeout = setTimeout(() => {
      setDebouncedSearch(searchQuery)
    }, 400)
    return () => clearTimeout(timeout)
  }, [searchQuery])

  // Queries
  const { data: channelsData } = useQuery({
    queryKey: ['channels'],
    queryFn: () => channelsApi.list(),
  })

  // Only fetch done videos for the library
  const { data: videosData, isLoading: videosLoading } = useQuery({
    queryKey: ['videos-done', selectedChannel],
    queryFn: () => videosApi.list({
      channel_id: selectedChannel || undefined,
      status: 'done',
      per_page: 100
    }),
  })

  // Semantic search query
  const { data: searchData, isLoading: searchLoading } = useQuery({
    queryKey: ['search', debouncedSearch, selectedChannel],
    queryFn: () => videosApi.search(debouncedSearch, selectedChannel || undefined),
    enabled: debouncedSearch.length >= 2,
  })

  const channels = channelsData?.data.channels || []
  const videos = videosData?.data.videos || []
  const searchResults = searchData?.data.results || []
  const isSearching = debouncedSearch.length >= 2

  return (
    <div className="p-4 md:p-8 animate-fade-in">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl mb-1">{t.libraryTitle}</h1>
        <p className="mono text-xs text-[var(--text-muted)]">
          {videos.length} {t.videosIndexed}
        </p>
      </div>

      {/* Search and Filter Bar */}
      <div className="panel p-4 mb-6">
        <div className="flex flex-col md:flex-row gap-3 md:items-center">
          {/* Search Input */}
          <div className="relative flex-1">
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]">
              {searchLoading ? (
                <Loader2 className="w-4 h-4 animate-spin text-[var(--accent)]" />
              ) : (
                <Search className="w-4 h-4" />
              )}
            </div>
            <input
              type="text"
              placeholder={t.searchPlaceholder}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field w-full pl-9 pr-9 py-2.5"
            />
            {searchQuery && (
              <button
                onClick={() => {
                  setSearchQuery('')
                  setDebouncedSearch('')
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Channel Filter */}
          <select
            value={selectedChannel}
            onChange={(e) => setSelectedChannel(e.target.value)}
            className="select-field w-full md:w-auto md:min-w-[200px]"
          >
            <option value="">{t.allChannels}</option>
            {channels.map((channel) => (
              <option key={channel.id} value={channel.id}>
                {channel.name}
              </option>
            ))}
          </select>
        </div>

        {/* Search hint */}
        {!isSearching && (
          <p className="mono text-[11px] text-[var(--text-muted)] mt-2.5">
            <span className="text-[var(--accent)]">//</span> {t.searchHint}
          </p>
        )}
      </div>

      {/* Content Area */}
      {isSearching ? (
        // Search Results
        <div>
          <div className="flex items-center gap-3 mb-4">
            <h2 className="t-label">{t.searchResults}</h2>
            {searchResults.length > 0 && (
              <span className="mono text-[11px] text-[var(--accent)]">
                {searchResults.length} {t.hits}
              </span>
            )}
          </div>

          {searchLoading ? (
            <div className="flex flex-col items-center justify-center py-20">
              <Loader2 className="w-6 h-6 animate-spin text-[var(--accent)] mb-3" />
              <p className="mono text-xs text-[var(--text-secondary)]">{t.searchingTranscripts}</p>
            </div>
          ) : searchResults.length === 0 ? (
            <div className="panel text-center py-16">
              <Search className="w-8 h-8 text-[var(--text-muted)] mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">{t.noHits}</h3>
              <p className="mono text-xs text-[var(--text-muted)]">
                {t.noVideosFoundFor} "{debouncedSearch}"
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {searchResults.map((result) => (
                <SearchResultCard
                  key={result.id}
                  result={result}
                  onClick={async () => {
                    const response = await videosApi.get(result.id)
                    setSelectedVideo(response.data)
                  }}
                />
              ))}
            </div>
          )}
        </div>
      ) : (
        // Video Grid
        <div>
          <div className="flex items-center gap-2 mb-4">
            <h2 className="t-label">
              {t.allVideos}
              {selectedChannel && channels.find(c => c.id === selectedChannel) && (
                <span className="text-[var(--accent)] ml-2 normal-case">
                  / {channels.find(c => c.id === selectedChannel)?.name}
                </span>
              )}
            </h2>
          </div>

          {videosLoading ? (
            <div className="flex justify-center py-20">
              <Loader2 className="w-6 h-6 animate-spin text-[var(--accent)]" />
            </div>
          ) : videos.length === 0 ? (
            <div className="panel text-center py-16">
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">{t.noDoneVideos}</h3>
              <p className="mono text-xs text-[var(--text-muted)]">
                {t.videosAppearHere}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
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

export default Library

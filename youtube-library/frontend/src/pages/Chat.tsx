import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Send, ExternalLink, Bot, RotateCcw, Terminal } from 'lucide-react'
import { chatApi, channelsApi, ChatMessage, ChatSource } from '../api/client'
import { t } from '../i18n'

interface Message extends ChatMessage {
  sources?: ChatSource[]
}

const STORAGE_KEY = 'youtube-library-chat'

function Chat() {
  const [messages, setMessages] = useState<Message[]>(() => {
    const saved = sessionStorage.getItem(STORAGE_KEY)
    return saved ? JSON.parse(saved) : []
  })
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [selectedChannel, setSelectedChannel] = useState<string>('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Save messages to sessionStorage
  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
  }, [messages])

  const clearChat = () => {
    setMessages([])
    sessionStorage.removeItem(STORAGE_KEY)
  }

  const { data: channelsData } = useQuery({
    queryKey: ['channels'],
    queryFn: () => channelsApi.list(),
  })

  const channels = channelsData?.data.channels || []

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const updateLastMessage = (update: (message: Message) => Message) => {
    setMessages((prev) =>
      prev.map((message, index) => (index === prev.length - 1 ? update(message) : message))
    )
  }

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return

    const question = input
    const history = messages.map(({ role, content }) => ({ role, content }))

    // Append the user message plus an empty assistant bubble that fills as tokens stream in
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: question },
      { role: 'assistant', content: '' },
    ])
    setInput('')
    setIsLoading(true)

    try {
      await chatApi.stream(question, history, selectedChannel || undefined, {
        onSources: (sources) => updateLastMessage((m) => ({ ...m, sources })),
        onContent: (chunk) => updateLastMessage((m) => ({ ...m, content: m.content + chunk })),
      })
    } catch (error) {
      console.error('Chat error:', error)
      updateLastMessage((m) => ({
        ...m,
        content: m.content || t.chatError,
      }))
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const isStreaming = (index: number) =>
    isLoading && index === messages.length - 1 && messages[index].role === 'assistant'

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 md:px-6 py-3 border-b border-[var(--border)] bg-[var(--bg-1)] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-lg">{t.chatTitle}</h1>
          <p className="mono text-[11px] text-[var(--text-muted)]">{t.ragOver} {channels.reduce((n, c) => n + c.video_count, 0)} {t.videosWord}</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {messages.length > 0 && (
            <button onClick={clearChat} className="btn-ghost">
              <RotateCcw className="w-3.5 h-3.5" />
              {t.newChat}
            </button>
          )}
          <select
            value={selectedChannel}
            onChange={(e) => setSelectedChannel(e.target.value)}
            className="select-field min-w-[180px]"
          >
            <option value="">{t.allChannels}</option>
            {channels.map((channel) => (
              <option key={channel.id} value={channel.id}>
                {channel.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full animate-fade-in">
            <div className="w-14 h-14 rounded border border-[var(--border-strong)] bg-[var(--bg-1)] flex items-center justify-center mb-5">
              <Terminal className="w-6 h-6 text-[var(--accent)]" />
            </div>
            <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-2">{t.askYourLibrary}</h2>
            <p className="text-sm text-[var(--text-secondary)] text-center max-w-md">
              {t.chatIntro}
            </p>

            {/* Example prompts */}
            <div className="mt-6 flex flex-wrap gap-2 justify-center max-w-xl">
              {t.examplePrompts.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => setInput(prompt)}
                  className="mono text-xs px-3 py-1.5 rounded border border-[var(--border)] bg-[var(--bg-1)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-strong)] hover:bg-[var(--bg-2)] transition-colors"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4 max-w-4xl mx-auto">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex gap-3 animate-fade-in ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {message.role === 'assistant' && (
                  <div className="w-8 h-8 rounded border border-[var(--border-strong)] bg-[var(--bg-1)] flex items-center justify-center flex-shrink-0">
                    <Bot className="w-4 h-4 text-[var(--accent)]" />
                  </div>
                )}

                <div
                  className={`max-w-2xl rounded p-3.5 border ${
                    message.role === 'user'
                      ? 'bg-[var(--bg-2)] border-[var(--border-strong)]'
                      : 'bg-[var(--bg-1)] border-[var(--border)]'
                  }`}
                >
                  {message.role === 'assistant' && message.content === '' ? (
                    <span className="mono text-xs text-[var(--text-muted)] cursor-blink">{t.searchingContext}</span>
                  ) : (
                    <div
                      className={`whitespace-pre-wrap leading-relaxed text-sm ${
                        isStreaming(index) ? 'cursor-blink' : ''
                      }`}
                    >
                      {message.content}
                    </div>
                  )}

                  {/* Sources */}
                  {message.sources && message.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-[var(--border)]">
                      <div className="t-label mb-2">{t.sources}</div>
                      <div className="space-y-1">
                        {message.sources.map((source, i) => (
                          <a
                            key={i}
                            href={`https://youtube.com/watch?v=${source.youtube_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 mono text-xs text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors"
                          >
                            <span className="text-[var(--text-muted)]">[{i + 1}]</span>
                            <span className="truncate">{source.title}</span>
                            <ExternalLink className="w-3 h-3 flex-shrink-0" />
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {message.role === 'user' && (
                  <div className="w-8 h-8 rounded border border-[var(--border-strong)] bg-[var(--bg-2)] flex items-center justify-center flex-shrink-0">
                    <span className="mono text-[10px] font-semibold text-[var(--text-secondary)]">{t.you}</span>
                  </div>
                )}
              </div>
            ))}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-[var(--border)] bg-[var(--bg-1)]">
        <div className="max-w-4xl mx-auto flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={t.askPlaceholder}
            rows={1}
            className="input-field flex-1 resize-none min-h-[44px] py-3"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            className="btn-primary px-4"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

export default Chat

import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { MessageSquare, Download, BookOpen, Terminal } from 'lucide-react'
import Import from './pages/Import'
import Library from './pages/Library'
import Chat from './pages/Chat'
import { t } from './i18n'

function App() {
  const location = useLocation()

  const navItems = [
    { path: '/import', icon: Download, label: t.navImport, index: '01' },
    { path: '/', icon: BookOpen, label: t.navLibrary, index: '02' },
    { path: '/chat', icon: MessageSquare, label: t.navChat, index: '03' },
  ]

  return (
    <div className="h-screen flex flex-col lg:flex-row bg-[var(--bg-0)]">
      {/* Mobile top bar */}
      <header className="lg:hidden bg-[var(--bg-1)] border-b border-[var(--border)] sticky top-0 z-40">
        <div className="flex items-center justify-between gap-3 px-4 py-2.5">
          <Link to="/" className="flex items-center gap-2.5 shrink-0">
            <div className="w-7 h-7 border border-[var(--border-strong)] rounded bg-[var(--bg-0)] flex items-center justify-center">
              <Terminal className="w-3.5 h-3.5 text-[var(--accent)]" />
            </div>
            <span className="mono text-sm font-semibold text-[var(--text-primary)]">
              yt<span className="text-[var(--text-muted)]">_</span>library
            </span>
          </Link>
          <nav className="flex items-center gap-1">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  aria-label={item.label}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded border transition-colors ${
                    isActive
                      ? 'bg-[var(--bg-2)] border-[var(--border-strong)] text-[var(--text-primary)]'
                      : 'text-[var(--text-secondary)] border-transparent hover:text-[var(--text-primary)] hover:bg-[var(--bg-2)]'
                  }`}
                >
                  <item.icon className="w-4 h-4" />
                  <span className="hidden sm:inline text-xs font-medium">{item.label}</span>
                </Link>
              )
            })}
          </nav>
        </div>
      </header>

      {/* Sidebar (desktop) */}
      <aside className="hidden lg:flex w-60 bg-[var(--bg-1)] border-r border-[var(--border)] flex-col">
        {/* Logo */}
        <div className="px-4 py-5 border-b border-[var(--border)]">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 border border-[var(--border-strong)] rounded bg-[var(--bg-0)] flex items-center justify-center">
              <Terminal className="w-4 h-4 text-[var(--accent)]" />
            </div>
            <div className="leading-tight">
              <span className="mono text-sm font-semibold text-[var(--text-primary)] block">
                yt<span className="text-[var(--text-muted)]">_</span>library
              </span>
              <span className="t-label">transcript index</span>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-4 py-2.5 border-l-2 transition-colors ${
                  isActive
                    ? 'border-[var(--accent)] bg-[var(--bg-2)] text-[var(--text-primary)]'
                    : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-2)]'
                }`}
              >
                <span className={`mono text-[10px] ${isActive ? 'text-[var(--accent)]' : 'text-[var(--text-muted)]'}`}>
                  {item.index}
                </span>
                <item.icon className="w-4 h-4" />
                <span className="text-sm font-medium">{item.label}</span>
              </Link>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-[var(--border)]">
          <div className="t-label">v1.0 // local</div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Library />} />
          <Route path="/import" element={<Import />} />
          <Route path="/chat" element={<Chat />} />
        </Routes>
      </main>
    </div>
  )
}

export default App

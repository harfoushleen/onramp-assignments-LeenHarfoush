import type { ReactNode } from 'react'

// Only highlights literal substring matches -- semantic results whose
// chunk_text doesn't literally contain the query (the common case, since
// embedding similarity doesn't imply shared text) just render unhighlighted.
export function highlightMatches(text: string, query: string): ReactNode[] {
  const trimmed = query.trim()
  if (!trimmed) return [text]

  const escaped = trimmed.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'))
  if (parts.length === 1) return [text]

  return parts.map((part, index) =>
    part.toLowerCase() === trimmed.toLowerCase() ? (
      <mark key={index} className="highlight">
        {part}
      </mark>
    ) : (
      <span key={index}>{part}</span>
    ),
  )
}

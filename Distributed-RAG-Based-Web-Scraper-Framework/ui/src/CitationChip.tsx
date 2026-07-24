import type { ReactNode } from 'react'

export function CitationChip({ children }: { children: ReactNode }) {
  return <span className="chip">{children}</span>
}

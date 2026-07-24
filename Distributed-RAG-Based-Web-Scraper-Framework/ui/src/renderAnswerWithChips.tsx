import type { ReactNode } from 'react'
import { CitationChip } from './CitationChip'

// answer_query() (rag.py) writes citations into the answer text as bracket
// markers -- usually a single number ("[1]") but the model sometimes cites
// several sources in one bracket ("[1, 3]"), so match on the whole bracket
// and render one chip per number inside it.
export function renderAnswerWithChips(answer: string): ReactNode[] {
  const parts = answer.split(/(\[\s*\d+(?:\s*,\s*\d+)*\s*\])/g)
  return parts.map((part, index) => {
    const match = /^\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]$/.exec(part)
    if (match) {
      const numbers = match[1].split(',').map((n) => n.trim())
      return (
        <span key={index}>
          {numbers.map((n, i) => (
            <CitationChip key={i}>{n}</CitationChip>
          ))}
        </span>
      )
    }
    return <span key={index}>{part}</span>
  })
}

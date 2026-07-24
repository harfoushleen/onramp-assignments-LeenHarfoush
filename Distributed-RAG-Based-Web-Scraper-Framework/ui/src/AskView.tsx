import { useState } from 'react'
import type { AskResponse } from './api'
import { ask } from './api'
import { CitationChip } from './CitationChip'
import { IconArrow } from './icons'
import { renderAnswerWithChips } from './renderAnswerWithChips'

function AskView() {
  const [query, setQuery] = useState('')
  const [response, setResponse] = useState<AskResponse | null>(null)
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [error, setError] = useState('')

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!query.trim()) return

    setStatus('loading')
    setError('')
    try {
      const result = await ask(query)
      setResponse(result)
      setStatus('idle')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'the API is unreachable')
      setResponse(null)
      setStatus('error')
    }
  }

  return (
    <section className="view">
      <form className="input-row" onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="What is the price of a book about science?"
          aria-label="question"
        />
        <button type="submit" className="icon-button" disabled={status === 'loading'}>
          <IconArrow />
        </button>
      </form>

      {status === 'loading' && <p className="status-message">generating answer...</p>}
      {status === 'error' && (
        <p className="status-message status-error" role="alert">
          {error}
        </p>
      )}
      {status === 'idle' && response !== null && (
        <div>
          <div className="card answer-card">
            <p>{renderAnswerWithChips(response.answer)}</p>
          </div>

          {response.sources.length > 0 && (
            <>
              <h4 className="sources-heading">Sources</h4>
              <ul className="sources-list">
                {response.sources.map((source) => (
                  <li className="card source-row" key={source.citation}>
                    <CitationChip>{source.citation}</CitationChip>
                    <a href={source.url} target="_blank" rel="noreferrer">
                      {source.url.replace(/^https?:\/\//, '')}
                    </a>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  )
}

export default AskView

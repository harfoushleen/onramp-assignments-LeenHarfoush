import { useState } from 'react'
import type { KeywordSearchResult, SemanticSearchResult } from './api'
import { searchKeyword, searchSemantic } from './api'
import { highlightMatches } from './highlightMatches'
import { IconExternal, IconSearch } from './icons'
import { titleFromUrl } from './titleFromUrl'

type SearchMode = 'keyword' | 'semantic'
type Result = KeywordSearchResult | SemanticSearchResult

function isSemanticResult(result: Result): result is SemanticSearchResult {
  return 'chunk_text' in result
}

function SearchView() {
  const [mode, setMode] = useState<SearchMode>('keyword')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Result[] | null>(null)
  const [submittedQuery, setSubmittedQuery] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [error, setError] = useState('')

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!query.trim()) return

    setStatus('loading')
    setError('')
    try {
      const response =
        mode === 'keyword' ? await searchKeyword(query) : await searchSemantic(query)
      setResults(response.results)
      setSubmittedQuery(query)
      setStatus('idle')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'the API is unreachable')
      setResults(null)
      setStatus('error')
    }
  }

  return (
    <section className="view">
      <div className="radio-group" role="radiogroup" aria-label="search mode">
        <label className="radio">
          <input
            type="radio"
            name="mode"
            value="keyword"
            checked={mode === 'keyword'}
            onChange={() => setMode('keyword')}
          />
          Keyword
        </label>
        <label className="radio">
          <input
            type="radio"
            name="mode"
            value="semantic"
            checked={mode === 'semantic'}
            onChange={() => setMode('semantic')}
          />
          Semantic
        </label>
      </div>

      <form className="input-row" onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search scraped pages..."
          aria-label="search query"
        />
        <button type="submit" className="icon-button" disabled={status === 'loading'}>
          <IconSearch />
        </button>
      </form>

      {status === 'loading' && <p className="status-message">searching...</p>}
      {status === 'error' && (
        <p className="status-message status-error" role="alert">
          {error}
        </p>
      )}
      {status === 'idle' && results !== null && results.length === 0 && (
        <p className="status-message">no results found</p>
      )}
      {status === 'idle' && results !== null && results.length > 0 && (
        <ul className="card-list">
          {results.map((result) => (
            <li
              className="card"
              key={isSemanticResult(result) ? result.chunk_id : `${result.page_id}-${result.url}`}
            >
              <div className="card-heading">
                <h3>{titleFromUrl(result.url)}</h3>
                {isSemanticResult(result) && (
                  <span className="badge">distance {result.distance.toFixed(2)}</span>
                )}
              </div>
              <p className="card-text">
                {highlightMatches(
                  isSemanticResult(result) ? result.chunk_text : result.snippet,
                  submittedQuery,
                )}
              </p>
              <a className="card-link" href={result.url} target="_blank" rel="noreferrer">
                {result.url.replace(/^https?:\/\//, '')}
                <IconExternal />
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default SearchView

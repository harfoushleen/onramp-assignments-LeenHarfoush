import { useState } from 'react'
import AskView from './AskView'
import { IconChat, IconSearch } from './icons'
import SearchView from './SearchView'

type Tab = 'search' | 'ask'

function App() {
  const [tab, setTab] = useState<Tab>('search')

  return (
    <main className="page">
      <header className="page-header">
        <h1>Distributed RAG web scraper</h1>
        <p className="subtitle">Search scraped pages or ask a grounded question</p>
      </header>

      <div className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'search'}
          className={`tab ${tab === 'search' ? 'tab-active' : ''}`}
          onClick={() => setTab('search')}
        >
          <IconSearch />
          Search
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'ask'}
          className={`tab ${tab === 'ask' ? 'tab-active' : ''}`}
          onClick={() => setTab('ask')}
        >
          <IconChat />
          Ask
        </button>
      </div>

      {tab === 'search' ? <SearchView /> : <AskView />}
    </main>
  )
}

export default App

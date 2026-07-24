import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders the heading and defaults to the search tab', () => {
    render(<App />)
    expect(screen.getByText('Distributed RAG web scraper')).toBeInTheDocument()
    expect(screen.getByLabelText('search query')).toBeInTheDocument()
  })
})

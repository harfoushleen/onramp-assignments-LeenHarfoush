import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SearchView from './SearchView'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SearchView', () => {
  it('calls the keyword search endpoint with the typed query and renders a result', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        query: 'books',
        results: [{ page_id: 1, url: 'https://example.com/books', snippet: '...books...' }],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<SearchView />)
    fireEvent.change(screen.getByLabelText('search query'), { target: { value: 'books' } })
    fireEvent.submit(screen.getByLabelText('search query').closest('form')!)

    // the query is now split across a highlighted <mark> and surrounding
    // <span>s, so match on the mark's own text rather than the full snippet
    const mark = await screen.findByText('books', { selector: 'mark' })
    expect(mark).toBeInTheDocument()

    const requestedUrl = fetchMock.mock.calls[0][0] as string
    expect(requestedUrl).toContain('/search/keyword')
    expect(requestedUrl).toContain('q=books')
  })

  it('shows a clean error message when the API is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    render(<SearchView />)
    fireEvent.change(screen.getByLabelText('search query'), { target: { value: 'books' } })
    fireEvent.submit(screen.getByLabelText('search query').closest('form')!)

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Failed to fetch'))
  })
})

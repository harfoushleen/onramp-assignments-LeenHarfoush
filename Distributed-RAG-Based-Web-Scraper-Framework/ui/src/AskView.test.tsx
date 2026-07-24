import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AskView from './AskView'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AskView', () => {
  it('posts the question to /ask and renders the answer with a citation link', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        answer: 'Books cost £16.85 [1].',
        sources: [{ citation: 1, url: 'https://example.com/book', chunk_text: '...' }],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<AskView />)
    fireEvent.change(screen.getByLabelText('question'), { target: { value: 'how much?' } })
    fireEvent.submit(screen.getByLabelText('question').closest('form')!)

    await waitFor(() => expect(screen.getByText(/Books cost £16.85/)).toBeInTheDocument())

    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toContain('/ask')
    expect(JSON.parse(options.body)).toEqual({ query: 'how much?' })
    // inline "[1]" is rendered as a numbered chip, not a plain bracket
    expect(screen.queryByText('[1]')).not.toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'example.com/book' })
    expect(link).toHaveAttribute('href', 'https://example.com/book')
  })
})

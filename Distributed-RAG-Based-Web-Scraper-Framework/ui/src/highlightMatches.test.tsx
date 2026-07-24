import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { highlightMatches } from './highlightMatches'

describe('highlightMatches', () => {
  it('wraps a case-insensitive substring match in a <mark>', () => {
    const { container } = render(<p>{highlightMatches('The Books Are Here', 'books')}</p>)
    const mark = container.querySelector('mark')
    expect(mark).not.toBeNull()
    expect(mark).toHaveTextContent('Books')
  })

  it('does not crash on regex special characters and highlights the literal match', () => {
    const { container } = render(<p>{highlightMatches('Learning C++ is fun', 'C++')}</p>)
    const mark = container.querySelector('mark')
    expect(mark).toHaveTextContent('C++')
  })

  it('renders plain text with no <mark> when there is no literal match', () => {
    const { container } = render(<p>{highlightMatches('semantically related text', 'unrelated')}</p>)
    expect(container.querySelector('mark')).toBeNull()
  })
})

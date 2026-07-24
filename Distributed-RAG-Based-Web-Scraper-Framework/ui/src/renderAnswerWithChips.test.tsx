import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAnswerWithChips } from './renderAnswerWithChips'

describe('renderAnswerWithChips', () => {
  it('renders a single-number bracket as one chip', () => {
    const { container } = render(<p>{renderAnswerWithChips('Einstein said it [1].')}</p>)
    const chips = container.querySelectorAll('.chip')
    expect(chips).toHaveLength(1)
    expect(chips[0]).toHaveTextContent('1')
  })

  it('renders a multi-number bracket like "[1, 3]" as separate chips, not literal text', () => {
    const { container } = render(<p>{renderAnswerWithChips('Priced at £57.36 [1, 3]')}</p>)
    const chips = container.querySelectorAll('.chip')
    expect(chips).toHaveLength(2)
    expect(chips[0]).toHaveTextContent('1')
    expect(chips[1]).toHaveTextContent('3')
    expect(container).not.toHaveTextContent('[1, 3]')
  })
})

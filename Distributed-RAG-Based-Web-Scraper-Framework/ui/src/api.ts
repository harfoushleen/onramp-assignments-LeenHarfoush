// Matches api/src/api/schemas.py -- kept in sync manually since the two
// projects don't share a codegen step.

export interface KeywordSearchResult {
  page_id: number
  url: string
  snippet: string
}

export interface KeywordSearchResponse {
  query: string
  results: KeywordSearchResult[]
}

export interface SemanticSearchResult {
  chunk_id: number
  page_id: number
  url: string
  chunk_text: string
  distance: number
}

export interface SemanticSearchResponse {
  query: string
  results: SemanticSearchResult[]
}

export interface AskSource {
  citation: number
  url: string
  chunk_text: string
}

export interface AskResponse {
  answer: string
  sources: AskSource[]
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      // response body wasn't JSON -- fall back to statusText
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export async function searchKeyword(q: string): Promise<KeywordSearchResponse> {
  const url = `${API_URL}/search/keyword?${new URLSearchParams({ q })}`
  return handleResponse(await fetch(url))
}

export async function searchSemantic(q: string): Promise<SemanticSearchResponse> {
  const url = `${API_URL}/search/semantic?${new URLSearchParams({ q })}`
  return handleResponse(await fetch(url))
}

export async function ask(query: string): Promise<AskResponse> {
  const response = await fetch(`${API_URL}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  return handleResponse(response)
}

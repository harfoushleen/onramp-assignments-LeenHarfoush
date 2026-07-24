// The API doesn't return a page title (schemas.py has no such field, only
// url/snippet/chunk_text), so result cards need a readable heading derived
// from the url's slug -- e.g. ".../the-songs-of-the-gods_763/index.html" ->
// "The Songs Of The Gods". Best-effort, not a real title.
export function titleFromUrl(url: string): string {
  const segments = url.replace(/\/index\.html?$/, '').split('/').filter(Boolean)
  const slug = segments.at(-1) ?? url
  const words = slug
    .replace(/_\d+$/, '')
    .split(/[-_]/)
    .filter(Boolean)
  if (words.length === 0) return url
  return words.map((word) => word[0].toUpperCase() + word.slice(1)).join(' ')
}

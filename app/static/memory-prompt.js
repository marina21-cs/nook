// Deliberately bounded parsing. Unclear messages ask for fields; no location is invented.
export function parseMemoryPrompt(value) {
  const text = value.trim().replace(/\s+/g, ' ').replace(/[.!]$/, '');
  const empty = {name: '', location: ''};
  if (!text || /[?]|[.!]\s|\b(?:maybe|perhaps|not sure|forgot|don't know|do not know|where|not|isn't|aren't)\b/i.test(text)) return empty;
  const body = text.replace(/^(?:please\s+)?(?:remember|save)(?:\s+that)?\s+/i, '')
    .replace(/^I\s+(?:left|put|keep|stored|placed)\s+/i, '');
  const match = body.match(/^(.+?)\s+(?:(?:is|are)\s+)?((?:in|inside|on|under|at|behind|beside|near|next to)\s+.+)$/i);
  if (!match) return empty;
  const name = match[1].trim(), location = match[2].trim();
  if (name.length > 80 || location.length > 240 || /^(?:it|this|that|these|those|something|stuff)$/i.test(name)
    || /\b(?:and|or|is|are|was|were)\b/i.test(name) || /\b(?:or|and .+? (?:is|are))\b/i.test(location)) return empty;
  return {name, location};
}

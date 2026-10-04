/**
 * Narration parity for check-content: slides/script.md (the narration, by
 * slide and live segment) and docs/demo/video-monologue.md (the same words,
 * split across the four speakers) must say exactly the same thing.
 *
 *   script.md          [click 2] [Juan Young] spoken words ...
 *   video-monologue.md **Juan Young:** spoken words ...
 *                      | Juan Young | 118 | ... |   (the word-count table)
 *
 * Bracketed cues are not spoken. A `[Name]` tag in script.md sets the speaker
 * until the next tag. The check compares the two word sequences and their
 * speakers, and the monologue's word-count table against the real counts.
 */
export interface Spoken { word: string; speaker: string }

const norm = (w: string) => w.toLowerCase().replace(/[^\p{L}\p{N}'-]/gu, '')
const isWord = (w: string) => /[\p{L}\p{N}]/u.test(w)

/** The spoken words of script.md in order, each with its speaker ('' before any tag). */
export function scriptWords(script: string, team: readonly string[]): Spoken[] {
  const out: Spoken[] = []
  let speaker = ''
  for (const part of script.split(/^##\s+/m).slice(1)) {
    const body = part.split('\n').slice(1).join('\n').replace(/<!--[\s\S]*?-->/g, '')
    for (const line of body.split('\n')) {
      if (/^\s*(#|\||>|```)/.test(line)) continue
      for (const tok of line.split(/(\[[^\]]*\])/)) {
        const tag = tok.match(/^\[([^\]]*)\]$/)
        if (tag) {
          if (team.includes(tag[1])) speaker = tag[1]
          continue
        }
        for (const w of tok.replace(/[*_`]/g, '').split(/\s+/)) if (isWord(w)) out.push({ word: norm(w), speaker })
      }
    }
  }
  return out
}

/** The spoken words of the monologue: every line that starts with **Name:**. */
export function monologueWords(md: string, team: readonly string[]): Spoken[] {
  const out: Spoken[] = []
  for (const line of md.replace(/<!--[\s\S]*?-->/g, '').split('\n')) {
    const m = line.match(/^\*\*([^*:]+):\*\*\s*(.*)$/)
    if (!m || !team.includes(m[1])) continue
    const text = m[2].replace(/\[[^\]]*\]/g, ' ').replace(/[*_`]/g, '')
    for (const w of text.split(/\s+/)) if (isWord(w)) out.push({ word: norm(w), speaker: m[1] })
  }
  return out
}

/** The word-count table of the monologue: rows whose first cell is a speaker and second a number. */
export function monologueTable(md: string, team: readonly string[]): Map<string, number> {
  const rows = new Map<string, number>()
  for (const line of md.split('\n')) {
    const cells = line.split('|').map((c) => c.trim())
    if (cells.length > 3 && team.includes(cells[1]) && /^\d+$/.test(cells[2])) rows.set(cells[1], Number(cells[2]))
  }
  return rows
}

export function countBySpeaker(words: Spoken[]): Map<string, number> {
  const m = new Map<string, number>()
  for (const w of words) m.set(w.speaker, (m.get(w.speaker) ?? 0) + 1)
  return m
}

/** The first difference between two spoken sequences, as a message, or null when they agree. */
export function firstDifference(a: Spoken[], b: Spoken[]): string | null {
  const n = Math.max(a.length, b.length)
  for (let i = 0; i < n; i++) {
    if (a[i]?.word === b[i]?.word && a[i]?.speaker === b[i]?.speaker) continue
    const ctx = (s: Spoken[]) => s.slice(Math.max(0, i - 4), i + 3).map((w) => w.word).join(' ')
    const who = (s: Spoken[]) => s[i] ? `"${s[i].word}" (${s[i].speaker || 'no speaker'})` : 'the end'
    return `word ${i + 1}: script.md has ${who(a)} in "${ctx(a)}", the monologue has ${who(b)} in "${ctx(b)}"`
  }
  return null
}

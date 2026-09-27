/**
 * The text colour pairs the deck is allowed to use, with the WCAG ratio each
 * must meet. pnpm check:content computes every ratio and fails below it.
 *
 *   4.5  body-size text (anything under 24 px bold in the 1920 x 1080 space)
 *   3.0  large text only (24 px bold and up, or 32 px regular and up)
 *
 * If a scene needs a new text/background combination, add it here first.
 */
import { C } from './kit'

export interface TextPair {
  fg: keyof typeof C
  bg: keyof typeof C
  min: 4.5 | 3
  use: string
}

export const TEXT_PAIRS: readonly TextPair[] = [
  { fg: 'paper', bg: 'bg', min: 4.5, use: 'main text' },
  { fg: 'dim', bg: 'bg', min: 4.5, use: 'secondary text' },
  { fg: 'mute', bg: 'bg', min: 4.5, use: 'captions, citations, kind labels' },
  { fg: 'blueText', bg: 'bg', min: 4.5, use: 'model labels at body size' },
  { fg: 'redText', bg: 'bg', min: 4.5, use: 'risk labels at body size' },
  { fg: 'yellow', bg: 'bg', min: 4.5, use: 'decision labels at any size' },
  { fg: 'blue', bg: 'bg', min: 3, use: 'large model headline words' },
  { fg: 'red', bg: 'bg', min: 3, use: 'large risk headline words' },
  { fg: 'paper', bg: 'bg2', min: 4.5, use: 'text on the raised surface' },
  { fg: 'mute', bg: 'bg2', min: 4.5, use: 'captions on the raised surface' },
  { fg: 'blueText', bg: 'blueDeep', min: 4.5, use: 'model chips' },
  { fg: 'redText', bg: 'redDeep', min: 4.5, use: 'risk chips' },
  { fg: 'yellow', bg: 'yellowDeep', min: 4.5, use: 'decision chips' },
  { fg: 'paper', bg: 'blueDeep', min: 4.5, use: 'text inside a model node' },
  { fg: 'paper', bg: 'yellowDeep', min: 4.5, use: 'text inside a decision node' },
  { fg: 'paper', bg: 'redDeep', min: 4.5, use: 'text inside a risk node' },
  { fg: 'bg', bg: 'yellow', min: 4.5, use: 'ink on a filled yellow tab' },
  { fg: 'bg', bg: 'paper', min: 4.5, use: 'ink on a filled paper tab' },
  { fg: 'bg', bg: 'blue', min: 4.5, use: 'ink on a filled blue tab' },
  { fg: 'bg', bg: 'red', min: 3, use: 'ink on a filled red tab or field, large only' },
  // colour fields and the light-gray slide
  { fg: 'inkDim', bg: 'paper', min: 4.5, use: 'secondary text on the light-gray slide' },
  { fg: 'inkMute', bg: 'paper', min: 4.5, use: 'captions and citations on the light-gray slide' },
  { fg: 'inkDim', bg: 'yellow', min: 4.5, use: 'secondary text on a yellow field' },]

const lin = (v: number) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
export function luminance(hex: string) {
  const n = Number.parseInt(hex.slice(1), 16)
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => lin(v / 255))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
export function ratio(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

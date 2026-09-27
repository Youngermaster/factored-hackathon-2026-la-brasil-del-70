/**
 * Scene strings: every word a scene draws lives in one file, keyed by scene:
 *
 *   locales/en.yml
 *     hook:   { title: ..., ... }
 *     thesis: { ... }
 *
 * Kept out of the drawing code so wording can be edited without touching a
 * scene, and kept out of vue-i18n on purpose: canvas text is plain strings,
 * and vue-i18n's compiler rejects the braces and pipes code-like labels need.
 * pnpm check:content fails when a scene draws a key the file does not define.
 */
import { parse } from 'yaml'
import raw from '../../locales/en.yml?raw'

type Strings = Record<string, Record<string, string>>

export const sceneStrings: Strings = (parse(raw) ?? {}) as Strings

/**
 * L(key) for a scene. With a variant (<Scene name="x" v="alt" />), `alt_key`
 * wins over `key`, so one scene can serve several slides. A missing key
 * renders as a visible marker instead of a blank.
 */
export function labeler(name: string, variant?: string) {
  const s = sceneStrings[name] ?? {}
  const get = (k: string) => {
    const v = s[k]
    return v === undefined || v === null ? undefined : String(v)
  }
  return (key: string) => (variant ? get(`${variant}_${key}`) : undefined) ?? get(key) ?? `[${name}.${key}]`
}

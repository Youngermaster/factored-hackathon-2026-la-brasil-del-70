/**
 * Content drift guard (part of `pnpm verify`).
 *
 *   1. scenes: every L('key') exists in locales/en.yml; clicks match cues
 *   2. metrics: every M('key') exists; every entry has a kind and a source that
 *      exists; pending metrics are listed, and --strict fails while any remain
 *   3. tokens: styles/tokens.css and the kit's C object agree
 *   4. contrast: every allowed text pair meets its WCAG ratio
 *   5. script: every slide has a narration section; total spoken duration at
 *      150 words per minute sits inside the declared target
 *   6. writing: no em dashes in anything shown or spoken
 *   7. naming: no known variant spelling of the product, team, systems,
 *      workflows, metrics or levels; team names identical on the close slide,
 *      in script.md and in the README; placeholders fail under --strict
 *   8. intervals and fractions agree with the values they describe
 *
 *   pnpm check:content            report, fail on errors
 *   pnpm check:content --strict   also fail while any metric is pending
 */
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { parse } from 'yaml'
import { C } from '../lib/scene/kit'
import { TEXT_PAIRS, ratio } from '../lib/scene/contrast'
import { METRIC_KINDS } from '../lib/metric-kinds'
import { countBySpeaker, firstDifference, monologueTable, monologueWords, scriptWords } from './narration'

const ROOT = process.cwd()
const REPO = resolve(ROOT, '..')
const strict = process.argv.includes('--strict')
let errors = 0
let warnings = 0
const fail = (m: string) => { console.error(`  FAIL ${m}`); errors++ }
const warn = (m: string) => { console.warn(`  warn ${m}`); warnings++ }
const ok = (m: string) => console.log(`  ok   ${m}`)
const read = (p: string) => readFileSync(join(ROOT, p), 'utf8')
const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/[^\n]*/g, '$1')

// ── 1. scenes and strings ──────────────────────────────────────────────────
console.log('\nscenes and strings')
const strings = (parse(read('locales/en.yml')) ?? {}) as Record<string, Record<string, unknown>>
const slidesMd = read('slides.md')
const sceneNames = readdirSync(join(ROOT, 'scenes')).filter((f) => f.endsWith('.ts') && f !== 'index.ts').map((f) => f.slice(0, -3))
const cueCount = new Map<string, number>()
const usedMetrics = new Set<string>()
const metricFamilies: string[] = []
for (const name of sceneNames) {
  // a scene may split its drawing into scenes/parts/<name>-*.ts; those strings count as its own
  const parts = existsSync(join(ROOT, 'scenes/parts')) ? readdirSync(join(ROOT, 'scenes/parts')).filter((f) => f.startsWith(`${name}-`)) : []
  const src = strip([read(`scenes/${name}.ts`), ...parts.map((f) => read(`scenes/parts/${f}`))].join('\n'))
  const ident = src.match(/cues:\s*([A-Z_][A-Z0-9_]*)\b/)?.[1]
  const cues = ident ? src.match(new RegExp(`const ${ident} = \\[([^\\]]*)\\]`)) : src.match(/cues:\s*\[([^\]]*)\]/)
  if (!cues) fail(`scenes/${name}.ts has no cues array`)
  else cueCount.set(name, cues[1].split(',').filter((x) => x.trim()).length)
  const block = strings[name]
  if (!block) { fail(`locales/en.yml has no "${name}" block`); continue }
  const keys = Object.keys(block)
  const used = new Set<string>()
  const families: string[] = []
  for (const m of src.matchAll(/\bL\(\s*'([^']+)'\s*\)/g)) {
    used.add(m[1])
    if (!keys.includes(m[1])) fail(`scene ${name} draws L('${m[1]}') but locales/en.yml has no ${name}.${m[1]}`)
  }
  for (const m of src.matchAll(/\bL\(\s*`([^`$]*)\$\{/g)) families.push(m[1])
  const dynamic = /\bL\(\s*[A-Za-z_][\w.[\]]*\s*[),]/.test(src)
  for (const k of keys) {
    const hit = used.has(k) || families.some((p) => p && k.startsWith(p))
    if (!hit && !dynamic) warn(`${name}.${k} is defined but never drawn`)
  }
  // metric keys appear as M('key') or as string literals in row tables passed to M()
  for (const m of src.matchAll(/'([a-z_0-9]+(?:\.[a-z_0-9]+)+)'/g)) usedMetrics.add(m[1])
  for (const m of src.matchAll(/\bM\(\s*`([^`$]*)\$\{/g)) metricFamilies.push(m[1])
}
const blocks = slidesMd.split(/^---$/m)
const aliases: string[] = []
for (let i = 0; i < blocks.length - 1; i++) {
  const use = blocks[i + 1].match(/<Scene\s+name="(\w+)"/)
  const alias = blocks[i].match(/^routeAlias:\s*(\S+)/m)?.[1]
  if (!use || !alias) continue
  aliases.push(alias)
  const clicks = Number(blocks[i].match(/^clicks:\s*(\d+)/m)?.[1] ?? 0)
  const n = cueCount.get(use[1])
  if (n === undefined) fail(`slide "${alias}" uses scene "${use[1]}", which does not exist`)
  else if (clicks !== n - 1) fail(`slide "${alias}": clicks is ${clicks} but scene "${use[1]}" has ${n - 1} (cues - 1)`)
}
for (const d of new Set(aliases.filter((a, i) => aliases.indexOf(a) !== i))) fail(`duplicate routeAlias "${d}"`)
if (!errors) ok(`${sceneNames.length} scenes, ${aliases.length} slides, strings resolve, click budgets match`)

// ── 2. metrics ─────────────────────────────────────────────────────────────
console.log('\nmetrics (data/metrics.yml)')
const e0 = errors
type Entry = { value?: unknown; display?: string; status?: string; kind?: string; source?: string }
const metrics = (parse(read('data/metrics.yml')) ?? {}) as Record<string, Entry>
const pending: string[] = []
for (const [k, e] of Object.entries(metrics)) {
  if (!e.kind || !(METRIC_KINDS as readonly string[]).includes(e.kind)) fail(`${k}: kind must be one of ${METRIC_KINDS.join(', ')}`)
  if (!e.source) { fail(`${k}: no source`); continue }
  const isPending = e.status === 'pending' || e.value === undefined || e.value === null
  if (isPending) { pending.push(k); continue }
  const path = e.source.split(' ')[0]
  if (!existsSync(join(REPO, path))) fail(`${k}: source ${path} does not exist`)
}
const inFamily = (k: string) => metricFamilies.some((p) => p && k.startsWith(p))
for (const k of usedMetrics) if (!metrics[k]) fail(`a scene reads M('${k}') but data/metrics.yml has no such key`)
for (const k of Object.keys(metrics)) if (!usedMetrics.has(k) && !inFamily(k)) warn(`metric ${k} is defined but no scene reads it`)
if (errors === e0) ok(`${Object.keys(metrics).length} metrics, each with a kind and an existing source`)
if (pending.length) {
  console.log(`\n  ${pending.length} pending metric(s), shown as "pending" on screen:`)
  for (const k of pending) console.log(`    - ${k}  (${metrics[k].source})`)
  if (strict) fail(`--strict: ${pending.length} metric(s) still pending; fill data/metrics.yml before the final export`)
}

// ── 3. tokens: CSS and canvas agree ───────────────────────────────────────
console.log('\ntokens')
const css = read('styles/tokens.css')
const cssVar = (n: string) => css.match(new RegExp(`--${n}:\\s*(#[0-9A-Fa-f]{6})`))?.[1]?.toUpperCase()
const MAP: Record<string, string> = {
  bg: 'ink', bg2: 'ink-2', rail: 'rail', faint: 'faint', paper: 'paper', dim: 'dim', mute: 'mute', inkDim: 'ink-dim', inkMute: 'ink-mute',
  blue: 'blue', blueText: 'blue-text', blueDeep: 'blue-deep', yellow: 'yellow', yellowDeep: 'yellow-deep',
  red: 'red', redText: 'red-text', redDeep: 'red-deep',
}
const e1 = errors
for (const [k, v] of Object.entries(C)) {
  const n = MAP[k]
  if (!n) fail(`C.${k} has no CSS token mapping in check-content.ts`)
  else if (cssVar(n) !== v.toUpperCase()) fail(`C.${k} is ${v} but --${n} is ${cssVar(n) ?? 'missing'}`)
}
if (errors === e1) ok(`${Object.keys(C).length} colours identical in styles/tokens.css and lib/scene/kit.ts`)

// ── 4. contrast ────────────────────────────────────────────────────────────
console.log('\ncontrast (WCAG 2.2)')
const e2 = errors
for (const p of TEXT_PAIRS) {
  const r = ratio(C[p.fg], C[p.bg])
  if (r < p.min) fail(`${p.fg} on ${p.bg} is ${r.toFixed(2)}:1, needs ${p.min}:1 (${p.use})`)
}
if (errors === e2) ok(`${TEXT_PAIRS.length} text pairs meet their ratio (4.5:1 body, 3:1 large only)`)

// ── 5. narration script ────────────────────────────────────────────────────
console.log('\nnarration (script.md, 150 words per minute)')
const WPM = 150
const VIDEO_LIMIT_S = 180
const MONOLOGUE = 'docs/demo/video-monologue.md'
/** the video documents outside slides/, held to the same writing and naming rules */
const DEMO_DOCS = ['../docs/demo/video-plan.md', '../docs/demo/video-monologue.md', '../docs/demo/practice-cases.md']
const script = existsSync(join(ROOT, 'script.md')) ? read('script.md') : ''
if (!script) fail('script.md is missing')
const range = script.match(/<!--\s*total-target:\s*(\d+)-(\d+)\s*-->/)
const sections = script.split(/^##\s+/m).slice(1).map((p) => {
  const [head, ...body] = p.split('\n')
  const text = body.join('\n').replace(/<!--[\s\S]*?-->/g, '').split('\n')
    .filter((l) => !/^\s*(#|\||>|```)/.test(l)).join(' ').replace(/\[[^\]]*\]/g, ' ').replace(/[*_`]/g, '')
  const words = text.split(/\s+/).filter((w) => /[A-Za-z0-9]/.test(w)).length
  return { alias: head.trim().split(/\s/)[0], words }
})
for (const a of aliases) if (!sections.some((s) => s.alias === a)) fail(`script.md has no "## ${a}" section`)
let total = 0
for (const s of sections) {
  total += s.words / WPM * 60
  console.log(`  ${s.alias.padEnd(18)} ${String(s.words).padStart(4)} words  ${(s.words / WPM * 60).toFixed(0).padStart(4)} s`)
}
const fmt = (sec: number) => `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, '0')}`
console.log(`  ${'total'.padEnd(18)} ${fmt(total)} spoken`)
if (!range) fail('script.md needs a "<!-- total-target: MIN-MAX -->" comment (seconds)')
else if (total < Number(range[1]) || total > Number(range[2])) fail(`spoken total ${fmt(total)} is outside the target ${fmt(Number(range[1]))} to ${fmt(Number(range[2]))}`)
else ok(`spoken total ${fmt(total)} is inside ${fmt(Number(range[1]))} to ${fmt(Number(range[2]))}`)
// the organizers' hard limit: the whole video, demo footage included, is at most 3:00
if (total > VIDEO_LIMIT_S) fail(`spoken total ${fmt(total)} exceeds the organizers' ${fmt(VIDEO_LIMIT_S)} video limit at ${WPM} words per minute`)
else ok(`spoken total ${fmt(total)} fits the ${fmt(VIDEO_LIMIT_S)} video limit`)
checkMonologue(script)

/** script.md and the team monologue say the same words, by the same speakers, with true word counts. */
function checkMonologue(text: string) {
  const team = Object.keys(strings.close ?? {}).filter((k) => /^m\d+$/.test(k)).map((k) => String(strings.close[k]))
  const path = join(REPO, MONOLOGUE)
  if (!existsSync(path)) return fail(`${MONOLOGUE} is missing`)
  const md = readFileSync(path, 'utf8')
  const a = scriptWords(text, team)
  const b = monologueWords(md, team)
  const unassigned = a.filter((w) => !w.speaker).length
  if (unassigned) fail(`script.md has ${unassigned} spoken word(s) before any [speaker] tag`)
  const diff = firstDifference(a, b)
  if (diff) fail(`script.md and ${MONOLOGUE} differ at ${diff}`)
  else ok(`script.md and ${MONOLOGUE} say the same ${a.length} words`)
  const counts = countBySpeaker(a)
  const table = monologueTable(md, team)
  for (const name of team) {
    const n = counts.get(name) ?? 0
    console.log(`  ${name.padEnd(18)} ${String(n).padStart(4)} words  ${(n / WPM * 60).toFixed(0).padStart(4)} s`)
    if (table.get(name) !== n) fail(`${MONOLOGUE}: the word-count table says ${table.get(name) ?? 'nothing'} for ${name}, the script has ${n}`)
  }
}

// ── 5b. the six main slides, and the PDF that holds only them ─────────────
console.log('\nsubmission PDF')
const mainSlides = aliases.filter((a) => !a.startsWith('appendix'))
const firstAppendix = aliases.findIndex((a) => a.startsWith('appendix'))
if (mainSlides.length < 4 || mainSlides.length > 6) fail(`${mainSlides.length} main slides; the organizers allow 4 to 6`)
if (firstAppendix !== -1 && firstAppendix !== mainSlides.length) fail('appendix slides must come after every main slide')
const pkg = JSON.parse(read('package.json')) as { scripts: Record<string, string> }
const rangeOf = (s?: string) => s?.match(/--range\s+(\S+)/)?.[1]
if (rangeOf(pkg.scripts.export) !== `1-${mainSlides.length}`) fail(`package.json "export" must use --range 1-${mainSlides.length} (the main slides only)`)
else if (firstAppendix !== -1 && rangeOf(pkg.scripts['export:appendix']) !== `${firstAppendix + 1}-${aliases.length}`) fail(`package.json "export:appendix" must use --range ${firstAppendix + 1}-${aliases.length}`)
else ok(`${mainSlides.length} main slides in the submission PDF (export --range 1-${mainSlides.length}); the appendix exports apart`)

// ── 6. writing ─────────────────────────────────────────────────────────────
console.log('\nwriting')
const prose = ['slides.md', 'locales/en.yml', 'data/metrics.yml', 'script.md', 'VIDEO.md', 'README.md', 'lib/metric-kinds.ts', ...DEMO_DOCS]
let dashes = 0
for (const f of prose.filter((p) => existsSync(join(ROOT, p)))) {
  read(f).split('\n').forEach((line, i) => {
    if (line.includes('—')) { fail(`${f}:${i + 1} has an em dash`); dashes++ }
  })
}
if (!dashes) ok(`no em dashes in ${prose.length} prose files`)

// ── 7. naming: one spelling for the product, team, systems, workflows, metrics
console.log('\nnaming')
const e3 = errors
// Spellings that drifted from docs/evaluation, the app, or the README. The
// right-hand side is the canonical form; README.md explains the rule.
const BANNED: [RegExp, string][] = [
  [/\bJulian\b/, 'Julián (with the accent, as in the README team section)'],
  [/\bBank agent\b|\bBankAgent\b|\bbank-agent app\b/, 'Bank Agent (the name in the app header, apps/web locale app.name)'],
  [/(?<!La )\bBrasil del 70\b/, 'La Brasil del 70'],
  [/\bunneeded\b/i, 'unnecessary transfers'],
  [/\b(missed|unnecessary) escalations?\b/i, 'missed or unnecessary transfers (docs/evaluation)'],
  [/\b(keyword|rule) menu\b|\bmenu bot\b/i, 'the menu and rules bot (B0)'],
  [/\bnaive agent\b/i, 'the naive LLM agent (B1)'],
  [/\bsafe (automatic|resolution rate)\b|\bautomated safe resolution\b/i, 'safe automated resolution'],
  [/\bfirst-contact resolution\b/i, 'first contact resolution'],
  [/\baccounts and payments\b/i, 'account inquiry (the workflow name in docs/evaluation)'],
  [/\blevel [0-4]\b/i, 'L0 to L4 (docs/operations/degradation.md)'],
]
const named = ['slides.md', 'locales/en.yml', 'script.md', 'VIDEO.md', 'README.md', ...DEMO_DOCS]
for (const f of named.filter((p) => existsSync(join(ROOT, p)))) {
  read(f).split('\n').forEach((line, i) => {
    for (const [re, want] of BANNED) if (re.test(line)) fail(`${f}:${i + 1} "${line.match(re)?.[0]}": write ${want}`)
  })
}
// the team: each name on the close slide appears verbatim in the narration and the repository README
const team = strings.close ?? {}
const readme = existsSync(join(REPO, 'README.md')) ? readFileSync(join(REPO, 'README.md'), 'utf8') : ''
const members = Object.keys(team).filter((k) => /^m\d+$/.test(k)).map((k) => String(team[k]))
for (const name of members) {
  if (!script.includes(name)) fail(`team member "${name}" (close slide) is not named in script.md`)
  if (!readme.includes(`| ${name} |`)) fail(`team member "${name}" (close slide) is not in the README team table`)
}
// placeholders: allowed while drafting, never in the submission build
const PLACEHOLDER = /\[(confirm|placeholder)[^\]]*\]|\bTBD\b|\bTODO\b/i
for (const f of ['locales/en.yml', 'script.md']) {
  read(f).split('\n').forEach((line, i) => {
    if (!PLACEHOLDER.test(line)) return
    if (strict) fail(`${f}:${i + 1} still holds a placeholder: ${line.trim()}`)
    else warn(`${f}:${i + 1} holds a placeholder (fails under --strict): ${line.trim()}`)
  })
}
if (errors === e3) ok(`${BANNED.length} known variant spellings absent; ${members.length} team names match script.md and the README`)

// ── 8. intervals and fractions agree with their values ───────────────────
console.log('\nintervals and fractions')
const e4 = errors
type Rich = Entry & { lo?: number; hi?: number; of?: number }
for (const [k, raw] of Object.entries(metrics)) {
  const e = raw as Rich
  if (typeof e.value !== 'number') continue
  const frac = e.display?.match(/^(\d+)\/(\d+)$/)
  if (frac && e.of !== undefined && (Number(frac[1]) !== e.value || Number(frac[2]) !== e.of)) fail(`${k}: display ${e.display} does not match ${e.value} of ${e.of}`)
  if (frac && e.of === undefined && Math.abs((Number(frac[1]) / Number(frac[2])) * 100 - e.value) > 0.1) fail(`${k}: display ${e.display} does not match value ${e.value}`)
  if (e.of !== undefined && e.value > e.of) fail(`${k}: value ${e.value} exceeds its denominator ${e.of}`)
  if (e.lo !== undefined || e.hi !== undefined) {
    const rate = e.of ? (e.value / e.of) * 100 : e.value
    if (e.lo === undefined || e.hi === undefined || e.lo > rate + 0.5 || e.hi < rate - 0.5) fail(`${k}: interval ${e.lo} to ${e.hi} does not contain ${rate.toFixed(1)}`)
  }
}
if (errors === e4) ok('every interval contains its estimate; every fraction matches its value')

console.log('')
if (errors) {
  console.error(`FAIL ${errors} error(s), ${warnings} warning(s)\n`)
  process.exit(1)
}
console.log(`ok content is consistent${warnings ? ` (${warnings} warning(s))` : ''}${pending.length ? `, ${pending.length} metric(s) pending` : ''}\n`)

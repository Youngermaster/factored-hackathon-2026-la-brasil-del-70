/**
 * Split the exported video deck into its build-up PDF and the appendix PDF, and
 * check the submission PDF.
 *
 * The organizers allow 4 to 6 slides. The video deck (slides.md) replaces its
 * content between clicks, so no single frame of it carries a whole slide; the
 * submission is therefore a separate static entry, pitch.md, with one still
 * frame per slide (scenes/pitch*.ts), exported by `pnpm export:pitch` straight
 * to export/la-brasil-del-70-pitch.pdf. This script fails unless that PDF has
 * exactly one page per pitch.md slide, and as many slides as the video deck
 * has main slides (the same story, in the same order).
 *
 * Slidev 52 ignores --range in hash router mode (the print page reads the range
 * from the hash route, the exporter puts it in the search part), so the video
 * deck is rendered once, one page per click, and cut here: slides whose
 * routeAlias starts with "appendix" go to the appendix PDF, every other slide
 * to the steps PDF. Page counts come from the `clicks:` budgets in slides.md,
 * and the script fails when the rendered page count does not match them.
 *
 * pdf-lib is the copy Slidev's own exporter uses (a dependency of @slidev/cli),
 * resolved from there so the deck gains no dependency of its own.
 *
 *   node scripts/split-pdf.mjs <full.pdf> <pitch.pdf>
 *   -> export/la-brasil-del-70-pitch-steps.pdf    one page per build-up step of the main slides
 *      export/la-brasil-del-70-appendix.pdf       the appendix, one page per step
 *   checks <pitch.pdf>                            one page per pitch.md slide (the submission)
 */
import { createRequire } from 'node:module'
import { readFileSync, rmSync, writeFileSync } from 'node:fs'
import { parse } from 'yaml'

const require = createRequire(createRequire(import.meta.url).resolve('@slidev/cli/package.json'))
const { PDFDocument } = require('pdf-lib')

const [full, pitch] = process.argv.slice(2)
if (!full || !pitch) {
  console.error('usage: node scripts/split-pdf.mjs <full.pdf> <pitch.pdf>')
  process.exit(1)
}

// the deck's slides in order, with their pages (one per click, plus the arrival)
const slides = []
for (const fm of readFileSync('slides.md', 'utf8').split(/^---$/m)) {
  if (!/^routeAlias:/m.test(fm)) continue
  const meta = parse(fm) ?? {}
  slides.push({ alias: String(meta.routeAlias), pages: Number(meta.clicks ?? 0) + 1 })
}
const main = slides.filter((s) => !s.alias.startsWith('appendix'))
const appendix = slides.filter((s) => s.alias.startsWith('appendix'))
if (slides.slice(0, main.length).some((s) => s.alias.startsWith('appendix'))) {
  console.error('FAIL appendix slides must come after every main slide in slides.md')
  process.exit(1)
}
const mainPages = main.reduce((a, s) => a + s.pages, 0)
const appendixPages = appendix.reduce((a, s) => a + s.pages, 0)

const src = await PDFDocument.load(readFileSync(full))
const total = src.getPageCount()
if (total !== mainPages + appendixPages) {
  console.error(`FAIL the export has ${total} pages; slides.md expects ${mainPages + appendixPages} (${mainPages} main, ${appendixPages} appendix)`)
  process.exit(1)
}

async function write(path, from, count) {
  const out = await PDFDocument.create()
  out.setTitle(src.getTitle() ?? 'Bank Agent')
  out.setAuthor('La Brasil del 70')
  const pages = await out.copyPages(src, Array.from({ length: count }, (_, i) => from + i))
  for (const p of pages) out.addPage(p)
  writeFileSync(path, await out.save())
  console.log(`  ${path}: ${count} pages`)
}

// The submission: pitch.md, one still frame per slide, as many slides as the
// video deck has main slides.
const pitchSlides = readFileSync('pitch.md', 'utf8').split(/^---$/m).filter((b) => /<Scene\s+name="/.test(b)).length
const pitchPages = (await PDFDocument.load(readFileSync(pitch))).getPageCount()
if (pitchSlides < 4 || pitchSlides > 6) {
  console.error(`FAIL pitch.md has ${pitchSlides} slides; the organizers allow 4 to 6`)
  process.exit(1)
}
if (pitchSlides !== main.length) {
  console.error(`FAIL pitch.md has ${pitchSlides} slides; the video deck has ${main.length} main slides`)
  process.exit(1)
}
if (pitchPages !== pitchSlides) {
  console.error(`FAIL ${pitch} has ${pitchPages} pages; pitch.md has ${pitchSlides} slides, one page each`)
  process.exit(1)
}
console.log(`  ${pitch}: ${pitchPages} pages, one full slide per page`)

await write('export/la-brasil-del-70-pitch-steps.pdf', 0, mainPages)
if (appendixPages) await write('export/la-brasil-del-70-appendix.pdf', mainPages, appendixPages)
rmSync(full)
console.log(`ok ${pitchSlides} static slides in the submission PDF, ${mainPages} build-up steps of the video deck in the steps PDF, ${appendix.length} appendix slides apart`)

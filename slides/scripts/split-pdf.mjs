/**
 * Split the exported deck into the submission PDF and the appendix PDF.
 *
 * The organizers allow 4 to 6 slides, so the submission PDF must hold only the
 * main slides. Slidev 52 ignores --range in hash router mode (the print page
 * reads the range from the hash route, the exporter puts it in the search
 * part), so `pnpm export` renders the whole deck once, one page per click, and
 * this script cuts it: slides whose routeAlias starts with "appendix" go to the
 * appendix PDF, every other slide to the pitch PDF. Page counts come from the
 * `clicks:` budgets in slides.md, and the script fails when the rendered page
 * count does not match them.
 *
 * pdf-lib is the copy Slidev's own exporter uses (a dependency of @slidev/cli),
 * resolved from there so the deck gains no dependency of its own.
 *
 *   node scripts/split-pdf.mjs <full.pdf>
 *   -> export/la-brasil-del-70-pitch.pdf, export/la-brasil-del-70-appendix.pdf
 */
import { createRequire } from 'node:module'
import { readFileSync, rmSync, writeFileSync } from 'node:fs'
import { parse } from 'yaml'

const require = createRequire(createRequire(import.meta.url).resolve('@slidev/cli/package.json'))
const { PDFDocument } = require('pdf-lib')

const full = process.argv[2]
if (!full) {
  console.error('usage: node scripts/split-pdf.mjs <full.pdf>')
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

await write('export/la-brasil-del-70-pitch.pdf', 0, mainPages)
if (appendixPages) await write('export/la-brasil-del-70-appendix.pdf', mainPages, appendixPages)
rmSync(full)
console.log(`ok ${main.length} main slides in the submission PDF, ${appendix.length} appendix slides apart`)

/**
 * Split the exported deck into the submission PDF, its build-up version, and
 * the appendix PDF.
 *
 * The organizers allow 4 to 6 slides, so the submission PDF holds exactly one
 * page per main slide. Slidev 52 ignores --range in hash router mode (the print
 * page reads the range from the hash route, the exporter puts it in the search
 * part), so `pnpm export` renders the whole deck once, one page per click, and
 * this script cuts it: slides whose routeAlias starts with "appendix" go to the
 * appendix PDF, every other slide to the pitch PDFs. Page counts come from the
 * `clicks:` budgets in slides.md, and the script fails when the rendered page
 * count does not match them.
 *
 * The scenes replace their content between clicks, so no single frame carries a
 * whole slide. The submission PDF therefore draws each main slide's frames
 * (arrival, then every click, in reading order) as a grid on one 16:9 page; the
 * frames are embedded, not rasterized again, so a reader can zoom into any of
 * them. The build-up PDF keeps one full page per frame.
 *
 * pdf-lib is the copy Slidev's own exporter uses (a dependency of @slidev/cli),
 * resolved from there so the deck gains no dependency of its own.
 *
 *   node scripts/split-pdf.mjs <full.pdf>
 *   -> export/la-brasil-del-70-pitch.pdf          one page per main slide (the submission)
 *      export/la-brasil-del-70-pitch-steps.pdf    one page per build-up step of the main slides
 *      export/la-brasil-del-70-appendix.pdf       the appendix, one page per step
 */
import { createRequire } from 'node:module'
import { readFileSync, rmSync, writeFileSync } from 'node:fs'
import { parse } from 'yaml'

const require = createRequire(createRequire(import.meta.url).resolve('@slidev/cli/package.json'))
const { PDFDocument, rgb } = require('pdf-lib')

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

// The grid for n frames: two columns up to four frames, then three.
function grid(n) {
  const cols = n <= 4 ? 2 : 3
  return { cols, rows: Math.ceil(n / cols) }
}

// One 16:9 page per main slide, its frames tiled left to right, top to bottom,
// on the deck's own background so the seams between frames stay quiet.
async function writeSlides(path) {
  const out = await PDFDocument.create()
  out.setTitle(src.getTitle() ?? 'Bank Agent')
  out.setAuthor('La Brasil del 70')
  const { width, height } = src.getPage(0).getSize()
  const gap = width / 160
  let from = 0
  for (const s of main) {
    const frames = await out.embedPages(Array.from({ length: s.pages }, (_, i) => src.getPage(from + i)))
    from += s.pages
    const page = out.addPage([width, height])
    page.drawRectangle({ x: 0, y: 0, width, height, color: rgb(0.04, 0.04, 0.04) })
    const { cols, rows } = grid(frames.length)
    const cellW = (width - gap * (cols + 1)) / cols
    const cellH = (height - gap * (rows + 1)) / rows
    const scale = Math.min(cellW / width, cellH / height)
    const w = width * scale
    const h = height * scale
    const top = (height - (rows * h + (rows - 1) * gap)) / 2
    const left = (width - (cols * w + (cols - 1) * gap)) / 2
    frames.forEach((frame, i) => {
      const col = i % cols
      const row = Math.floor(i / cols)
      page.drawPage(frame, { x: left + col * (w + gap), y: height - top - (row + 1) * h - row * gap, width: w, height: h })
    })
  }
  writeFileSync(path, await out.save())
  const written = (await PDFDocument.load(readFileSync(path))).getPageCount()
  if (written !== main.length) {
    console.error(`FAIL ${path} has ${written} pages; the deck has ${main.length} main slides`)
    process.exit(1)
  }
  console.log(`  ${path}: ${written} pages, one per main slide`)
}

await writeSlides('export/la-brasil-del-70-pitch.pdf')
await write('export/la-brasil-del-70-pitch-steps.pdf', 0, mainPages)
if (appendixPages) await write('export/la-brasil-del-70-appendix.pdf', mainPages, appendixPages)
rmSync(full)
console.log(`ok ${main.length} main slides in the submission PDF (${mainPages} build-up steps in the steps PDF), ${appendix.length} appendix slides apart`)

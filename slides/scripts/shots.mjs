/**
 * Screenshot every slide at every click step from the running dev server,
 * through Slidev itself (not the lab), so the seams, the layout and the
 * finished frame of each cue are what the recording and the PDF will show.
 *
 *   node scripts/shots.mjs [--port 3131] [--last-only]
 *
 * Output: .shots/deck/NN-<alias>-cK.png
 */
import { chromium } from 'playwright-chromium'
import { mkdir, rm } from 'node:fs/promises'
import { readFileSync } from 'node:fs'
import { parse } from 'yaml'

const i = process.argv.indexOf('--port')
const port = i > -1 ? process.argv[i + 1] : '3131'
const lastOnly = process.argv.includes('--last-only')
const outDir = '.shots/deck'

// Click budgets come from the deck itself, so this never drifts from slides.md.
// The headmatter doubles as slide 1's frontmatter.
const blocks = readFileSync('slides.md', 'utf8').split(/^---$/m)
const slides = []
for (const fm of blocks) {
  if (!/^routeAlias:/m.test(fm)) continue
  let meta = {}
  try { meta = parse(fm) ?? {} } catch { meta = {} }
  if (meta.routeAlias) slides.push({ alias: meta.routeAlias, clicks: meta.clicks ?? 0 })
}

await rm(outDir, { recursive: true, force: true })
await mkdir(outDir, { recursive: true })
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 })

let shot = 0
for (let n = 1; n <= slides.length; n++) {
  const s = slides[n - 1]
  const steps = lastOnly ? [s.clicks] : [...Array(s.clicks + 1).keys()]
  for (const c of steps) {
    await page.goto(`http://localhost:${port}/#/${n}?clicks=${c}&scene_snap`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(900)
    await page.screenshot({ path: `${outDir}/${String(n).padStart(2, '0')}-${s.alias}-c${c}.png` })
    shot++
  }
}
await browser.close()
console.log(`${shot} screenshots in ${outDir}/ (${slides.length} slides)`)

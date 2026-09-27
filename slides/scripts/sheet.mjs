/**
 * Contact sheet of a canvas scene, from the running dev server.
 *
 *   node scripts/sheet.mjs <scene> [--times 0,1.5,3] [--cols 4] [--port 3131] [--out file.png]
 *
 * Without --times it renders every cue and every segment midpoint. Look at the
 * sheet before calling a scene done: overlaps and ghosts are invisible in code.
 */
import { chromium } from 'playwright-chromium'
import { mkdir } from 'node:fs/promises'

const scene = process.argv[2]
if (!scene) {
  console.error('usage: node scripts/sheet.mjs <scene> [--times 0,1,2] [--cols 4]')
  process.exit(1)
}
const arg = (n, d) => {
  const i = process.argv.indexOf(`--${n}`)
  return i > -1 ? process.argv[i + 1] : d
}
const port = arg('port', '3131')
const cols = arg('cols', '4')
const times = arg('times')
const v = arg('v')
const out = arg('out', `.shots/scenes/${scene}${v ? `-${v}` : ''}.png`)

const q = new URLSearchParams({ scene, cols, ...(v ? { v } : {}), ...(times ? { times } : { sheet: '1' }) })
await mkdir(out.split('/').slice(0, -1).join('/') || '.', { recursive: true })
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 })
const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))
await page.goto(`http://localhost:${port}/#/lab?${q}`)
await page.waitForFunction(() => window.__labReady === true, null, { timeout: 30000 })
// The lab scrolls inside a 100vh box; grow the viewport so every cell paints.
const tall = await page.evaluate(() => document.querySelector('.lab__sheet')?.scrollHeight ?? 900)
await page.setViewportSize({ width: 1600, height: Math.ceil(tall) + 40 })
await page.evaluate(() => window.dispatchEvent(new Event('hashchange')))
await page.waitForTimeout(500)
await page.locator('.lab__sheet').screenshot({ path: out })
await browser.close()
if (errors.length) console.error(`console errors:\n  ${errors.join('\n  ')}`)
console.log(out)

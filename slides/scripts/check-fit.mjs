/**
 * Fit check for canvas scenes.
 *
 * The slides are canvases, so a DOM overflow check says nothing. Instead the
 * lab page renders every scene at every cue with the kit's text probe on and
 * reports text that leaves the safe area or lands on other text. Those are the
 * failures that survive code review and show up in the recording.
 *
 * Requires the dev server (pnpm dev, port 3131).
 *   node scripts/check-fit.mjs [--port 3131]
 */
import { chromium } from 'playwright-chromium'

const i = process.argv.indexOf('--port')
const port = i > -1 ? process.argv[i + 1] : '3131'

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
await page.goto(`http://localhost:${port}/#/lab?fit=1`)
await page.waitForFunction(() => window.__labReady === true, null, { timeout: 60000 })
const report = await page.evaluate(() => window.__fitReport ?? null)
await browser.close()

if (report === null) {
  console.error('\nFAIL the lab page did not produce a fit report\n')
  process.exit(1)
}
if (report.length) {
  console.error(`\nFAIL ${report.length} fit problem(s):\n`)
  for (const line of report) console.error(`  ${line}`)
  console.error('')
  process.exit(1)
}
console.log('\nok every scene fits the safe area at every cue, with no overlapping text\n')

// Fonts are npm packages, not a CDN stylesheet: Slidev's `fonts:` headmatter
// emits a fonts.googleapis.com link the browser resolves at runtime, so the
// deck sets `provider: none` in slides.md and imports the woff2 files here.
// That keeps the recording machine and the PDF export fully offline.
import '@fontsource-variable/instrument-sans'
import '@fontsource-variable/geist-mono'
import '@fontsource-variable/unbounded'

import './tokens.css'
import './base.css'
import './motion.css'

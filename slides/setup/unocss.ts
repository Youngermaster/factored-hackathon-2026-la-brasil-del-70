import { defineUnoSetup } from '@slidev/types'

/**
 * Slidev's client defines `bg-main: 'bg-white dark:bg-[#121212]'` and puts it
 * on <body> and its own chrome. #121212 is not our ground, so during a seam
 * that lighter grey would flash through. Redefining the shortcut fixes the
 * deck and Slidev's chrome in one place. Values mirror styles/tokens.css.
 */
export default defineUnoSetup(() => ({
  shortcuts: {
    'bg-main': 'bg-[#070707]',
    'text-main': 'text-[#E6E6E4]',
  },
}))

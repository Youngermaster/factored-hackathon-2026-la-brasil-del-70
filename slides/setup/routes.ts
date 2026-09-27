import { defineRoutesSetup } from '@slidev/types'

/**
 * The scene workbench at /#/lab: scrub any canvas scene, jump between cues,
 * or render a contact sheet. A static segment outranks Slidev's `/:no` route
 * in Vue Router's ranking, so `/lab` wins without being prepended.
 */
export default defineRoutesSetup((routes) => [
  ...routes,
  {
    path: '/lab',
    name: 'lab',
    component: () => import('../pages/lab.vue'),
  },
])

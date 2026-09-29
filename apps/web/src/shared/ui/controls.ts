/** Shared look of text controls: the strong border meets 3:1 on every surface (see contrast.ts). */
export const controlClasses =
  'w-full rounded-control border border-border-strong bg-surface px-3 text-body text-fg ' +
  'placeholder:text-fg-muted transition-[border-color] duration-150 ' +
  'hover:border-fg focus-visible:border-fg disabled:cursor-not-allowed disabled:opacity-60 ' +
  'aria-invalid:border-risk-text';

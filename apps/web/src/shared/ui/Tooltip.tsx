import { Tooltip as RadixTooltip } from 'radix-ui';
import type { ReactElement, ReactNode } from 'react';

export const TooltipProvider = RadixTooltip.Provider;

/**
 * A short visual label for an already-named control (for example an <IconButton>). It supplements the accessible
 * name; it never carries information that is not available otherwise.
 */
export function Tooltip({
  content,
  children,
}: {
  readonly content: ReactNode;
  readonly children: ReactElement;
}) {
  return (
    <RadixTooltip.Root>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          sideOffset={6}
          className="z-50 rounded-control bg-action px-2.5 py-1.5 text-caption font-medium text-action-fg animate-overlay-in"
        >
          {content}
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
}

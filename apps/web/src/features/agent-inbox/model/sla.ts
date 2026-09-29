import type { Schema } from '@/shared/api';

/** Priority order for sorting: the most urgent first. */
export const PRIORITY_RANK: Record<Schema<'Priority'>, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

/** Whether the SLA has passed at `now`; the countdown text says so in words, color only repeats it. */
export function isOverdue(slaDue: string, now: Date): boolean {
  return new Date(slaDue).getTime() <= now.getTime();
}

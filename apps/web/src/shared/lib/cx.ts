/** Joins class names, skipping false, null, and undefined, so conditional classes read plainly. */
export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter((part): part is string => typeof part === 'string' && part !== '').join(' ');
}

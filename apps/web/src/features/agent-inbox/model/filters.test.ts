import { describe, expect, it } from 'vitest';

import { INBOX_PAGE_SIZE, toQuery } from './filters';

describe('the inbox query', () => {
  it('asks for the API maximum so a new handoff is never cut off the soonest-SLA-first page', () => {
    expect(INBOX_PAGE_SIZE).toBe(200);
    expect(toQuery({}, new Date('2026-10-06T04:00:00Z'))).toEqual({ limit: 200 });
  });

  it('keeps the filters next to the page size', () => {
    const query = toQuery({ language: 'pt', priority: 'high' }, new Date('2026-10-06T04:00:00Z'));
    expect(query).toEqual({ limit: 200, language: ['pt'], priority: ['high'] });
  });
});

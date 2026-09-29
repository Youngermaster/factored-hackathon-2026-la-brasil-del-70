import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router';

/**
 * After a client-side navigation, moves focus to the main region so keyboard and screen reader users start at the
 * new content instead of wherever the old page left them. The first render keeps the browser's default.
 */
export function useRouteFocus<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const { pathname } = useLocation();
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    ref.current?.focus();
  }, [pathname]);
  return ref;
}

import { useEffect, useState } from 'react';

/** Whole seconds left until `deadline` (an ISO instant), ticking once a second; 0 once it has passed. */
export function useSecondsUntil(deadline: string | null): number {
  const compute = () =>
    deadline === null
      ? 0
      : Math.max(0, Math.ceil((new Date(deadline).getTime() - Date.now()) / 1000));
  const [seconds, setSeconds] = useState(compute);

  useEffect(() => {
    if (deadline === null) {
      return undefined;
    }
    const tick = () => {
      setSeconds(Math.max(0, Math.ceil((new Date(deadline).getTime() - Date.now()) / 1000)));
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => {
      window.clearInterval(timer);
    };
  }, [deadline]);

  return seconds;
}

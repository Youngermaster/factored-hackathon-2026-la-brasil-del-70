import { RequireSession } from '@/features/auth';
import { SupervisionOverview } from '@/features/supervision';

/** Model and operations supervision for evaluators, who play the supervisor in this product. */
export function SupervisionPage() {
  return (
    <RequireSession roles={['evaluator']}>
      <SupervisionOverview />
    </RequireSession>
  );
}

import { AdminDashboard } from '@/features/admin-dashboard';
import { RequireSession } from '@/features/auth';

/** Administrative analytics over published, versioned evaluation results. */
export function AdminDashboardPage() {
  return (
    <RequireSession roles={['evaluator']}>
      <AdminDashboard />
    </RequireSession>
  );
}

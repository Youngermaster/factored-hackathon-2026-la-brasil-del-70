/** The evaluation view: published offline, simulated, or projected summaries, per workflow before the aggregate. */
export { EvaluationReport } from './ui/EvaluationReport';
export {
  useSummaries,
  type EvaluationSummary,
  type OutcomeMetrics,
  type SliceSummary,
} from './api/summaries';
export { groupRuns, systemCode } from './model/systems';
export { proportion, wilson, zeroEventUpperBound } from './model/stats';
export { RateCell } from './ui/MetricTable';
export { SystemLabel } from './ui/SystemLabel';

/** The auth feature's public surface: sign-in, the session, route guards, step-up, and sign-out. */
export { useSession, type SessionView } from './api/session';
export { createSessionLossChannel, type SessionLossChannel } from './model/session-loss';
export { homeFor, PERSONAS, type Persona, type PersonaId } from './model/personas';
export { useStepUp, type StepUpRequest } from './model/step-up-context';
export { expiredLoginPath } from './model/paths';
export { AuthProvider } from './ui/AuthProvider';
export { SessionNotice, type LoginReason } from './ui/ExpiredSessionNotice';
export { LoginFlow } from './ui/LoginFlow';
export { LogoutButton } from './ui/LogoutButton';
export { RequireSession } from './ui/RequireSession';
export { SessionStatus } from './ui/SessionStatus';
export * as StepUp from './ui/StepUp';

"""Lifetimes and limits for one-time codes and sessions (CLAUDE.md section 7). Fixed values, not settings."""

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class OtpPolicy:
    code_lifetime: timedelta = timedelta(minutes=5)
    max_attempts: int = 5
    lockout_cooldown: timedelta = timedelta(minutes=15)


@dataclass(frozen=True)
class SessionPolicy:
    idle_timeout: timedelta = timedelta(minutes=15)
    absolute_lifetime: timedelta = timedelta(minutes=60)
    step_up_window: timedelta = timedelta(minutes=5)


OTP_POLICY = OtpPolicy()
SESSION_POLICY = SessionPolicy()

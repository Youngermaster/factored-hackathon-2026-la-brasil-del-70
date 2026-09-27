"""``DemoOtpSender``: the only code delivery in the prototype.

With ``DEMO_MODE=true`` the code comes back in the receipt so the UI can show it with a clear demo label.
Otherwise the sender only emits a delivery event, which never carries the code or a destination. There is no
real SMS gateway: a production deployment replaces this adapter.
"""

from collections.abc import Callable, Mapping

import structlog

from bank_agent.domain.identity import OtpDeliveryReceipt, OtpDispatch

DeliveryEvent = Callable[[str, Mapping[str, str]], None]


def _log_event(name: str, fields: Mapping[str, str]) -> None:
    structlog.get_logger("bank_agent.identity").info(name, **fields)


class DemoOtpSender:
    """Implements ``OtpSender``."""

    def __init__(self, *, demo_mode: bool, emit: DeliveryEvent = _log_event) -> None:
        self._demo_mode = demo_mode
        self._emit = emit

    def _receipt(self, code: str) -> OtpDeliveryReceipt:
        if self._demo_mode:
            return OtpDeliveryReceipt(delivered=True, channel="demo", demo_code=code)
        return OtpDeliveryReceipt(delivered=True, channel="sms")

    async def send(self, dispatch: OtpDispatch) -> OtpDeliveryReceipt:
        self._emit(
            "otp_delivery_requested",
            {"challenge_id": dispatch.challenge_id, "purpose": dispatch.purpose.value, "channel": self._channel},
        )
        return self._receipt(dispatch.code)

    def decoy_receipt(self, challenge_id: str, code: str) -> OtpDeliveryReceipt:
        """The receipt for an identification that matched nobody: indistinguishable from a real one."""
        fields = {"challenge_id": challenge_id, "purpose": "login", "channel": self._channel}
        self._emit("otp_delivery_requested", fields)
        return self._receipt(code)

    @property
    def _channel(self) -> str:
        return "demo" if self._demo_mode else "sms"

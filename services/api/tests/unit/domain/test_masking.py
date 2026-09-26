import pytest
from pydantic import ValidationError

from bank_agent.domain.errors import InvalidMaskedNumberError
from bank_agent.domain.masking import MaskedNumber


@pytest.mark.parametrize(
    ("number", "last4"),
    [("4111111111111234", "1234"), ("4111 1111 1111 1234", "1234"), ("ACC-00-99a7", "99A7"), ("12345", "2345")],
)
def test_keeps_only_the_last_four_characters(number: str, last4: str) -> None:
    masked = MaskedNumber.from_full(number)
    assert masked.last4 == last4
    assert str(masked) == f"**** {last4}"


def test_never_exposes_the_full_number() -> None:
    masked = MaskedNumber.from_full("4111111111111234")
    for rendering in (str(masked), repr(masked), masked.model_dump_json()):
        assert "411111111111" not in rendering


@pytest.mark.parametrize("number", ["1234", "12-34", "", "ab"])
def test_rejects_numbers_too_short_to_mask(number: str) -> None:
    with pytest.raises(InvalidMaskedNumberError):
        MaskedNumber.from_full(number)


def test_rejects_a_direct_value_that_is_not_four_characters() -> None:
    with pytest.raises(ValidationError):
        MaskedNumber(last4="123456")

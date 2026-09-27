import pytest

from bank_agent.domain.locale import Country, Language, Locale
from bank_agent.domain.money import Currency


@pytest.mark.parametrize(
    ("name", "country"), [("Mexico", Country.MX), (" colombia ", Country.CO), ("Argentina", Country.AR)]
)
def test_maps_dataset_country_names(name: str, country: Country) -> None:
    assert Country.from_dataset_name(name) is country


def test_rejects_unknown_country_names() -> None:
    with pytest.raises(ValueError, match="unknown country"):
        Country.from_dataset_name("Brazil")


def test_country_defaults() -> None:
    assert Country.MX.default_currency is Currency.MXN
    assert Country.CO.default_currency is Currency.COP
    assert Country.AR.default_currency is Currency.ARS
    assert Country.AR.default_locale is Locale.ES_AR
    assert Country.CO.timezone_name == "America/Bogota"


@pytest.mark.parametrize(
    ("country", "language", "locale"),
    [
        (Country.MX, Language.ES, Locale.ES_MX),
        (Country.AR, Language.ES, Locale.ES_AR),
        (Country.CO, Language.PT, Locale.PT_BR),
        (Country.MX, Language.EN, Locale.EN_US),
    ],
)
def test_locale_for_customer(country: Country, language: Language, locale: Locale) -> None:
    assert Locale.for_customer(country, language) is locale
    assert locale.language is language

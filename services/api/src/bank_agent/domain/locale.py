"""Countries, languages, and locales.

``Country`` is the customer's jurisdiction (the bank operates in MX, CO, and AR). A transaction can happen
anywhere, so its location uses ``CountryCode`` instead. Time zones are IANA names as strings; the application
layer resolves them, so the domain never touches the time zone database.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import StringConstraints

from bank_agent.domain.money import Currency

CountryCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
"""An ISO 3166-1 alpha-2 code for where a transaction happened."""


class Language(StrEnum):
    ES = "es"
    PT = "pt"
    EN = "en"


class Country(StrEnum):
    MX = "MX"
    CO = "CO"
    AR = "AR"

    @classmethod
    def from_dataset_name(cls, name: str) -> "Country":
        """Map the dataset spelling (``Mexico``, ``Colombia``, ``Argentina``) to a country."""
        try:
            return _DATASET_NAMES[name.strip().casefold()]
        except KeyError:
            raise ValueError("unknown country name") from None

    @property
    def default_currency(self) -> Currency:
        return _CURRENCIES[self]

    @property
    def default_locale(self) -> "Locale":
        return _SPANISH_LOCALES[self]

    @property
    def timezone_name(self) -> str:
        return _TIMEZONES[self]


class Locale(StrEnum):
    ES_MX = "es-MX"
    ES_CO = "es-CO"
    ES_AR = "es-AR"
    PT_BR = "pt-BR"
    EN_US = "en-US"

    @property
    def language(self) -> Language:
        return Language(self.value.split("-", 1)[0])

    @classmethod
    def for_customer(cls, country: Country, language: Language) -> "Locale":
        """The locale for a customer's country and chosen language: Spanish follows the country's dialect."""
        if language is Language.ES:
            return _SPANISH_LOCALES[country]
        if language is Language.PT:
            return cls.PT_BR
        return cls.EN_US


_DATASET_NAMES = {"mexico": Country.MX, "méxico": Country.MX, "colombia": Country.CO, "argentina": Country.AR}
_CURRENCIES = {Country.MX: Currency.MXN, Country.CO: Currency.COP, Country.AR: Currency.ARS}
_SPANISH_LOCALES = {Country.MX: Locale.ES_MX, Country.CO: Locale.ES_CO, Country.AR: Locale.ES_AR}
_TIMEZONES = {
    Country.MX: "America/Mexico_City",
    Country.CO: "America/Bogota",
    Country.AR: "America/Argentina/Buenos_Aires",
}

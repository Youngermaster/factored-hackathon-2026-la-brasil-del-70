import re
from datetime import date

import pytest

from bank_data.sample import pseudonyms


def test_names_keep_the_number_of_parts_and_avoid_originals() -> None:
    value = pseudonyms.name("Samuel Andrés", "customers", "first_name", "CLI-1", {"Samuel Andrés"})
    again = pseudonyms.name("Samuel Andrés", "customers", "first_name", "CLI-1", {"Samuel Andrés"})
    assert value == again
    assert len(value.split()) == 2
    assert value != "Samuel Andrés"
    assert pseudonyms.name("Ana", "customers", "first_name", "CLI-2", set()) != value


def test_shaped_values_keep_length_pattern_and_optional_prefixes() -> None:
    document = pseudonyms.shaped("G8637940", "customers", "document_number", "CLI-1", {"G8637940"})
    assert re.fullmatch(r"[A-Z]\d{7}", document)
    assert document != "G8637940"
    policy = pseudonyms.shaped("POL-9988678", "products", "product_number", "PRD-1", set(), keep_letters=True)
    assert re.fullmatch(r"POL-\d{7}", policy)


def test_phones_keep_the_country_prefix_and_grouping() -> None:
    value = pseudonyms.phone("+57 315 564 6977", "customers", "mobile_phone", "CLI-1", {"+57 315 564 6977"})
    assert re.fullmatch(r"\+57 \d{3} \d{3} \d{4}", value)
    assert re.fullmatch(r"\d{3}-\d{4}", pseudonyms.phone("555-1234", "t", "phone", "k", set()))


def test_email_address_date_and_ip_pseudonyms() -> None:
    email = pseudonyms.email("Zoé Mara", "Núñez Ruiz", "customers", "CLI-1", set())
    assert re.fullmatch(r"zoe\.nunez\d{2}@example\.com", email)
    address = pseudonyms.address("customers", "CLI-1", set())
    assert re.fullmatch(r"(Calle|Avenida|Carrera|Pasaje|Boulevard) [A-Z][a-z]+ \d{1,3}, Barrio [A-Z][a-z]+", address)
    born = date(1990, 5, 17)
    shifted = pseudonyms.birth_date(born, "customers", "CLI-1", {born})
    assert shifted != born
    assert 1 <= abs((shifted - born).days) <= 365
    assert re.fullmatch(
        r"(192\.0\.2|198\.51\.100|203\.0\.113)\.\d{1,3}", pseudonyms.ip_address("digital_events", "E1", set())
    )


def test_draw_fails_when_every_candidate_is_avoided() -> None:
    with pytest.raises(ValueError, match="no pseudonym"):
        pseudonyms.shaped("7", "t", "c", "k", {str(digit) for digit in range(10)})

"""Tests for the expense tracker.

    pip install pytest && pytest -q

Every test here corresponds to something that was actually broken. That is the
point of writing them at all: a test that could never have failed tells you
nothing about the program.
"""

import csv

import pytest

from expense import CATEGORIES, Expense, InvalidExpense, parse_amount
from expense_tracker import append, normalise_category, read, summarise


# ── the bug that corrupted the file ──────────────────────────────────────────

def test_a_comma_in_the_name_survives_a_round_trip(tmp_path):
    """The original wrote rows with an f-string, so this destroyed the ledger.

    "Almoço, Lisboa" became a four-field row that split(",") could not read,
    and every later summary raised ValueError. One comma, permanent damage,
    no warning.
    """
    ledger = tmp_path / "expenses.csv"
    append(Expense(name="Almoço, Lisboa", category="Restaurants", amount=12.5), ledger)

    (lido,) = read(ledger)
    assert lido.name == "Almoço, Lisboa"
    assert lido.amount == 12.5
    assert lido.category == "Restaurants"


@pytest.mark.parametrize("nome", [
    'Café "do canto"',      # quotes
    "Livro; e caderno",     # semicolon
    "Multi\nlinha",         # a newline, which is the worst case
])
def test_awkward_names_survive_a_round_trip(tmp_path, nome):
    ledger = tmp_path / "expenses.csv"
    append(Expense(name=nome, category="Various", amount=1.0), ledger)
    (lido,) = read(ledger)
    assert lido.name == nome


# ── the bug a Portuguese user hits first ─────────────────────────────────────

@pytest.mark.parametrize("cru,esperado", [
    ("25.50", 25.50),
    ("25,50", 25.50),          # how it is written here — float() raises on this
    (" 25,50 ", 25.50),
    ("25,50 €", 25.50),
    ("1.234,56", 1234.56),     # Portuguese thousands separator
    ("1,234.56", 1234.56),     # English thousands separator
    ("7", 7.0),
])
def test_amounts_are_read_the_way_people_write_them(cru, esperado):
    assert parse_amount(cru) == pytest.approx(esperado)


@pytest.mark.parametrize("cru", ["", "abc", "-5", "0", "1,2,3"])
def test_bad_amounts_raise_something_a_human_can_read(cru):
    with pytest.raises(InvalidExpense):
        parse_amount(cru)


# ── the model refuses to hold nonsense ───────────────────────────────────────

def test_an_expense_needs_a_name():
    with pytest.raises(InvalidExpense):
        Expense(name="   ", category="Various", amount=1.0)


def test_an_expense_needs_a_known_category():
    with pytest.raises(InvalidExpense):
        Expense(name="x", category="Bitcoin", amount=1.0)


def test_an_expense_needs_a_positive_amount():
    with pytest.raises(InvalidExpense):
        Expense(name="x", category="Various", amount=0)


def test_an_expense_cannot_be_changed_after_it_exists():
    e = Expense(name="x", category="Various", amount=1.0)
    with pytest.raises(Exception):
        e.amount = 99  # type: ignore[misc]


def test_the_repr_uses_one_currency():
    """It used to print a dollar sign while the summary printed euros."""
    r = repr(Expense(name="x", category="Various", amount=1.0))
    assert "EUR" in r and "$" not in r


# ── reading a file written by the old version, or by a bad day ───────────────

def test_a_corrupt_row_is_skipped_not_fatal(tmp_path, capsys):
    ledger = tmp_path / "expenses.csv"
    ledger.write_text(
        "name,amount,category,date\n"
        "Boa,10.00,Various,2026-01-01\n"
        "isto,nao,e,uma,linha,valida\n"
        "Outra,5.00,Leisure,2026-01-02\n",
        encoding="utf-8",
    )
    lidas = read(ledger)
    assert [e.name for e in lidas] == ["Boa", "Outra"]
    assert "skipped" in capsys.readouterr().err


def test_a_ledger_from_the_old_version_still_reads(tmp_path):
    """No header, three columns, no date — what the original wrote."""
    ledger = tmp_path / "expenses.csv"
    ledger.write_text("Calças,25.0,Clothing\n", encoding="utf-8")
    (lido,) = read(ledger)
    assert lido.name == "Calças" and lido.amount == 25.0


def test_a_missing_ledger_is_empty_not_an_error(tmp_path):
    assert read(tmp_path / "nao-existe.csv") == []


def test_summarising_nothing_says_so(tmp_path, capsys):
    summarise(tmp_path / "vazio.csv")
    assert "Nothing recorded" in capsys.readouterr().out


# ── the header is written once, not once per row ─────────────────────────────

def test_the_header_is_written_exactly_once(tmp_path):
    ledger = tmp_path / "expenses.csv"
    for i in range(3):
        append(Expense(name=f"n{i}", category="Various", amount=1.0), ledger)

    with ledger.open(encoding="utf-8", newline="") as f:
        linhas = list(csv.reader(f))
    assert linhas[0][0] == "name"
    assert sum(1 for l in linhas if l and l[0] == "name") == 1
    assert len(linhas) == 4


def test_totals_add_up(tmp_path, capsys):
    ledger = tmp_path / "expenses.csv"
    append(Expense(name="a", category="Various", amount=10.0), ledger)
    append(Expense(name="b", category="Leisure", amount=5.50), ledger)
    summarise(ledger)
    out = capsys.readouterr().out
    assert "15.50" in out


def test_every_category_is_accepted():
    for c in CATEGORIES:
        assert Expense(name="x", category=c, amount=1.0).category == c


# ── the migration: a ledger from the emoji era ───────────────────────────────

def test_the_old_emoji_categories_still_read(tmp_path):
    """The first version stored "🕶  Clothing", emoji and double space included.

    Dropping those rows would mean the fix for the CSV bug silently deleted the
    ledger it existed to protect.
    """
    ledger = tmp_path / "expenses.csv"
    ledger.write_text(
        "Calças,25.0,🕶  Clothing\n"
        "Bilhete,3.20,🚗 Transport\n"
        "Jantar,18.00,🍽  Restaurants\n",
        encoding="utf-8",
    )
    lidas = read(ledger)
    assert [e.category for e in lidas] == ["Clothing", "Transport", "Restaurants"]
    assert sum(e.amount for e in lidas) == pytest.approx(46.20)


def test_an_unknown_category_is_still_skipped(tmp_path, capsys):
    ledger = tmp_path / "expenses.csv"
    ledger.write_text("x,1.0,Crypto\n", encoding="utf-8")
    assert read(ledger) == []
    assert "skipped" in capsys.readouterr().err

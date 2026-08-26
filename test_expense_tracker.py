"""Tests for the expense tracker.

    pip install pytest && pytest -q

Every test here corresponds to something that was actually broken. That is the
point of writing them at all: a test that could never have failed tells you
nothing about the program.
"""

import csv
import datetime

import pytest

from expense import CATEGORIES, Expense, InvalidExpense, parse_amount, parse_date
from expense_tracker import (
    append, in_month, normalise_category, parse_args, parse_month, read, summarise,
)


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


# ── the summary used to cover a window it never chose ────────────────────────

def _ledger(tmp_path, linhas):
    p = tmp_path / "expenses.csv"
    p.write_text("name,amount,category,date\n" + "".join(linhas), encoding="utf-8")
    return p


def test_the_date_column_is_read_back(tmp_path):
    """It was being written on every row and thrown away on every read."""
    ledger = _ledger(tmp_path, ["Almoço,12.50,Restaurants,2026-07-14\n"])
    (lido,) = read(ledger)
    assert lido.date == datetime.date(2026, 7, 14)


def test_a_row_with_no_date_is_still_an_expense(tmp_path):
    ledger = tmp_path / "expenses.csv"
    ledger.write_text("Calças,25.0,Clothing\n", encoding="utf-8")
    (lido,) = read(ledger)
    assert lido.amount == 25.0
    assert lido.date is None


def test_an_unreadable_date_does_not_lose_the_row(tmp_path):
    # A corrupt fourth field costs the row its month, not its existence.
    ledger = _ledger(tmp_path, ["x,1.00,Various,not-a-date\n"])
    (lido,) = read(ledger)
    assert lido.amount == 1.0 and lido.date is None


def test_a_month_is_a_month(tmp_path):
    ledger = _ledger(tmp_path, [
        "junho,10.00,Various,2026-06-30\n",
        "julho a,20.00,Various,2026-07-01\n",
        "julho b,5.00,Leisure,2026-07-31\n",
        "agosto,99.00,Various,2026-08-01\n",
    ])
    julho = in_month(read(ledger), 2026, 7)
    assert sorted(e.amount for e in julho) == [5.0, 20.0]


def test_the_summary_defaults_to_one_month(tmp_path, capsys):
    """THE BUG. Six months in the file, one month in the answer.

    The old version summed everything and divided by today's day of the month.
    On a file holding half a year that is not a daily average, it is half a
    year divided by an arbitrary number — and it looked entirely plausible,
    which is the part that makes it dangerous.
    """
    ledger = _ledger(tmp_path, [
        "março,300.00,Various,2026-03-05\n",
        "abril,300.00,Various,2026-04-05\n",
        "julho,40.00,Various,2026-07-05\n",
    ])
    summarise(ledger, (2026, 7))
    out = capsys.readouterr().out
    assert "40.00" in out
    assert "300.00" not in out, "another month leaked into this one"
    assert "July 2026" in out


def test_all_time_prints_no_daily_average(tmp_path, capsys):
    # Printing one over a six-month window would be the same bug wearing a flag.
    ledger = _ledger(tmp_path, [
        "março,300.00,Various,2026-03-05\n",
        "julho,40.00,Various,2026-07-05\n",
    ])
    summarise(ledger, None)
    out = capsys.readouterr().out
    assert "340.00" in out
    assert "Per day" not in out


def test_an_empty_month_says_so_and_points_at_all(tmp_path, capsys):
    ledger = tmp_path / "expenses.csv"
    ledger.write_text("antigo,25.0,Clothing\n", encoding="utf-8")
    summarise(ledger, (2026, 8))
    out = capsys.readouterr().out
    assert "Nothing recorded in August 2026" in out
    assert "--all" in out, "a dead end is not an answer"


def test_undated_rows_are_flagged_not_silently_dropped(tmp_path, capsys):
    ledger = tmp_path / "expenses.csv"
    ledger.write_text(
        "name,amount,category,date\n"
        "sem data,10.00,Various,\n"
        "com data,5.00,Various,2026-08-02\n",
        encoding="utf-8",
    )
    summarise(ledger, (2026, 8))
    out = capsys.readouterr().out
    assert "5.00" in out
    assert "1 row(s) with no date" in out


# ── the flags ────────────────────────────────────────────────────────────────

def test_no_arguments_means_this_month():
    hoje = datetime.date.today()
    month, summary_only = parse_args([])
    assert month == (hoje.year, hoje.month)
    assert summary_only is False


def test_all_means_no_window():
    assert parse_args(["--all"]) == (None, False)


def test_summary_skips_the_prompts():
    assert parse_args(["--summary"])[1] is True
    assert parse_args(["-s"])[1] is True


def test_month_takes_a_month():
    assert parse_args(["--month", "2026-07"])[0] == (2026, 7)


def test_help_is_not_an_error():
    assert parse_args(["--help"]) is None
    assert parse_args(["-h"]) is None


@pytest.mark.parametrize("cru", ["2026-13", "2026-00", "07-2026", "julho", "2026", "", "1800-01"])
def test_months_that_are_not_months(cru):
    with pytest.raises(InvalidExpense):
        parse_month(cru)


def test_month_with_nothing_after_it_explains_itself():
    with pytest.raises(InvalidExpense, match="needs a value"):
        parse_args(["--month"])


def test_an_unknown_flag_is_not_ignored():
    # Silently ignoring a typo'd flag means the program does something other
    # than what was asked and says nothing about it.
    with pytest.raises(InvalidExpense, match="Unknown option"):
        parse_args(["--evrything"])

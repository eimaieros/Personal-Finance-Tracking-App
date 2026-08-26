# Expense tracker

A terminal expense tracker in Python. You type what you spent, it appends a row
to a CSV, and it shows you where the money went.

[![CI](https://github.com/eimaieros/Personal-Finance-Tracking-App/actions/workflows/ci.yml/badge.svg)](https://github.com/eimaieros/Personal-Finance-Tracking-App/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![52 tests](https://img.shields.io/badge/tests-52-brightgreen)

```bash
python expense_tracker.py                    # record, then summarise this month
python expense_tracker.py --summary          # just the summary
python expense_tracker.py --month 2026-07    # a specific month
python expense_tracker.py --all              # the whole ledger
```

No dependencies to run it. `pytest` for the tests.

---

## Why this repository is worth two minutes

I wrote this in February 2025, as one of the first things I built in Python. It
worked when I used it and it had a bug that would have destroyed the file.

I came back to it in August 2026 and fixed what was wrong. The interesting part
is not the code — it is a hundred and fifty lines of terminal program — it is
what a year of writing software lets you see in your own work.

## What was broken

### An expense with a comma in its name corrupted the ledger permanently

The row was written by hand:

```python
f.write(f"{expense.name},{expense.amount},{expense.category}\n")
```

Buy lunch, call it `Almoço, Lisboa`, and the file now has a four-field row that
`split(",")` can never read back. Every summary after that raised `ValueError`
and the program died on startup. One comma, permanent damage, no warning.

`csv.writer` quotes the field. `csv.reader` unquotes it. The module has been in
the standard library since 1.5 and I did not reach for it, because writing a
line with an f-string looked simpler and was — right up until it wasn't.

### `float("25,50")` raises, and that is how the amount is written here

I am Portuguese. The decimal separator is a comma. The program crashed with a
traceback on the most natural input its author could give it, which is a good
demonstration of why you test with something other than the happy path you had
in mind while writing.

`parse_amount` now reads `25,50`, `25.50`, `1.234,56`, `1,234.56` and `25,50 €`.

### Every prompt was one typo away from losing your work

`float(input(...))` and `int(input(...))` were called directly. Mistype the
amount and the program exited with a stack trace, taking the expense name you
had already typed with it. Every prompt loops now.

### It recorded exactly one expense and exited

Which made it a form you filled in once, rather than a thing you would open
twice. It loops until you press enter on an empty name.

### The file lived wherever you happened to be standing

`"expenses.csv"` is relative to the working directory, so running the program
from anywhere else silently started a second, empty ledger. It resolves next to
the script now.

### Two lines that looked like a feature and did nothing

`days_in_month` and `remaining_days` were computed at the end of the summary and
never used. Dead code is worse than missing code: it reads like an intention and
proves the author stopped paying attention. It reports a daily average now.

### The repr said dollars, the summary said euros

A program that reports two currencies for the same number is worse than one that
reports the wrong one, because you cannot tell which of the two is the mistake.

### The daily average was a number, not an answer

The summary summed the entire file and divided by today's day of the month. That
is correct for exactly as long as the ledger holds one month. Put six months in
it and "per day so far" divides half a year of spending by the twenty-sixth of
August — and the result looks perfectly plausible, which is the part that makes
it dangerous. A crash tells you something is wrong. This just quietly lies.

The date was already being written to every row since the rewrite. It simply was
not being read back. The summary is scoped to a month now, `--all` opens it up,
and the daily average is only printed for the window where it means something.

---

## Tests

```bash
pip install pytest
pytest -q          # 52 tests
```

Every test corresponds to something that was actually broken. A test that could
never have failed tells you nothing.

Two of them are worth pointing at:

- `test_a_comma_in_the_name_survives_a_round_trip` — the corruption bug, pinned.
  Put the f-string back and it fails.
- `test_the_old_emoji_categories_still_read` — the first version stored
  `"🕶  Clothing"`, emoji and double space included. The new code writes a header
  and a date column and still reads that. Breaking someone's existing data to
  fix a bug is not a fix, so `normalise_category` strips anything that is not a
  letter and matches on what is left.

## Files

```
expense.py                 the Expense model, the categories, amount parsing
expense_tracker.py         prompts, the CSV, the summary
test_expense_tracker.py    52 tests
expenses.csv               the ledger — one sample row, in the old format on
                           purpose, so the migration is visible
```

## What it still is not

- No editing or deleting a row once written. Append-only, by design at this size.
- No budgets, no recurring expenses, no multi-currency, no search.
- The category list is fixed in `expense.py`. Changing a label orphans the rows
  already written under the old one, which is why it is a constant and not a
  prompt.

## Licence

MIT © [Rodrigo Figueiredo](https://rodrigofigueiredo.dev)

"""A terminal expense tracker.

Written in February 2025 as one of my first Python programs, and revisited
since. The revisit is documented in the README: the bugs it had are more
interesting than the code it is.
"""

from __future__ import annotations

import calendar
import csv
import datetime
import sys
from pathlib import Path

from expense import CATEGORIES, Expense, InvalidExpense, parse_amount

# Next to this file, not next to whatever directory you happened to run it
# from. The original used a bare "expenses.csv", so running it from anywhere
# else silently started a second, empty ledger.
LEDGER = Path(__file__).with_name("expenses.csv")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0

    print("Expense tracker. Blank name to stop.\n")

    added = 0
    while True:
        expense = ask_for_expense()
        if expense is None:
            break
        append(expense, LEDGER)
        added += 1
        print(f"  saved: {expense.name} — {expense.amount:.2f} EUR\n")

    # The original recorded exactly one expense and exited, which made it a
    # form you filled in once rather than something you would use twice.
    if added:
        print(f"{added} expense{'s' if added != 1 else ''} added.\n")

    summarise(LEDGER)
    return 0


def ask_for_expense() -> Expense | None:
    """Collect one expense, or None if the user is finished.

    Every prompt loops on bad input instead of raising. The original called
    `float(input(...))` and `int(input(...))` directly, so a typo ended the
    program with a traceback and lost whatever the user had already typed.
    """
    name = input("Expense name: ").strip()
    if not name:
        return None

    while True:
        try:
            amount = parse_amount(input("Amount (EUR): "))
            break
        except InvalidExpense as e:
            print(f"  {e}")

    while True:
        print("\nCategory:")
        for i, category in enumerate(CATEGORIES, start=1):
            print(f"  {i}. {category}")
        choice = input(f"Pick one [1-{len(CATEGORIES)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(CATEGORIES):
            category = CATEGORIES[int(choice) - 1]
            break
        print("  Not one of the options.")

    return Expense(name=name, category=category, amount=amount)


def append(expense: Expense, path: Path) -> None:
    """Write one row, through the csv module.

    THE BUG THIS FIXES. The original wrote the line by hand:

        f.write(f"{expense.name},{expense.amount},{expense.category}\\n")

    An expense called "Almoço, Lisboa" then produced a four-field row that
    `split(",")` could never read back, and every later summary raised
    ValueError on it. The file was corrupted permanently by one comma, and
    nothing warned you. `csv.writer` quotes it; `csv.reader` unquotes it.
    """
    novo = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if novo:
            writer.writerow(["name", "amount", "category", "date"])
        writer.writerow([
            expense.name,
            f"{expense.amount:.2f}",
            expense.category,
            datetime.date.today().isoformat(),
        ])


def read(path: Path) -> list[Expense]:
    """Read the ledger, skipping rows that cannot be read rather than dying.

    A ledger written by the old version has no header and may contain corrupt
    rows. Refusing to open the file at all would punish the user for a bug they
    did not write.
    """
    if not path.exists():
        return []

    out: list[Expense] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            if not row or row[0] == "name":       # header, or a blank line
                continue
            try:
                out.append(Expense(
                    name=row[0],
                    category=normalise_category(row[2]),
                    amount=float(row[1]),
                ))
            except (IndexError, ValueError, InvalidExpense):
                print(f"  skipped an unreadable row: {','.join(row)}", file=sys.stderr)
    return out


def normalise_category(raw: str) -> str:
    """Map a stored category onto a current one.

    The first version prefixed every category with an emoji and padded some of
    them with two spaces — `"🕶  Clothing"`. Dropping those rows would mean the
    fix for the CSV bug also silently deleted the ledger it was meant to
    protect, which is not a fix. Strip anything that is not a letter and match
    on what is left.
    """
    limpo = "".join(c for c in raw if c.isalpha() or c.isspace()).strip()
    for known in CATEGORIES:
        if limpo.casefold() == known.casefold():
            return known
    return raw     # unknown; Expense will reject it and the row is skipped


def summarise(path: Path) -> None:
    expenses = read(path)
    if not expenses:
        print("Nothing recorded yet.")
        return

    by_category: dict[str, float] = {}
    for e in expenses:
        by_category[e.category] = by_category.get(e.category, 0.0) + e.amount

    total = sum(e.amount for e in expenses)
    largest = max(len(c) for c in by_category)

    print("By category")
    for category, amount in sorted(by_category.items(), key=lambda kv: -kv[1]):
        share = amount / total * 100
        print(f"  {category:<{largest}}  {amount:>9.2f} EUR  {share:>5.1f}%")

    print(f"\n  {'Total':<{largest}}  {total:>9.2f} EUR")

    # The original computed the days left in the month and then never used
    # them — two lines that looked like a feature and did nothing. Either it
    # says something or it comes out; this says something.
    today = datetime.date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    remaining = days_in_month - today.day
    if remaining > 0:
        print(f"  {'Per day so far':<{largest}}  {total / today.day:>9.2f} EUR")
        print(f"  {remaining} day{'s' if remaining != 1 else ''} left in the month.")


if __name__ == "__main__":
    raise SystemExit(main())

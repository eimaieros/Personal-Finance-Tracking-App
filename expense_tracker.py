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

from expense import CATEGORIES, Expense, InvalidExpense, parse_amount, parse_date

# Next to this file, not next to whatever directory you happened to run it
# from. The original used a bare "expenses.csv", so running it from anywhere
# else silently started a second, empty ledger.
LEDGER = Path(__file__).with_name("expenses.csv")


USAGE = """Expense tracker.

  python expense_tracker.py               record expenses, then summarise this month
  python expense_tracker.py --summary     summarise this month and exit
  python expense_tracker.py --month 2026-07   a specific month
  python expense_tracker.py --all         the whole ledger

The summary defaults to the current month. Before that default existed it
summed the entire file and divided by today's date, which is correct for
exactly as long as the file holds one month.
"""


def parse_args(argv: list[str]) -> tuple[tuple[int, int] | None, bool] | None:
    """Return (month, summary_only), or None if the caller asked for help.

    Hand-rolled rather than argparse: four flags do not justify importing a
    parser, and the error messages here can say what to do instead.
    """
    today = datetime.date.today()
    month: tuple[int, int] | None = (today.year, today.month)
    summary_only = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in {"-h", "--help"}:
            return None
        elif arg == "--all":
            month = None
        elif arg in {"-s", "--summary"}:
            summary_only = True
        elif arg == "--month":
            if i + 1 >= len(argv):
                raise InvalidExpense("--month needs a value, like --month 2026-07.")
            month = parse_month(argv[i + 1])
            i += 1
        else:
            raise InvalidExpense(f"Unknown option {arg!r}. Try --help.")
        i += 1

    return month, summary_only


def parse_month(raw: str) -> tuple[int, int]:
    """`2026-07`, or a message a human can act on."""
    try:
        year_s, month_s = raw.strip().split("-")
        year, month = int(year_s), int(month_s)
    except ValueError:
        raise InvalidExpense(f"Could not read {raw!r} as a month. Use YYYY-MM.") from None
    if not 1 <= month <= 12:
        raise InvalidExpense(f"{month} is not a month.")
    if not 1970 <= year <= 9999:
        raise InvalidExpense(f"{year} is not a year this program will believe.")
    return year, month


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    try:
        parsed = parse_args(argv)
    except InvalidExpense as e:
        print(e, file=sys.stderr)
        return 2
    if parsed is None:
        print(USAGE)
        return 0
    month, summary_only = parsed

    if summary_only:
        summarise(LEDGER, month)
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

    summarise(LEDGER, month)
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
            (expense.date or datetime.date.today()).isoformat(),
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
                    # Column 3 exists only in files written by the current
                    # version. Rows from the first one keep date=None.
                    date=parse_date(row[3]) if len(row) > 3 else None,
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


def in_month(expenses: list[Expense], year: int, month: int) -> list[Expense]:
    """The rows belonging to one calendar month."""
    return [
        e for e in expenses
        if e.date is not None and e.date.year == year and e.date.month == month
    ]


def summarise(path: Path, month: tuple[int, int] | None = None) -> None:
    """Print where the money went.

    THE BUG THIS SIGNATURE FIXES.

    The previous version summed the entire file and then divided by today's
    day of the month to get a daily average. That is right for exactly as long
    as the ledger contains one month. On a file with six months in it, "per day
    so far" divided half a year of spending by the twenty-sixth of August, and
    produced a number that was not wrong so much as meaningless — and it looked
    perfectly plausible, which is worse.

    The date was already being written to every row. It just was not being read.

    `month=None` means the whole file, which is what `--all` asks for.
    """
    todas = read(path)
    if not todas:
        print("Nothing recorded yet.")
        return

    if month is None:
        expenses, rotulo = todas, "all time"
        sem_data = 0
    else:
        year, mon = month
        expenses = in_month(todas, year, mon)
        rotulo = f"{calendar.month_name[mon]} {year}"
        sem_data = sum(1 for e in todas if e.date is None)

    if not expenses:
        print(f"Nothing recorded in {rotulo}.")
        if sem_data:
            print(f"  ({sem_data} row(s) have no date — try --all.)")
        return

    by_category: dict[str, float] = {}
    for e in expenses:
        by_category[e.category] = by_category.get(e.category, 0.0) + e.amount

    total = sum(e.amount for e in expenses)
    largest = max(len(c) for c in by_category)
    largest = max(largest, len("Per day so far"))

    print(f"{rotulo} — {len(expenses)} expense{'s' if len(expenses) != 1 else ''}")
    print("By category")
    for category, amount in sorted(by_category.items(), key=lambda kv: -kv[1]):
        share = amount / total * 100
        print(f"  {category:<{largest}}  {amount:>9.2f} EUR  {share:>5.1f}%")

    print(f"\n  {'Total':<{largest}}  {total:>9.2f} EUR")

    # The daily average only means something when the window is one month, and
    # only up to today within it. Printing it for "all time" would reintroduce
    # the exact bug this function was rewritten to remove.
    today = datetime.date.today()
    if month == (today.year, today.month):
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        remaining = days_in_month - today.day
        print(f"  {'Per day so far':<{largest}}  {total / today.day:>9.2f} EUR")
        if remaining > 0:
            print(f"  {remaining} day{'s' if remaining != 1 else ''} left in the month.")

    if sem_data:
        print(f"\n  {sem_data} row(s) with no date are not counted here. --all includes them.")


if __name__ == "__main__":
    raise SystemExit(main())

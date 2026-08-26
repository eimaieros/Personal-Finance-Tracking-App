"""The one thing this program stores."""

from __future__ import annotations

from dataclasses import dataclass

# The categories, and the order they are offered in. Kept here rather than in
# the UI because the CSV stores the category name verbatim: change a label and
# you orphan every row already written under the old one.
CATEGORIES: tuple[str, ...] = (
    "Various",
    "Leisure",
    "Transport",
    "Restaurants",
    "Clothing",
    "Supermarket",
)


class InvalidExpense(ValueError):
    """Raised when a value cannot be an expense, with a message for a human."""


@dataclass(frozen=True)
class Expense:
    """A single line of spending.

    Frozen because nothing in this program has a reason to mutate one after it
    exists, and an accidental write is a class of bug that simply cannot happen
    if the attribute refuses to be set.
    """

    name: str
    category: str
    amount: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidExpense("An expense needs a name.")
        if self.category not in CATEGORIES:
            raise InvalidExpense(
                f"Unknown category {self.category!r}. "
                f"Expected one of: {', '.join(CATEGORIES)}."
            )
        if self.amount <= 0:
            raise InvalidExpense("An amount has to be greater than zero.")

    def __repr__(self) -> str:
        # The original printed a dollar sign here while the summary printed
        # euros. A program that reports two currencies for the same number is
        # worse than one that reports the wrong one, because you cannot tell
        # which of the two is the mistake.
        return f"<Expense: {self.name}, {self.category}, {self.amount:.2f} EUR>"


def parse_amount(raw: str) -> float:
    """Read an amount the way a person in Portugal would type it.

    `float("25,50")` raises. Half the world writes decimals with a comma, and
    the original crashed with a traceback on the most natural input a
    Portuguese user could give it. Thousands separators are stripped for the
    same reason.
    """
    cleaned = raw.strip().replace(" ", "").replace("€", "")

    if "," in cleaned and "." in cleaned:
        # 1.234,56 or 1,234.56 — whichever separator comes last is the decimal.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        value = float(cleaned)
    except ValueError:
        raise InvalidExpense(f"{raw!r} is not a number.") from None

    if value <= 0:
        raise InvalidExpense("An amount has to be greater than zero.")
    return value

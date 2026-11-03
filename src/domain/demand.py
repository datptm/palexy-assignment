"""Required staffing estimates and complete-week demand checks."""

from src.domain.limits import bounded_int, checked_total
from src.model.scheduling import DemandCell, SchedulingError


def required_staff(transactions: object, threshold: object) -> int:
    """Estimate required staff with exact integer ceiling arithmetic."""
    count = bounded_int(transactions, field="transactions")
    divisor = bounded_int(threshold, field="threshold", minimum=1)
    return max(1, (count + divisor - 1) // divisor)


def validate_demand(cells: tuple[DemandCell, ...], threshold: int) -> None:
    """Require exactly one bounded cell per operating hour and bounded totals."""
    keys = {(cell.day, cell.hour) for cell in cells}
    expected = {(day, hour) for day in range(7) for hour in range(7, 23)}
    if len(cells) != 112 or keys != expected:
        raise SchedulingError("INVALID_DEMAND", "demand must contain exactly 112 unique cells")
    checked_total(
        sum(bounded_int(cell.transactions, field="transactions") for cell in cells),
        field="weekly_transactions",
    )
    checked_total(
        sum(required_staff(cell.transactions, threshold) for cell in cells),
        field="weekly_required_staff",
    )

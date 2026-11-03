"""Small, explicit inputs and contract checks for the scheduling tests."""

import csv
import importlib
import io
from collections.abc import Callable
from typing import Any

from src.domain.periods import WEEKDAYS


def require_symbol(module_name: str, symbol_name: str) -> Any:
    """Report an absent planned feature as an assertion, not a collection error."""
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name != module_name:
            raise
        module = None
    assert module is not None, f"missing planned module {module_name}"
    symbol = getattr(module, symbol_name, None)
    assert symbol is not None, f"missing planned {module_name}.{symbol_name}"
    return symbol


def require_method(instance: object, name: str) -> Callable[..., Any]:
    """Make a missing facade operation a clear red-stage assertion."""
    method = getattr(instance, name, None)
    assert callable(method), f"missing planned ScheduleService.{name}"
    return method


def week_csv(
    *,
    day_order: tuple[str, ...] = WEEKDAYS,
    values: dict[tuple[str, int], str | int] | None = None,
    title: bool = False,
    total: bool = False,
) -> bytes:
    """Build a complete synthetic report; overrides are literal source cells."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    if title:
        writer.writerow(["Aug 07, 2026 - Aug 13, 2026"])
    writer.writerow(["Hour", *day_order, *(["Total"] if total else [])])
    for hour in range(7, 23):
        row = [f"{hour:02d}:00"]
        row.extend((values or {}).get((day, hour), 0) for day in day_order)
        if total:
            row.append(999)
        writer.writerow(row)
    if total:
        writer.writerow(["Grand total", *([999] * (len(day_order) + 1))])
    return output.getvalue().encode("utf-8")


def demand_map(cells: object) -> dict[tuple[int, int], int]:
    """Project typed parsed cells to an independently checkable mapping."""
    return {(cell.day, cell.hour): cell.transactions for cell in cells}

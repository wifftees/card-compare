"""Broadcast group definitions for admin bot handlers.

Maps group keys (used in callback_data) to labels and query functions
that return user IDs for each segment.
"""

from collections.abc import Awaitable, Callable

from database.queries import (
    get_users_no_reports_no_payments,
    get_users_one_report_no_payments,
    get_users_single_purchase,
)

GROUP_LABELS: dict[str, str] = {
    "no_activity": "Без отчетов",
    "used_trial": "Использовали пробный",
    "bought_single": "Купили 1 отчет",
}

GROUP_QUERY_MAP: dict[str, Callable[[], Awaitable[list[int]]]] = {
    "no_activity": get_users_no_reports_no_payments,
    "used_trial": get_users_one_report_no_payments,
    "bought_single": get_users_single_purchase,
}

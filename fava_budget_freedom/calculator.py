from datetime import date, timedelta
from decimal import Decimal

from beancount.core.amount import Amount

from .utils import (
    get_active_budget_definition,
    get_next_period_start,
    get_period_start,
    iter_period_starts,
)


class BudgetCalculator:
    """
    Calculates effective budget amounts, handling periods and rollovers.
    """

    def __init__(self, usage_calculator):
        self.usage_calculator = usage_calculator

    def calculate_effective_budget(self, budget_list, report_start, report_end):
        """
        Calculate the effective budget for the report period, including rollovers.

        Args:
            budget_list: List of budget definitions for a pattern.
            report_start: Start date of the report.
            report_end: End date of the report.

        Returns:
            Tuple of (Total Amount, Rollover Amount)
        """
        latest_budget = budget_list[-1]
        cutoff_date = report_end
        if cutoff_date == date.max:
            cutoff_date = date.today()

        period_budget_accumulator = self._calculate_period_budget(
            budget_list, report_start, cutoff_date
        )

        rollover_amount = Decimal(0)
        active_budget_at_range_start = get_active_budget_definition(
            budget_list, get_period_start(report_start, 'monthly')
        )
        should_calculate_rollover = (
            active_budget_at_range_start is not None
            and active_budget_at_range_start['rollover']
            and active_budget_at_range_start['period'] == 'monthly'
        )
        if should_calculate_rollover:
            rollover_amount = self._calculate_accumulated_rollover(
                budget_list, report_start
            )

        total = Amount(
            period_budget_accumulator + rollover_amount,
            latest_budget['amount'].currency,
        )
        return total, rollover_amount

    def _calculate_accumulated_rollover(self, budget_list, report_start):
        rollover_amount = Decimal(0)
        current_month = date(report_start.year, 1, 1)
        selected_month_start = get_period_start(report_start, 'monthly')

        while current_month < selected_month_start:
            active_budget = get_active_budget_definition(budget_list, current_month)
            if (
                active_budget
                and active_budget['period'] == 'monthly'
                and active_budget['rollover']
            ):
                month_end = get_next_period_start(current_month, 'monthly')
                past_actual = self.usage_calculator.calculate_usage_for_period(
                    current_month,
                    month_end,
                    active_budget['pattern'],
                    active_budget['amount'].currency,
                )
                past_number = (
                    past_actual.number
                    if past_actual.number is not None
                    else Decimal(0)
                )
                remainder = active_budget['amount'].number - past_number
                rollover_amount += remainder

            current_month = get_next_period_start(current_month, 'monthly')

        return rollover_amount

    def _calculate_period_budget(self, budget_list, report_start, report_end):
        period_budget_accumulator = Decimal(0)
        report_end_exclusive = report_end + timedelta(days=1)

        for index, budget in enumerate(budget_list):
            segment_start = max(budget['effective_date'], report_start)
            next_effective_date = report_end_exclusive
            if index + 1 < len(budget_list):
                next_effective_date = budget_list[index + 1]['effective_date']

            segment_end_exclusive = min(next_effective_date, report_end_exclusive)
            if segment_start >= segment_end_exclusive:
                continue

            segment_end_inclusive = segment_end_exclusive - timedelta(days=1)
            for period_start in iter_period_starts(
                budget['period'], segment_start, segment_end_inclusive
            ):
                period_budget_accumulator += budget['amount'].number

        return period_budget_accumulator

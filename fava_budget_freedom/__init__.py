from decimal import Decimal
from datetime import timedelta

from beancount.core.amount import Amount
from beancount.core.inventory import Inventory
from fava.context import g
from fava.ext import FavaExtensionBase

from .budget import BudgetParser
from .calculator import BudgetCalculator
from .usage import UsageCalculator
from .utils import (
    budget_overlaps_range,
    calculate_year_progress,
    clean_pattern_for_link,
    get_report_date_range,
    is_subset,
)

print("Loading fava_budget_freedom module...")


class BudgetFreedom(FavaExtensionBase):
    """
    Fava extension for advanced budget reporting.
    """

    report_title = "Budget Freedom"

    def __init__(self, ledger, config=None):
        print("BudgetFreedom extension initialized!")
        super().__init__(ledger, config)

    def generate_budget_report(self):
        """
        Parses custom 'budget' directives and calculates actual usage based on
        wildcards.
        """
        entries, date_range = self._get_context()
        report_start, report_end = get_report_date_range(date_range)
        time_percent = calculate_year_progress(date_range)

        budget_parser = BudgetParser(self.ledger.all_entries)
        usage_calculator_all = UsageCalculator(self.ledger.all_entries)
        budget_calculator = BudgetCalculator(usage_calculator_all)
        usage_calculator_report = UsageCalculator(entries)

        budgets = budget_parser.parse_budget_definitions(report_end)

        report_data = self._generate_report_rows(
            budgets,
            entries,
            report_start,
            report_end,
            time_percent,
            usage_calculator_report,
            budget_calculator,
        )

        total_budget_row = None
        final_report_data = []

        for row in report_data:
            if row['pattern'] == "Expenses:*":
                total_budget_row = row
            else:
                final_report_data.append(row)

        if total_budget_row is None and final_report_data:
            first_row = final_report_data[0]
            currency = first_row['budget'].currency

            total_unadjusted_budget = Decimal(0)
            total_actual_amount = Decimal(0)

            for row in final_report_data:
                if row['budget'].currency == currency:
                    total_unadjusted_budget += row['unadjusted_budget'].number
                    total_actual_amount += (
                        row['total_actual'].number
                        if row['total_actual'].number is not None
                        else Decimal(0)
                    )

            unadjusted_percent = 0
            if total_unadjusted_budget != 0:
                unadjusted_percent = (
                    total_actual_amount / total_unadjusted_budget
                ) * 100

            total_budget_row = {
                'pattern': 'Total',
                'account_name': 'Expenses',
                'unadjusted_budget': Amount(total_unadjusted_budget, currency),
                'total_actual': Amount(total_actual_amount, currency),
                'unadjusted_percent': unadjusted_percent,
                'time_percent': time_percent,
            }

        return {
            'report_data': final_report_data,
            'range_start': report_start,
            'range_end': report_end,
            'total_budget_row': total_budget_row,
        }

    def _generate_report_rows(
        self,
        budgets,
        entries,
        report_start,
        report_end,
        time_percent,
        usage_calculator,
        budget_calculator,
    ):
        filtered_budgets = {
            pattern: budget_list
            for pattern, budget_list in budgets.items()
            if budget_list and budget_overlaps_range(
                budget_list, report_start, report_end
            )
        }

        usage_map = usage_calculator.calculate_all_usages(
            entries, filtered_budgets, report_start, report_end
        )
        amortization_details = usage_calculator.calculate_amortization_details(
            entries, filtered_budgets, report_start, report_end
        )

        effective_budgets = {}
        rollovers = {}
        latest_budgets = {}

        for pattern, budget_list in filtered_budgets.items():
            latest_budgets[pattern] = budget_list[-1]
            effective_budget, rollover = budget_calculator.calculate_effective_budget(
                budget_list, report_start, report_end
            )
            effective_budgets[pattern] = effective_budget
            rollovers[pattern] = rollover

        adjusted_budgets = {}
        for parent_pattern, parent_budget in effective_budgets.items():
            subtracted_amount = Decimal(0)
            candidates = []

            for child_pattern, child_budget in effective_budgets.items():
                if parent_pattern == child_pattern:
                    continue
                if child_budget.currency != parent_budget.currency:
                    continue
                if is_subset(child_pattern, parent_pattern):
                    candidates.append(child_pattern)

            direct_children = []
            for candidate in candidates:
                is_nested = False
                for other in candidates:
                    if candidate == other:
                        continue
                    if is_subset(candidate, other):
                        is_nested = True
                        break
                if not is_nested:
                    direct_children.append(candidate)

            for child_pattern in direct_children:
                subtracted_amount += effective_budgets[child_pattern].number

            new_amount = parent_budget.number - subtracted_amount
            adjusted_budgets[parent_pattern] = Amount(
                new_amount, parent_budget.currency
            )

        report_data = []
        for pattern in filtered_budgets:
            latest_budget = latest_budgets[pattern]
            effective_budget = adjusted_budgets[pattern]
            gross_budget = effective_budgets[pattern]
            rollover = rollovers[pattern]

            inventory = usage_map.get(pattern, Inventory())
            actual_amount = inventory.get_currency_units(effective_budget.currency)

            percent = 0
            actual_val = (
                actual_amount.number
                if actual_amount.number is not None
                else Decimal(0)
            )
            if effective_budget.number != 0:
                percent = (actual_val / effective_budget.number) * 100

            total_actual = usage_calculator.calculate_usage_for_period(
                report_start,
                report_end + timedelta(days=1),
                pattern,
                gross_budget.currency,
            )
            total_actual_val = (
                total_actual.number
                if total_actual.number is not None
                else Decimal(0)
            )

            gross_percent = 0
            if gross_budget.number != 0:
                gross_percent = (total_actual_val / gross_budget.number) * 100

            account_name = clean_pattern_for_link(pattern)

            amortization_items = []
            if pattern in amortization_details:
                for amort_account, inventory in amortization_details[pattern].items():
                    amort_amount = inventory.get_currency_units(
                        effective_budget.currency
                    )
                    if amort_amount.number and amort_amount.number > 0:
                        amortization_items.append(
                            {
                                'account': amort_account,
                                'amount': amort_amount,
                            }
                        )

            report_data.append(
                {
                    'pattern': pattern,
                    'account_name': account_name,
                    'budget': effective_budget,
                    'unadjusted_budget': gross_budget,
                    'actual': actual_amount,
                    'total_actual': total_actual,
                    'percent': percent,
                    'unadjusted_percent': gross_percent,
                    'time_percent': time_percent,
                    'period': latest_budget['period'],
                    'rollover': rollover,
                    'is_rollover': latest_budget['rollover'],
                    'amortization_items': amortization_items,
                }
            )
        return report_data

    def _get_context(self):
        try:
            return g.filtered.entries, g.filtered.date_range
        except:
            return self.ledger.all_entries, None

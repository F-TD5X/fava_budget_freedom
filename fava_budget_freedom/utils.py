import fnmatch
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from beancount.core.amount import Amount


def get_period_start(target_date, period):
    """
    Get the start date of the period containing target_date.

    Args:
        target_date: The date to resolve.
        period: One of monthly, weekly, quarterly, yearly.
    """
    if period == 'monthly':
        return date(target_date.year, target_date.month, 1)
    if period == 'weekly':
        return target_date - relativedelta(days=target_date.weekday())
    if period == 'quarterly':
        quarter_month = ((target_date.month - 1) // 3) * 3 + 1
        return date(target_date.year, quarter_month, 1)
    if period == 'yearly':
        return date(target_date.year, 1, 1)
    raise ValueError(f"Unsupported budget period: {period}")


def get_next_period_start(period_start, period):
    """
    Get the next start boundary for the given period.

    Args:
        period_start: Start date of the current period.
        period: One of monthly, weekly, quarterly, yearly.
    """
    if period == 'monthly':
        return period_start + relativedelta(months=1)
    if period == 'weekly':
        return period_start + relativedelta(days=7)
    if period == 'quarterly':
        return period_start + relativedelta(months=3)
    if period == 'yearly':
        return period_start + relativedelta(years=1)
    raise ValueError(f"Unsupported budget period: {period}")


def get_budget_effective_date(budget_date, period):
    """
    Get the first full period boundary on which a budget becomes active.

    Args:
        budget_date: Directive date.
        period: One of monthly, weekly, quarterly, yearly.
    """
    period_start = get_period_start(budget_date, period)
    if budget_date == period_start:
        return period_start
    return get_next_period_start(period_start, period)


def iter_period_starts(period, start_date, end_date):
    """
    Yield starts of all periods that overlap the inclusive report range.

    Args:
        period: One of monthly, weekly, quarterly, yearly.
        start_date: Inclusive report start.
        end_date: Inclusive report end.
    """
    current = get_period_start(start_date, period)
    while current <= end_date:
        yield current
        current = get_next_period_start(current, period)


def get_active_budget_definition(budget_list, target_date):
    """
    Resolve the budget definition active on target_date.

    Budgets become active on their first full period boundary and remain active
    until a later definition with a newer effective date supersedes them.

    Args:
        budget_list: Sorted list of budget definitions for one pattern.
        target_date: Date to resolve against.
    """
    active_budget = None
    active_effective_date = None
    active_index = -1

    for index, budget in enumerate(budget_list):
        effective_date = budget.get('effective_date')
        if effective_date is None:
            effective_date = get_budget_effective_date(budget['date'], budget['period'])

        if effective_date > target_date:
            continue

        if (
            active_budget is None or
            effective_date > active_effective_date or
            (effective_date == active_effective_date and index > active_index)
        ):
            active_budget = budget
            active_effective_date = effective_date
            active_index = index

    return active_budget

def budget_overlaps_range(budget_list, report_start, report_end):
    """
    Check whether any effective budget segment overlaps the inclusive report range.

    Args:
        budget_list: Sorted list of budget definitions for one pattern.
        report_start: Inclusive report start.
        report_end: Inclusive report end.
    """
    report_end_exclusive = report_end + relativedelta(days=1)

    for index, budget in enumerate(budget_list):
        segment_start = max(budget['effective_date'], report_start)
        next_effective_date = report_end_exclusive
        if index + 1 < len(budget_list):
            next_effective_date = budget_list[index + 1]['effective_date']

        segment_end_exclusive = min(next_effective_date, report_end_exclusive)
        if segment_start < segment_end_exclusive:
            return True

    return False


def matches_pattern(account, pattern):
    """
    Check if account matches the wildcard pattern.
    
    Args:
        account: The account name to check.
        pattern: The pattern to match against (can contain *).
    """
    if '*' in pattern:
         return fnmatch.fnmatch(account, pattern)
    else:
        return account == pattern or account.startswith(pattern + ":")

def is_subset(child_pattern, parent_pattern):
    """
    Check if child_pattern is a subset of parent_pattern.
    
    Args:
        child_pattern: The potential subset pattern.
        parent_pattern: The superset pattern.
    """
    if '*' in parent_pattern:
        return fnmatch.fnmatch(child_pattern, parent_pattern)
    else:
        return child_pattern.startswith(parent_pattern + ":")

def clean_pattern_for_link(pattern):
    """
    Remove wildcards to get a linkable account name.
    
    Args:
        pattern: The budget pattern.
    """
    if pattern.endswith(":*"):
        return pattern[:-2]
    elif pattern.endswith("*"):
        return pattern[:-1]
    return pattern

def parse_amount(amount_val):
    """
    Parse amount from string or Amount object.
    
    Args:
        amount_val: The amount value from the custom directive.
    """
    if isinstance(amount_val, str):
        try:
            parts = amount_val.split()
            if len(parts) == 2:
                return Amount(Decimal(parts[0]), parts[1])
        except:
            return None
    elif isinstance(amount_val, Amount):
        return amount_val
    return None

def get_report_date_range(date_range):
    """
    Determine the start and end date for the report.
    
    Args:
        date_range: The date range from Fava context.
    """
    if date_range:
        return date_range.begin, date_range.end - relativedelta(days=1)
    
    today = date.today()
    return date(today.year, 1, 1), today

def calculate_year_progress(date_range):
    """
    Calculate the percentage of time passed in the selected year.
    Returns None if the range is not a full year.
    
    Args:
        date_range: The date range from Fava context.
    """
    today = date.today()
    is_full_year = False
    report_year = today.year

    if date_range:
        if (date_range.begin.month == 1 and date_range.begin.day == 1 and
            date_range.end.month == 1 and date_range.end.day == 1 and
            date_range.end.year == date_range.begin.year + 1):
            is_full_year = True
            report_year = date_range.begin.year

    if not is_full_year:
        return None

    if today.year > report_year:
        return 100
    elif today.year < report_year:
        return 0
    
    start = date(today.year, 1, 1)
    end = date(today.year, 12, 31)
    total_days = (end - start).days + 1
    passed = (today - start).days + 1
    return (passed / total_days) * 100

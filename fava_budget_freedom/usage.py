from beancount.core import data
from beancount.core.inventory import Inventory
from .utils import matches_pattern

class UsageCalculator:
    """
    Calculates actual usage of budgets based on transaction entries.
    """
    def __init__(self, all_entries):
        """
        Initialize with all ledger entries.
        
        Args:
            all_entries: All entries from the ledger (used for historical calculations).
        """
        self.all_entries = all_entries
    
    def _is_amortization_transaction(self, entry):
        """
        Check if this transaction is amortization-generated.
        
        An amortization transaction contains a posting from Equity:Amortization:*
        with a negative amount (income side).
        
        Args:
            entry: Transaction entry to check.
            
        Returns:
            True if this is an amortization-generated transaction.
        """
        return any(
            posting.account.startswith('Equity:Amortization:') and posting.units.number < 0
            for posting in entry.postings
        )
    
    def _transform_amortization_account(self, account, amount):
        """
        Transform Equity:Amortization:* accounts to Expenses:* for budget matching.
        
        Args:
            account: Original account name.
            amount: Posting amount (number).
            
        Returns:
            Transformed account name for budget matching.
        """
        if account.startswith('Equity:Amortization:') and amount > 0:
            return 'Expenses:' + account[len('Equity:Amortization:'):]
        return account

    def calculate_usage_for_period(self, start_date, end_date, pattern, currency):
        """
        Calculate actual usage for a specific pattern and period using all entries.
        Used for rollover calculation.
        
        Args:
            start_date: Start date (inclusive).
            end_date: End date (exclusive).
            pattern: Account pattern.
            currency: Currency to sum.
        """
        inventory = Inventory()
        for entry in self.all_entries:
            if isinstance(entry, data.Transaction) and entry.date >= start_date and entry.date < end_date:
                self._accumulate_entry(entry, pattern, inventory)
        return inventory.get_currency_units(currency)

    def calculate_all_usages(self, entries, budgets, start_date, end_date):
        """
        Calculate usage for all budgets in the given period using the provided entries.
        Respects specificity (longest pattern wins).
        
        Args:
            entries: Filtered entries for the report.
            budgets: Dictionary of budget definitions.
            start_date: Start date (inclusive).
            end_date: End date (inclusive).
        """
        usage = {pattern: Inventory() for pattern in budgets}
        patterns = list(budgets.keys())
        
        for entry in entries:
            if isinstance(entry, data.Transaction):
                if entry.date >= start_date and entry.date <= end_date:
                    # Skip amortization-generated transactions
                    if self._is_amortization_transaction(entry):
                        continue
                    
                    for posting in entry.postings:
                        # Transform account name for amortization entries
                        account = self._transform_amortization_account(
                            posting.account, 
                            posting.units.number
                        )
                        
                        best_pattern = None
                        best_len = -1
                        
                        for pattern in patterns:
                            if matches_pattern(account, pattern):
                                # Specificity rule: longer pattern wins
                                if len(pattern) > best_len:
                                    best_pattern = pattern
                                    best_len = len(pattern)
                        
                        if best_pattern:
                            usage[best_pattern].add_amount(posting.units)
        return usage
    
    def calculate_amortization_details(self, entries, budgets, start_date, end_date):
        """
        Calculate amortization details for each budget pattern.
        
        Returns a dictionary mapping pattern -> {amortization_account -> Inventory}
        For example: {'Expenses:Home:Rent': {'Equity:Amortization:Home:Rent': Inventory}}
        
        Args:
            entries: Filtered entries for the report.
            budgets: Dictionary of budget definitions.
            start_date: Start date (inclusive).
            end_date: End date (inclusive).
        """
        amortization_details = {pattern: {} for pattern in budgets}
        patterns = list(budgets.keys())
        
        for entry in entries:
            if isinstance(entry, data.Transaction):
                if entry.date >= start_date and entry.date <= end_date:
                    # Skip amortization-generated transactions
                    if self._is_amortization_transaction(entry):
                        continue
                    
                    for posting in entry.postings:
                        original_account = posting.account
                        
                        # Only track Equity:Amortization:* postings
                        if not (original_account.startswith('Equity:Amortization:') and posting.units.number > 0):
                            continue
                        
                        # Transform to Expenses:* for pattern matching
                        transformed_account = self._transform_amortization_account(
                            original_account,
                            posting.units.number
                        )
                        
                        best_pattern = None
                        best_len = -1
                        
                        for pattern in patterns:
                            if matches_pattern(transformed_account, pattern):
                                if len(pattern) > best_len:
                                    best_pattern = pattern
                                    best_len = len(pattern)
                        
                        if best_pattern:
                            if original_account not in amortization_details[best_pattern]:
                                amortization_details[best_pattern][original_account] = Inventory()
                            amortization_details[best_pattern][original_account].add_amount(posting.units)
        
        return amortization_details

    def _accumulate_entry(self, entry, pattern, inventory):
        # Skip amortization-generated transactions
        if self._is_amortization_transaction(entry):
            return
        
        for posting in entry.postings:
            # Transform account name for amortization entries
            account = self._transform_amortization_account(
                posting.account, 
                posting.units.number
            )
            
            if matches_pattern(account, pattern):
                inventory.add_amount(posting.units)

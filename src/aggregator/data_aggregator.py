"""Data aggregation module for processing and analyzing bank data."""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass
from ..data.bank_connector import BankAccount, BankTransaction

logger = logging.getLogger(__name__)


@dataclass
class AccountSummary:
    """Summary information for a single account."""
    bank_name: str
    account_id: str
    account_name: str
    account_type: str
    balance: float
    currency: str
    transaction_count: int
    last_transaction_date: Optional[datetime] = None
    # Non-serialized reference back to the full account for rich display
    _source: Optional[BankAccount] = None


@dataclass
class BankSummary:
    """Summary information for a single bank."""
    bank_name: str
    total_accounts: int
    total_balance: float
    currency: str
    account_summaries: List[AccountSummary]


@dataclass
class FinancialSummary:
    """Overall financial summary across all banks."""
    total_balance: float
    currency: str
    total_accounts: int
    total_banks: int
    bank_summaries: List[BankSummary]
    category_spending: Dict[str, float]
    monthly_spending: Dict[str, float]
    last_updated: datetime


class DataAggregator:
    """Aggregates and processes financial data from multiple bank accounts."""
    
    def __init__(self):
        """Initialize the data aggregator."""
        logger.info("Data Aggregator initialized")
    
    def aggregate(self, bank_accounts_data: Dict[str, List[BankAccount]]) -> FinancialSummary:
        """
        Aggregate financial data from all bank accounts.
        
        Args:
            bank_accounts_data: Dictionary mapping bank names to lists of accounts.
            
        Returns:
            FinancialSummary containing aggregated financial information.
        """
        logger.info("Starting data aggregation...")
        
        bank_summaries = []
        total_balance = 0.0
        total_accounts = 0
        
        # Process each bank
        for bank_name, accounts in bank_accounts_data.items():
            if not accounts:
                logger.warning(f"No accounts found for {bank_name}")
                continue
            
            bank_summary = self._create_bank_summary(bank_name, accounts)
            bank_summaries.append(bank_summary)
            
            # Add to totals (assuming all accounts are in EUR for simplicity)
            total_balance += bank_summary.total_balance
            total_accounts += bank_summary.total_accounts
        
        # Create overall financial summary
        financial_summary = FinancialSummary(
            total_balance=total_balance,
            currency='EUR',  # Assuming EUR as base currency
            total_accounts=total_accounts,
            total_banks=len([bs for bs in bank_summaries if bs.total_accounts > 0]),
            bank_summaries=bank_summaries,
            category_spending={},  # Will be populated when transaction data is available
            monthly_spending={},   # Will be populated when transaction data is available
            last_updated=datetime.now()
        )
        
        logger.info(f"Aggregation complete: {financial_summary.total_accounts} accounts across {financial_summary.total_banks} banks")
        return financial_summary
    
    def aggregate_transactions(
        self, 
        transactions: List[BankTransaction]
    ) -> Dict[str, Any]:
        """
        Aggregate and analyze transaction data.
        
        Args:
            transactions: List of bank transactions.
            
        Returns:
            Dictionary containing transaction analysis.
        """
        if not transactions:
            return {
                'total_transactions': 0,
                'total_spent': 0.0,
                'total_received': 0.0,
                'categories': {},
                'monthly_breakdown': {},
                'average_transaction': 0.0
            }
        
        # Initialize aggregation variables
        total_spent = 0.0
        total_received = 0.0
        category_totals = defaultdict(float)
        monthly_totals = defaultdict(float)
        
        # Process each transaction
        for transaction in transactions:
            # Track spending vs income
            if transaction.amount < 0:  # Debit/expense
                total_spent += abs(transaction.amount)
            else:  # Credit/income
                total_received += transaction.amount
            
            # Category breakdown
            category_totals[transaction.category] += abs(transaction.amount)
            
            # Monthly breakdown
            month_key = transaction.date.strftime('%Y-%m')
            monthly_totals[month_key] += abs(transaction.amount)
        
        # Calculate average transaction amount
        avg_transaction = (total_spent + total_received) / len(transactions) if transactions else 0.0
        
        analysis = {
            'total_transactions': len(transactions),
            'total_spent': total_spent,
            'total_received': total_received,
            'net_flow': total_received - total_spent,
            'categories': dict(category_totals),
            'monthly_breakdown': dict(monthly_totals),
            'average_transaction': avg_transaction
        }
        
        logger.info(f"Transaction analysis complete: {len(transactions)} transactions processed")
        return analysis
    
    def _create_bank_summary(self, bank_name: str, accounts: List[BankAccount]) -> BankSummary:
        """
        Create a summary for a single bank.
        
        Args:
            bank_name: Name of the bank.
            accounts: List of accounts for this bank.
            
        Returns:
            BankSummary object.
        """
        if not accounts:
            return BankSummary(
                bank_name=bank_name,
                total_accounts=0,
                total_balance=0.0,
                currency='EUR',
                account_summaries=[]
            )
        
        account_summaries = []
        total_balance = 0.0
        
        for account in accounts:
            # Create account summary
            account_summary = AccountSummary(
                bank_name=account.bank_name,
                account_id=account.account_id,
                account_name=account.account_name,
                account_type=account.account_type,
                balance=account.balance,
                currency=account.currency,
                transaction_count=len(getattr(account, 'transactions', []) or []),
                last_transaction_date=(getattr(account, 'transactions', [None]) or [None])[0].date if getattr(account, 'transactions', None) else None,
                _source=account,
            )
            
            account_summaries.append(account_summary)
            total_balance += account.balance
        
        bank_summary = BankSummary(
            bank_name=bank_name,
            total_accounts=len(accounts),
            total_balance=total_balance,
            currency=accounts[0].currency,  # Assuming all accounts have same currency
            account_summaries=account_summaries
        )
        
        logger.info(f"Created summary for {bank_name}: {len(accounts)} accounts, total balance: {total_balance}")
        return bank_summary
    
    def calculate_net_worth_trend(
        self, 
        historical_data: List[FinancialSummary]
    ) -> Dict[str, Any]:
        """
        Calculate net worth trend over time.
        
        Args:
            historical_data: List of historical financial summaries.
            
        Returns:
            Dictionary containing trend analysis.
        """
        if len(historical_data) < 2:
            return {
                'trend': 'insufficient_data',
                'change': 0.0,
                'change_percentage': 0.0,
                'data_points': len(historical_data)
            }
        
        # Sort by date
        sorted_data = sorted(historical_data, key=lambda x: x.last_updated)
        
        # Calculate change from first to last
        first_balance = sorted_data[0].total_balance
        last_balance = sorted_data[-1].total_balance
        
        change = last_balance - first_balance
        change_percentage = (change / first_balance * 100) if first_balance != 0 else 0.0
        
        # Determine trend
        if change > 0:
            trend = 'increasing'
        elif change < 0:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'change': change,
            'change_percentage': change_percentage,
            'first_balance': first_balance,
            'last_balance': last_balance,
            'data_points': len(historical_data),
            'time_period': {
                'start': sorted_data[0].last_updated,
                'end': sorted_data[-1].last_updated
            }
        }
    
    def get_spending_insights(
        self, 
        transactions: List[BankTransaction],
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Generate spending insights from transaction data.
        
        Args:
            transactions: List of transactions to analyze.
            days_back: Number of days to analyze.
            
        Returns:
            Dictionary containing spending insights.
        """
        # Filter transactions to the specified time period
        cutoff_date = datetime.now() - timedelta(days=days_back)
        recent_transactions = [
            tx for tx in transactions 
            if tx.date >= cutoff_date and tx.amount < 0  # Only expenses
        ]
        
        if not recent_transactions:
            return {
                'period_days': days_back,
                'total_spending': 0.0,
                'transaction_count': 0,
                'daily_average': 0.0,
                'top_categories': [],
                'largest_expense': None
            }
        
        # Calculate spending metrics
        total_spending = sum(abs(tx.amount) for tx in recent_transactions)
        daily_average = total_spending / days_back
        
        # Category analysis
        category_spending = defaultdict(float)
        for tx in recent_transactions:
            category_spending[tx.category] += abs(tx.amount)
        
        # Sort categories by spending
        top_categories = sorted(
            category_spending.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        # Find largest single expense
        largest_expense = max(recent_transactions, key=lambda x: abs(x.amount))
        
        insights = {
            'period_days': days_back,
            'total_spending': total_spending,
            'transaction_count': len(recent_transactions),
            'daily_average': daily_average,
            'top_categories': top_categories,
            'largest_expense': {
                'amount': abs(largest_expense.amount),
                'description': largest_expense.description,
                'date': largest_expense.date.strftime('%Y-%m-%d'),
                'category': largest_expense.category
            }
        }
        
        logger.info(f"Generated spending insights for {days_back} days: {total_spending:.2f} EUR spent")
        return insights
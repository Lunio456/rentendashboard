"""Console display module for rendering financial dashboard to terminal."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..aggregator.data_aggregator import FinancialSummary, BankSummary, AccountSummary

logger = logging.getLogger(__name__)


class ConsoleDisplay:
    """Handles console-based display of financial dashboard data."""

    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors
        self._setup_colors()
        logger.info("Console Display initialized")

    def _setup_colors(self) -> None:
        if self.use_colors:
            self.colors = {
                'reset': '\033[0m',
                'bold': '\033[1m',
                'green': '\033[92m',
                'red': '\033[91m',
                'yellow': '\033[93m',
                'blue': '\033[94m',
                'cyan': '\033[96m',
                'white': '\033[97m',
                'gray': '\033[90m',
            }
        else:
            self.colors = {k: '' for k in ['reset', 'bold', 'green', 'red', 'yellow', 'blue', 'cyan', 'white', 'gray']}

    def show_dashboard(self, financial_summary: FinancialSummary) -> None:
        self._print_header()
        self._print_overall_summary(financial_summary)
        self._print_bank_summaries(financial_summary.bank_summaries)
        self._print_account_details(financial_summary.bank_summaries)
        self._print_footer(financial_summary.last_updated)

    def _print_header(self) -> None:
        print(f"{self.colors['cyan']}{self.colors['bold']}")
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║                    RENTENDASHBOARD                           ║")
        print("║                  Financial Overview                          ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print(self.colors['reset'])

    def _print_overall_summary(self, summary: FinancialSummary) -> None:
        print(f"\n{self.colors['bold']}📊 OVERALL FINANCIAL SUMMARY{self.colors['reset']}")
        print("═" * 60)
        balance_color = self.colors['green'] if summary.total_balance >= 0 else self.colors['red']
        print(f"💰 Total Balance:     {balance_color}{summary.total_balance:,.2f} {summary.currency}{self.colors['reset']}")
        print(f"🏦 Connected Banks:   {self.colors['blue']}{summary.total_banks}{self.colors['reset']}")
        print(f"🏛️  Total Accounts:    {self.colors['blue']}{summary.total_accounts}{self.colors['reset']}")
        print(f"🕒 Last Updated:      {self.colors['gray']}{summary.last_updated.strftime('%Y-%m-%d %H:%M:%S')}{self.colors['reset']}")

    def _print_bank_summaries(self, bank_summaries: List[BankSummary]) -> None:
        if not bank_summaries:
            print(f"\n{self.colors['yellow']}⚠️  No bank data available{self.colors['reset']}")
            return
        print(f"\n{self.colors['bold']}🏦 BANK SUMMARIES{self.colors['reset']}")
        print("═" * 60)
        for i, bank in enumerate(bank_summaries, 1):
            status_color = self.colors['green'] if bank.total_accounts > 0 else self.colors['red']
            status = "✅ Connected" if bank.total_accounts > 0 else "❌ No accounts"
            balance_color = self.colors['green'] if bank.total_balance >= 0 else self.colors['red']
            print(f"\n{i}. {self.colors['bold']}{bank.bank_name.upper()}{self.colors['reset']}")
            print(f"   Status:    {status_color}{status}{self.colors['reset']}")
            print(f"   Accounts:  {self.colors['blue']}{bank.total_accounts}{self.colors['reset']}")
            print(f"   Balance:   {balance_color}{bank.total_balance:,.2f} {bank.currency}{self.colors['reset']}")

    def _print_account_details(self, bank_summaries: List[BankSummary]) -> None:
        print(f"\n{self.colors['bold']}💳 ACCOUNT DETAILS{self.colors['reset']}")
        print("═" * 60)
        for bank in bank_summaries:
            if not bank.account_summaries:
                continue
            print(f"\n{self.colors['cyan']}{bank.bank_name}{self.colors['reset']}")
            print("-" * len(bank.bank_name))
            print(f"{self.colors['bold']}{'Account Name':<20} {'Type':<12} {'Balance':>15}{self.colors['reset']}")
            print("-" * 50)
            for account in bank.account_summaries:
                balance_color = self.colors['green'] if account.balance >= 0 else self.colors['red']
                balance_str = f"{account.balance:,.2f} {account.currency}"
                print(f"{account.account_name:<20} {account.account_type:<12} {balance_color}{balance_str:>15}{self.colors['reset']}")
                # Positions
                acct_obj = getattr(account, '_source', None)
                if acct_obj and getattr(acct_obj, 'positions', None):
                    print(f"   {self.colors['bold']}Positions:{self.colors['reset']}")
                    for pos in acct_obj.positions[:10]:
                        print(f"   - {pos}")
                # Recent transactions
                if acct_obj and getattr(acct_obj, 'transactions', None):
                    print(f"   {self.colors['bold']}Recent transactions:{self.colors['reset']}")
                    for tx in acct_obj.transactions[:10]:
                        sign = '-' if (tx.amount or 0) < 0 else '+'
                        amt_color = self.colors['red'] if sign == '-' else self.colors['green']
                        dt = tx.date.strftime('%Y-%m-%d') if getattr(tx, 'date', None) else ''
                        desc = tx.security_name or tx.description or ''
                        extra = f" x{tx.quantity}" if getattr(tx, 'quantity', None) else ''
                        print(f"   - {dt} {desc}{extra} {amt_color}{tx.amount:,.2f} {tx.currency}{self.colors['reset']}")

    def _print_footer(self, last_updated: datetime) -> None:
        print(f"\n{self.colors['gray']}" + "─" * 60)
        print(f"Dashboard generated at {last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"RentenDashboard - Secure Bank Account Integration{self.colors['reset']}\n")
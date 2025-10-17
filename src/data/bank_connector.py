"""Bank API connector for retrieving account and transaction data."""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import aiohttp
import os
from pathlib import Path
from ..auth.oauth_manager import OAuthManager

logger = logging.getLogger(__name__)


class BankAccount:
    """Represents a bank account with its associated data."""
    
    def __init__(self, account_data: Dict[str, Any]):
        """Initialize bank account from API data."""
        self.account_id = account_data.get('id', '')
        self.account_number = account_data.get('account_number', '')
        self.account_name = account_data.get('name', 'Unknown Account')
        self.account_type = account_data.get('type', 'checking')
        self.balance = float(account_data.get('balance', 0.0))
        self.currency = account_data.get('currency', 'EUR')
        self.bank_name = account_data.get('bank_name', 'Unknown Bank')
        self.last_updated = datetime.now()
        # Detailed data
        self.positions: List["Position"] = account_data.get('positions', [])
        self.transactions: List["BankTransaction"] = account_data.get('transactions', [])
        
    def __str__(self) -> str:
        return f"{self.bank_name} - {self.account_name} ({self.account_type}): {self.balance} {self.currency}"


class BankTransaction:
    """Represents a bank transaction."""
    
    def __init__(self, transaction_data: Dict[str, Any]):
        """Initialize transaction from API data."""
        self.transaction_id = transaction_data.get('id', '')
        self.account_id = transaction_data.get('account_id', '')
        self.amount = float(transaction_data.get('amount', 0.0))
        self.currency = transaction_data.get('currency', 'EUR')
        self.description = transaction_data.get('description', '')
        # Accept both YYYY-MM-DD and ISO with time
        _date = transaction_data.get('date') or datetime.now().date().isoformat()
        try:
            self.date = datetime.fromisoformat(_date)
        except Exception:
            # Fallback for YYYY-MM-DD
            try:
                self.date = datetime.strptime(_date, '%Y-%m-%d')
            except Exception:
                self.date = datetime.now()
        self.category = transaction_data.get('category', 'other')
        self.transaction_type = transaction_data.get('type', 'debit')
        # Optional securities-specific fields
        self.security_name: Optional[str] = transaction_data.get('security_name')
        self.isin: Optional[str] = transaction_data.get('isin')
        self.quantity: Optional[float] = transaction_data.get('quantity')
        self.price: Optional[float] = transaction_data.get('price')
        self.price_currency: Optional[str] = transaction_data.get('price_currency')


class Position:
    """Represents a portfolio position (holding)."""
    def __init__(self, data: Dict[str, Any]):
        self.name: str = data.get('name', 'Security')
        self.isin: Optional[str] = data.get('isin')
        self.wkn: Optional[str] = data.get('wkn')
        self.quantity: float = float(data.get('quantity', 0.0))
        self.price: Optional[float] = data.get('price')
        self.currency: str = data.get('currency', 'EUR')
    
    def __str__(self) -> str:
        value = None
        if self.price is not None:
            value = (self.price or 0.0) * (self.quantity or 0.0)
        value_str = f" | Value: {value:,.2f} {self.currency}" if value is not None else ""
        return f"{self.name} ({self.isin or self.wkn or 'N/A'}) | Qty: {self.quantity} @ {self.price or '-'} {self.currency}{value_str}"


class BankConnector:
    """Handles connections to bank APIs and data retrieval."""
    
    def __init__(self, oauth_manager: OAuthManager, banks_config: Dict[str, Any]):
        """
        Initialize bank connector.
        
        Args:
            oauth_manager: OAuth manager for authentication.
            banks_config: Configuration for all supported banks.
        """
        self.oauth_manager = oauth_manager
        self.banks_config = banks_config
        self.timeout = aiohttp.ClientTimeout(total=30)
        
        logger.info("Bank Connector initialized")
    
    async def connect_all_accounts(self) -> Dict[str, List[BankAccount]]:
        """
        Connect to all configured banks and retrieve account information.
        
        Returns:
            Dictionary mapping bank names to lists of accounts.
        """
        logger.info("Connecting to all configured banks...")
        
        all_accounts = {}
        
        # Process each configured bank
        for bank_name, bank_config in self.banks_config.items():
            try:
                logger.info(f"Connecting to {bank_name}...")

                # Ensure we have a valid token
                await self._ensure_valid_token(bank_name, bank_config)

                # Retrieve accounts for this bank
                accounts = await self._fetch_accounts(bank_name, bank_config)
                all_accounts[bank_name] = accounts

                logger.info(f"Successfully connected to {bank_name}, found {len(accounts)} accounts")

            except Exception as e:
                logger.error(f"Failed to connect to {bank_name}: {e}")
                # Continue with other banks even if one fails
                all_accounts[bank_name] = []
        
        total_accounts = sum(len(accounts) for accounts in all_accounts.values())
        logger.info(f"Connected to {len(all_accounts)} banks, total accounts: {total_accounts}")
        
        return all_accounts
    
    async def fetch_transactions(
        self, 
        account: BankAccount, 
        days_back: int = 30
    ) -> List[BankTransaction]:
        """
        Fetch transactions for a specific account.
        
        Args:
            account: Bank account to fetch transactions for.
            days_back: Number of days to look back for transactions.
            
        Returns:
            List of transactions.
        """
        bank_config = self._get_bank_config_for_account(account)
        if not bank_config:
            logger.error(f"No bank configuration found for account {account.account_id}")
            return []
        
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Get access token using token key derived from bank config
            token_bank_config = self._get_bank_config_for_account(account)
            token_key = token_bank_config.get('name') or account.bank_name if token_bank_config else account.bank_name
            access_token = self.oauth_manager.get_access_token(token_key)
            if not access_token:
                logger.error(f"No valid token for {token_key}")
                return []
            
            # Prepare API request
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
            }
            
            # In a real implementation, this would be the actual bank's API endpoint
            transactions_url = f"{bank_config['api_base_url']}/accounts/{account.account_id}/transactions"
            params = {
                'from_date': start_date.isoformat(),
                'to_date': end_date.isoformat(),
            }
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(transactions_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        transactions_data = await response.json()
                        
                        # Parse transactions
                        transactions = []
                        for tx_data in transactions_data.get('transactions', []):
                            tx_data['account_id'] = account.account_id
                            transaction = BankTransaction(tx_data)
                            transactions.append(transaction)
                        
                        logger.info(f"Fetched {len(transactions)} transactions for account {account.account_id}")
                        return transactions
                    else:
                        logger.error(f"Failed to fetch transactions: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error fetching transactions for account {account.account_id}: {e}")
            return []
    
    async def _ensure_valid_token(self, bank_name: str, bank_config: Dict[str, Any]) -> None:
        """
        Ensure we have a valid OAuth token for the bank.
        
        Args:
            bank_name: Name of the bank.
            bank_config: Bank configuration.
        """
        token_key = bank_config.get('name') or bank_name
        if not self.oauth_manager.is_token_valid(token_key):
            logger.info(f"No valid token found for {token_key} (bank '{bank_name}'), initiating OAuth flow...")
            
            # For development, use simulated OAuth flow
            # In production, this would involve actual user authentication
            await self.oauth_manager.simulate_oauth_flow(token_key, bank_config)
    
    async def _fetch_accounts(self, bank_name: str, bank_config: Dict[str, Any]) -> List[BankAccount]:
        """
        Fetch accounts from a specific bank.
        
        Args:
            bank_name: Name of the bank.
            bank_config: Bank configuration.
            
        Returns:
            List of bank accounts.
        """
        token_key = bank_config.get('name') or bank_name
        access_token = self.oauth_manager.get_access_token(token_key)
        if not access_token:
            logger.error(f"No valid token for {token_key} (bank '{bank_name}')")
            return []
        
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
            }

            # Commerzbank sandbox: GET {api_base_url}/accounts
            accounts_url = f"{bank_config['api_base_url']}/accounts"

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(accounts_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        accounts: List[BankAccount] = []
                        for acc in data.get('securitiesAccountIds', []):
                            # acc is AccountId with pseudonymizedAccountId and securitiesAccountId
                            pseudo_id = acc.get('pseudonymizedAccountId') or acc.get('securitiesAccountId')
                            acc_id = pseudo_id
                            if not acc_id:
                                continue
                            # Fetch portfolio to derive balance (totalValue)
                            portfolio_url = f"{bank_config['api_base_url']}/accounts/{acc_id}/portfolio"
                            balance = 0.0
                            currency = 'EUR'
                            positions: List[Position] = []
                            try:
                                eff_date = datetime.now().date().isoformat()
                                async with session.get(portfolio_url, headers=headers, params={'effectiveDate': eff_date}) as p_resp:
                                    if p_resp.status == 200:
                                        p = await p_resp.json()
                                        # Save raw portfolio JSON for debugging/inspection
                                        try:
                                            out_dir = Path('artifacts/portfolio')
                                            out_dir.mkdir(parents=True, exist_ok=True)
                                            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                                            out_path = out_dir / f"{acc_id}_portfolio_{ts}.json"
                                            import json as _json
                                            out_path.write_text(_json.dumps(p, indent=2))
                                            logger.info(f"Saved portfolio JSON to {out_path}")
                                        except Exception as fs_err:
                                            logger.warning(f"Failed to save portfolio JSON for {acc_id}: {fs_err}")
                                        tv = p.get('totalValue') or {}
                                        balance = float(tv.get('amount', 0.0) or 0.0)
                                        currency = tv.get('currency', 'EUR')
                                        # Parse positions
                                        for pos in p.get('positions', []) or []:
                                            positions.append(self._parse_position(pos))
                                        logger.info(f"Account {acc_id}: parsed {len(positions)} positions from portfolio")
                                    else:
                                        logger.warning(f"Portfolio API returned {p_resp.status} for {acc_id}")
                            except Exception as pe:
                                logger.warning(f"Portfolio fetch failed for {acc_id}: {pe}")

                            account_data = {
                                'id': str(acc_id),  # use pseudonymized id for API calls
                                'account_number': str(acc.get('securitiesAccountId') or acc_id),
                                'name': f'Securities {acc_id}',
                                'type': 'securities',
                                'balance': balance,
                                'currency': currency,
                                # Keep the bank_name aligned with banks_config key for lookups
                                'bank_name': bank_name,
                                'positions': positions,
                            }
                            account_obj = BankAccount(account_data)
                            # Fetch recent transactions (last 30 days, limit 25)
                            try:
                                account_obj.transactions = await self._fetch_transactions_for_account(session, bank_config, account_obj.account_id, access_token, days_back=30, limit=25)
                                logger.info(f"Account {acc_id}: fetched {len(account_obj.transactions)} recent transactions")
                            except Exception as te:
                                logger.warning(f"Transactions fetch failed for {acc_id}: {te}")
                            accounts.append(account_obj)
                        if accounts:
                            return accounts
                        # Fallback to mock if empty
                        return await self._get_mock_accounts(bank_name, bank_config)
                    else:
                        logger.warning(f"Accounts API returned {response.status}, using mock data")
                        return await self._get_mock_accounts(bank_name, bank_config)

        except Exception as e:
            logger.error(f"Error fetching accounts from {bank_name}: {e}")
            return await self._get_mock_accounts(bank_name, bank_config)

    def _parse_position(self, pos: Dict[str, Any]) -> Position:
        """Parse a portfolio position from API JSON into Position model."""
        md = (pos.get('masterdata') or {}).get('securitiesMasterdata') or {}
        quantity = (pos.get('quantity') or {}).get('amount') or 0.0
        current_price = (pos.get('currentPrice') or {}).get('amount')
        price_currency = (pos.get('currentPrice') or {}).get('currency') or 'EUR'
        return Position({
            'name': md.get('name') or 'Security',
            'isin': md.get('isin'),
            'wkn': md.get('wkn'),
            'quantity': float(quantity or 0.0),
            'price': float(current_price) if current_price is not None else None,
            'currency': price_currency,
        })

    async def _fetch_transactions_for_account(
        self,
        session: aiohttp.ClientSession,
        bank_config: Dict[str, Any],
        account_id: str,
        access_token: str,
        days_back: int = 30,
        limit: int = 25,
    ) -> List["BankTransaction"]:
        """Fetch recent transactions for a securities account using the sandbox schema."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
        }
        tx_url = f"{bank_config['api_base_url']}/accounts/{account_id}/transactions"
        params = {
            'fromTradingDate': start_date.isoformat(),
            'toTradingDate': end_date.isoformat(),
            'limit': str(limit),
        }
        txs: List[BankTransaction] = []
        async with session.get(tx_url, headers=headers, params=params) as resp:
            if resp.status != 200:
                return txs
            data = await resp.json()
            for t in data.get('transactions', []) or []:
                md = t.get('masterdata') or {}
                sec_name = md.get('name') or ''
                isin = md.get('isin')
                size = t.get('size') or {}
                price = (t.get('price') or {}).get('amount')
                price_currency = (t.get('price') or {}).get('currency') or 'EUR'
                amt = (t.get('actualAmount') or {}).get('amount') or 0.0
                amt_curr = (t.get('actualAmount') or {}).get('currency') or price_currency
                tx_type = (t.get('transactionType') or {}).get('name') or 'transaction'
                date_str = t.get('tradingDate') or t.get('bookingDate')
                txs.append(BankTransaction({
                    'id': t.get('transactionId') or '',
                    'account_id': account_id,
                    'amount': float(amt or 0.0),
                    'currency': amt_curr,
                    'description': sec_name,
                    'date': date_str,
                    'category': 'securities',
                    'type': tx_type,
                    'security_name': sec_name,
                    'isin': isin,
                    'quantity': float(size.get('amount') or 0.0) if isinstance(size, dict) else None,
                    'price': float(price) if price is not None else None,
                    'price_currency': price_currency,
                }))
        return txs

    async def _get_mock_accounts(self, bank_name: str, bank_config: Dict[str, Any]) -> List[BankAccount]:
        """
        Generate mock account data for development/testing.
        
        Args:
            bank_name: Name of the bank.
            bank_config: Bank configuration.
            
        Returns:
            List of mock bank accounts.
        """
        logger.warning(f"SIMULATION: Using mock data for {bank_name} - NOT FOR PRODUCTION")
        
        # Generate mock account data
        mock_accounts_data = [
            {
                'id': f'{bank_name}_checking_001',
                'account_number': '****1234',
                'name': 'Primary Checking',
                'type': 'checking',
                'balance': 2547.83,
                'currency': 'EUR',
                'bank_name': bank_name,
            },
            {
                'id': f'{bank_name}_savings_001',
                'account_number': '****5678',
                'name': 'Savings Account',
                'type': 'savings',
                'balance': 15420.91,
                'currency': 'EUR',
                'bank_name': bank_name,
            }
        ]
        
        accounts = [BankAccount(acc_data) for acc_data in mock_accounts_data]
        logger.info(f"Generated {len(accounts)} mock accounts for {bank_name}")
        
        return accounts
    
    def _get_bank_config_for_account(self, account: BankAccount) -> Optional[Dict[str, Any]]:
        """
        Get bank configuration for a specific account.
        
        Args:
            account: Bank account.
            
        Returns:
            Bank configuration or None if not found.
        """
        return self.banks_config.get(account.bank_name)
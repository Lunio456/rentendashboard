"""
RentenDashboard - Bank Account OAuth Integration and Financial Data Aggregation

This application connects to bank accounts using OAuth authentication,
retrieves financial data, and displays it in a dashboard format.
Priority: Bank account connectivity with console output.
"""

import asyncio
import logging
from src.auth.oauth_manager import OAuthManager
from src.data.bank_connector import BankConnector
from src.aggregator.data_aggregator import DataAggregator
from src.dashboard.console_display import ConsoleDisplay
from config.settings import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Main application entry point."""
    try:
        logger.info("Starting RentenDashboard application...")
        
        # Load configuration
        config = load_config()
        
        # Initialize components
        oauth_manager = OAuthManager(config['oauth'])
        bank_connector = BankConnector(oauth_manager, config['banks'])
        aggregator = DataAggregator()
        display = ConsoleDisplay()
        
        # If real OAuth client creds exist, prefer authorization code flow over simulation
        primary = config['banks']['primary']
        app_cfg = config['app']
        if primary.get('client_id') and primary.get('client_secret') and app_cfg.get('tls_cert_path') and app_cfg.get('tls_key_path'):
            try:
                await oauth_manager.authorization_code_flow(primary, app_cfg)
            except Exception as e:
                logger.warning(f"Auth code flow failed ({e}); continuing with simulated token for development")
                await oauth_manager.simulate_oauth_flow(primary['name'], primary)
        else:
            await oauth_manager.simulate_oauth_flow(primary['name'], primary)

        # Connect to bank accounts
        logger.info("Initiating bank account connections...")
        bank_data = await bank_connector.connect_all_accounts()
        
        # Aggregate data
        logger.info("Aggregating financial data...")
        aggregated_data = aggregator.aggregate(bank_data)
        
        # Display results
        logger.info("Displaying dashboard data...")
        display.show_dashboard(aggregated_data)
        
        logger.info("RentenDashboard completed successfully!")
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
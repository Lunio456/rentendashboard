# RentenDashboard

A Python application for connecting to bank accounts using OAuth authentication and displaying aggregated financial data in a dashboard.

## Features

- 🔐 Secure OAuth 2.0 authentication for bank accounts
- 🏦 Multi-bank API integration
- 📊 Financial data aggregation and processing
- 🖥️ Console-based dashboard (initial implementation)
- 📈 Account balance and transaction monitoring

## Prerequisites

- Python 3.8 or higher
- Bank API credentials (OAuth 2.0 compatible)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Lunio456/rentendashboard.git
cd rentendashboard
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure your bank API credentials:
```bash
cp .env.example .env
# Edit .env with your actual API credentials
```

## Configuration

Create a `.env` file in the project root with your bank API credentials:

```env
# Bank API Configuration
BANK_CLIENT_ID=your_client_id
BANK_CLIENT_SECRET=your_client_secret
BANK_REDIRECT_URI=http://localhost:8080/callback

# Security
SECRET_KEY=your_secret_key_for_token_encryption

# Logging
LOG_LEVEL=INFO
```

## Usage

Run the application:

```bash
python main.py
```

The application will:
1. Initiate OAuth authentication with configured banks
2. Retrieve account information and transaction data
3. Aggregate the financial data
4. Display results in the console

## Project Structure

```
rentendashboard/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment configuration template
├── config/                # Configuration management
│   ├── __init__.py
│   └── settings.py
├── src/                   # Source code
│   ├── __init__.py
│   ├── auth/              # OAuth authentication
│   │   ├── __init__.py
│   │   └── oauth_manager.py
│   ├── data/              # Bank data connectivity
│   │   ├── __init__.py
│   │   └── bank_connector.py
│   ├── aggregator/        # Data aggregation
│   │   ├── __init__.py
│   │   └── data_aggregator.py
│   └── dashboard/         # Display components
│       ├── __init__.py
│       └── console_display.py
└── tests/                 # Test suite
    ├── __init__.py
    ├── test_oauth.py
    ├── test_bank_connector.py
    └── test_aggregator.py
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black .
flake8 .
```

### Type Checking

```bash
mypy .
```

## Security

- All OAuth tokens are encrypted using industry-standard cryptography
- Environment variables are used for sensitive configuration
- No credentials are stored in code or logs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Roadmap

- [ ] Web-based dashboard interface
- [ ] Support for additional bank APIs
- [ ] Real-time data synchronization
- [ ] Advanced financial analytics
- [ ] Data export functionality
# Token Holder Rewards Bot

A modern, minimal Telegram bot that rewards token holders for diamond handing (holding without selling) for at least 30 days.

## Features

### 🎯 Holder of the Month Reward System
- Tracks all wallets that bought the token
- Only wallets that held for at least 30 days without selling are eligible
- Monthly random winner selection from eligible holders
- Admin panel for manual reward distribution
- Winner announcements in Telegram group

### 📊 Leaderboard & Motivation
- Public leaderboard showing top holders
- Displays wallet address, holding days, and current USD value
- Users can check their rank and progress toward eligibility
- Real-time balance tracking

### 🔧 Admin Panel (Restricted Access)
- View all holders and their holding duration
- Trigger monthly winner selection
- Update balances from blockchain
- View statistics and recent winners
- Manage bot settings

### 🎨 Modern UI Design
- Clean, minimal interface with inline keyboards
- User-friendly navigation flow
- Responsive button layouts
- Progress indicators and status displays

## Tech Stack

- **Backend**: Python 3.9+ with aiogram framework
- **Database**: PostgreSQL (Railway.com hosted)
- **Blockchain API**: Tatum API for transaction monitoring
- **Hosting**: Railway.com
- **Storage**: Async SQLAlchemy with Alembic migrations

## Quick Setup

### 1. Environment Variables

Create a `.env` file (copy from `env.example`):

```bash
# Telegram Bot Configuration
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_USER_IDS=123456789,987654321

# Database Configuration (Railway Postgres)
DATABASE_URL=postgresql://username:password@host:port/database

# Tatum API Configuration
TATUM_API_KEY=your_tatum_api_key_here

# Token Configuration
TOKEN_CONTRACT_ADDRESS=your_token_contract_address_here
BLOCKCHAIN_NETWORK=ethereum-sepolia  # or mainnet, polygon, etc.

# Application Settings
PORT=8000
ENVIRONMENT=production
```

### 2. Get Required API Keys

#### Telegram Bot Token
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token

#### Tatum API Key
1. Sign up at [Tatum.io](https://tatum.io)
2. Get your API key from the dashboard
3. Choose the appropriate blockchain network

#### Admin User IDs
1. Message [@userinfobot](https://t.me/userinfobot) to get your Telegram user ID
2. Add multiple admin IDs separated by commas

### 3. Railway Deployment

#### Method 1: Deploy Button
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/deployment-template)

#### Method 2: Manual Deployment
1. Fork this repository
2. Connect your Railway account to GitHub
3. Create a new Railway project
4. Add a PostgreSQL database
5. Configure environment variables
6. Deploy!

#### Method 3: Railway CLI
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init

# Add PostgreSQL database
railway add postgresql

# Set environment variables
railway variables set BOT_TOKEN=your_token_here
railway variables set TATUM_API_KEY=your_key_here
# ... set other variables

# Deploy
railway up
```

### 4. Local Development

```bash
# Clone the repository
git clone <repository-url>
cd rewards-tg-app

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp env.example .env
# Edit .env with your values

# Run the bot
python main.py
```

## Project Structure

```
rewards-tg-app/
├── main.py                 # Application entry point
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── Procfile              # Railway process configuration
├── railway.json          # Railway deployment settings
├── bot/                  # Bot logic
│   ├── __init__.py
│   ├── bot.py           # Bot setup and configuration
│   ├── keyboards.py     # Inline keyboard layouts
│   ├── utils.py         # Utility functions
│   └── handlers/        # Message and callback handlers
│       ├── __init__.py
│       ├── user_handlers.py    # User interaction handlers
│       └── admin_handlers.py   # Admin panel handlers
├── database/            # Database layer
│   ├── __init__.py
│   ├── models.py        # SQLAlchemy models
│   └── database.py      # Database operations
└── blockchain/          # Blockchain integration
    ├── __init__.py
    ├── tatum_client.py  # Tatum API client
    └── monitor.py       # Blockchain monitoring service
```

## Key Features Explained

### Holder Tracking
- Automatically tracks token purchases and sales
- Monitors wallet balances in real-time
- Marks holders as ineligible if they sell
- Calculates holding periods from first purchase

### Eligibility System
- Minimum 30-day holding period requirement
- Must maintain positive token balance
- No selling allowed (marks as ineligible)
- Automatic eligibility checking

### Winner Selection
- Random selection from eligible holders
- Prevents duplicate winners per month
- Admin confirmation required
- Comprehensive winner tracking

### Admin Controls
- Restricted access by Telegram user ID
- Complete holder management
- Manual balance updates
- Statistics and monitoring tools

## Configuration Options

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `BOT_TOKEN` | Telegram bot token | Yes | - |
| `ADMIN_USER_IDS` | Comma-separated admin user IDs | Yes | - |
| `DATABASE_URL` | PostgreSQL connection string | Yes | - |
| `TATUM_API_KEY` | Tatum API key | Yes | - |
| `TOKEN_CONTRACT_ADDRESS` | Token contract address | Yes | - |
| `BLOCKCHAIN_NETWORK` | Blockchain network name | No | ethereum-sepolia |
| `PORT` | Server port | No | 8000 |
| `ENVIRONMENT` | Environment mode | No | development |

### Supported Networks
- Ethereum (mainnet, sepolia)
- Polygon (mainnet)
- BSC (mainnet, testnet)

## Usage Guide

### For Users
1. Start the bot with `/start`
2. Link your wallet address
3. Buy and hold tokens for 30+ days
4. Check your status and leaderboard rank
5. Get automatically entered in monthly draws

### For Admins
1. Use `/admin` to access admin panel
2. View all holders and their status
3. Trigger monthly winner selection
4. Update balances manually if needed
5. Monitor bot statistics

## Monitoring & Maintenance

### Health Checks
- Built-in health check endpoint at `/health`
- Database connection monitoring
- Blockchain monitor status

### Logging
- Comprehensive logging to `bot.log`
- Error tracking and debugging
- Performance monitoring

### Background Tasks
- Automatic balance updates every 5 minutes
- Transaction monitoring
- Eligibility status updates

## Security Features

- Admin access control by user ID
- Input validation for wallet addresses
- Rate limiting protection
- Secure database connections
- Environment variable protection

## Troubleshooting

### Common Issues

#### Bot Not Responding
1. Check bot token is correct
2. Verify Railway deployment is running
3. Check logs for errors

#### Database Connection Errors
1. Verify DATABASE_URL is correct
2. Check Railway PostgreSQL status
3. Test connection manually

#### Blockchain API Issues
1. Verify Tatum API key
2. Check network configuration
3. Monitor API rate limits

#### Winner Selection Not Working
1. Check if eligible holders exist
2. Verify admin permissions
3. Ensure no duplicate winners for month

### Support

For technical support or feature requests:
1. Check the logs first
2. Review configuration settings
3. Contact the development team

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

---

Built with ❤️ for the token holding community 💎🙌

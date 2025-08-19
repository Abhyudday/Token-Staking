# Token Holder Bot

A comprehensive Telegram bot that takes daily snapshots of Solana token holders and maintains a leaderboard based on how long each wallet has held tokens.

## Features

- 🕐 **Daily Automated Snapshots** - Automatically captures token holder data every day
- 🏆 **Leaderboard System** - Ranks wallets by days held (longest holders rank highest)
- 💰 **USD Threshold Filtering** - Admin-configurable minimum value threshold
- 🗄️ **PostgreSQL Database** - Stores all holder data and snapshots (Railway compatible)
- 🔧 **Admin Panel** - Manage bot settings and trigger manual operations
- 📊 **Real-time Statistics** - View current bot status and holder information
- 🧹 **Automatic Cleanup** - Maintains database performance with scheduled cleanup
- 🏥 **Health Monitoring** - Built-in health check endpoints for Railway
 - 🔌 **Helius Integration** - Fetch token holders via Helius `getTokenAccounts`

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for immediate deployment instructions.

## Token Contract

**Contract Address:** `9M7eYNNP4TdJCmMspKpdbEhvpdds6E5WFVTTLjXfVray`

## Commands

- `/start` - Welcome message
- `/leaderboard` - View top token holders
- `/rank <wallet>` - Check wallet rank
- `/admin` - Admin panel (admin only)
- `/stats` - Bot statistics
- `/help` - Help information

## Health Check Endpoints

- **`/health`** - JSON health status for Railway monitoring
- **`/`** - Web dashboard showing bot status

## Data Source

This bot uses Helius to fetch token holders using the `getTokenAccounts` RPC with pagination. See the Helius guide: [How to Get Token Holders on Solana](https://www.helius.dev/blog/how-to-get-token-holders-on-solana).

## Deployment

This bot is configured for Railway deployment with:
- Health check monitoring
- Automatic restarts
- PostgreSQL database support
- Environment variable configuration

## License

MIT License

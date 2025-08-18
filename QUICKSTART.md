# 🚀 Quick Start Guide - Token Holder Bot

## Immediate Setup (5 minutes)

### 1. 🏃‍♂️ Quick Deploy
```bash
# Run the deployment script
./deploy.sh
```

This will:
- Initialize git repository (if needed)
- Add all files
- Commit changes
- Push to your repository
- Guide you through Railway setup

### 2. 🔑 Required Environment Variables

Create a `.env` file with:
```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql://username:password@host:port/db
SOLSCAN_API_KEY=your_solscan_pro_api_key
ADMIN_USER_IDS=123456789,987654321
MINIMUM_USD_THRESHOLD=100
```

### 3. 🚂 Railway Deployment

1. Go to [Railway.app](https://railway.app)
2. Connect your GitHub repository
3. Add PostgreSQL database service
4. Set environment variables
5. Deploy!

## 🏥 Health Check Endpoints

Once deployed, your bot will have:
- **`/health`** - JSON health status (for Railway monitoring)
- **`/`** - Web dashboard showing bot status

## 📱 Bot Commands

- `/start` - Welcome message
- `/leaderboard` - View top holders
- `/rank <wallet>` - Check wallet rank
- `/admin` - Admin panel (admin only)

## ⚡ What Happens Next

1. **Daily at 00:00 UTC**: Bot takes snapshots of all token holders
2. **Automatic ranking**: Wallets ranked by days held
3. **Real-time updates**: Leaderboard updates daily
4. **Admin control**: Adjust USD threshold via admin panel

## 🆘 Need Help?

- Check logs: `bot.log`
- Test locally: `python test_bot.py`
- Health check: Visit `/health` endpoint
- View status: Visit `/` endpoint

---

**🎯 Goal**: Track token holders and rank them by how long they've held tokens!

**🔗 Token**: `9M7eYNNP4TdJCmMspKpdbEhvpdds6E5WFVTTLjXfVray`

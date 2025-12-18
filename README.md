# CryptoWatcher

## Summary

CryptoWatcher is a Telegram Mini App for real-time cryptocurrency price monitoring with smart notifications. It aggregates price data from multiple exchanges via WebSocket connections and allows users to set up price alerts that are delivered directly through Telegram.

**Telegram Bot:** [@cryptowatcher_bot](https://t.me/cryptowatcher_bot)

## Key Features

- **Real-time Price Tracking:** WebSocket connections to Binance, OKX, and MEXC for live price updates
- **Smart Notifications:** Customizable stop-loss and take-profit alerts with flexible trigger conditions
- **Interactive Charts:** Historical price charts with 1d, 7d, 30d, and 1y periods
- **Multi-Exchange Aggregation:** Automatic price source selection based on availability and priority
- **Do Not Disturb Mode:** Configurable quiet hours to pause notifications

## Technology Stack

- **Backend:** Python with FastAPI, async WebSocket workers for real-time data
- **Frontend:** React with TypeScript, built with Vite
- **Database:** PostgreSQL for persistent storage
- **Caching:** Redis for price data, charts, and static content
- **External APIs:** CoinGecko (metadata), Binance/OKX/MEXC (prices and charts)

## Architecture

```
                      ┌─────────────────────────────────────────┐
                      │                 CLIENTS                 │
                      └─────────────────────────────────────────┘
                                          │
             ┌────────────────────────────┼────────────────────────────┐
             ▼                            ▼                            ▼
    ┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
    │  Telegram Bot   │          │  React Mini App │          │   REST API      │
    │   (polling)     │          │   (WebApp)      │          │   /api/v1/*     │
    └────────┬────────┘          └────────┬────────┘          └────────┬────────┘
             │                            │                            │
             └────────────────────────────┼────────────────────────────┘
                                          ▼
                            ┌─────────────────────────────┐
                            │      FastAPI Backend        │
                            │  ┌───────────────────────┐  │
                            │  │   Background Tasks    │  │
                            │  │ • Bot Polling         │  │
                            │  │ • Notification Checker│  │
                            │  │ • WebSocket Workers   │  │
                            │  └───────────────────────┘  │
                            └──────────────┬──────────────┘
                                           │
          ┌────────────────────────────────┼────────────────────────────────┐
          │                                │                                │
          ▼                                ▼                                ▼
┌───────────────────┐            ┌───────────────────┐            ┌───────────────────┐
│      STORAGE      │            │    PRICE DATA     │            │   STATIC DATA     │
├───────────────────┤            │   (Real-time)     │            │   (Metadata)      │
│                   │            ├───────────────────┤            ├───────────────────┤
│  ┌─────────────┐  │            │  ┌─────────────┐  │            │  ┌─────────────┐  │
│  │ PostgreSQL  │  │            │  │   Binance   │  │            │  │  CoinGecko  │  │
│  │  • Users    │  │            │  │  WebSocket  │  │            │  │    API      │  │
│  │  • Alerts   │  │            │  └─────────────┘  │            │  │  • Names    │  │
│  └─────────────┘  │            │  ┌─────────────┐  │            │  │  • Icons    │  │
│                   │            │  │     OKX     │  │            │  │  • Symbols  │  │
│  ┌─────────────┐  │            │  │  WebSocket  │  │            │  └─────────────┘  │
│  │    Redis    │  │◀──────────│  └─────────────┘  │            │                   │
│  │  • Prices   │  │  prices    │  ┌─────────────┐  │            │                   │
│  │  • Charts   │  │            │  │    MEXC     │  │            │                   │
│  │  • Static   │  │◀──────────│  │  WebSocket  │  │            │                   │
│  └─────────────┘  │  cache     │  └─────────────┘  │            │                   │
└───────────────────┘            └───────────────────┘            └───────────────────┘
```

### Data Flow

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             PRICE UPDATE FLOW                                    │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Binance/OKX/MEXC ─▶ WebSocket ─▶ Backend ─▶ RedisCache ─▶ API ─▶ Frontend    │
│         (tickers)                  (parse)     (store)     (serve)  (display)    │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────┐
│                               NOTIFICATION FLOW                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│    User creates alert ─▶ PostgreSQL ─▶ Checker (every 60s) ─▶ Telegram Bot     │
│       (Mini App)           (store)      (compares with Redis)  (send message)    │
│                                            (cached prices)                       │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────┐
│                            STATIC DATA FLOW                                      │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│         CoinGecko API ─▶ Backend ─▶ Redis Cache ─▶ API ─▶ Frontend             │
│         (names, icons)    (fetch)      (store)     (serve)  (display)            │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.11+ and pip
- Node.js 18+ and npm
- PostgreSQL 14+
- Redis 7+

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Pandusss/cryptowatcher.git
   cd cryptowatcher
   ```

2. Configure environment variables (see [Configuration](#configuration) section)

3. Set up the backend:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or: venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   alembic upgrade head
   ```

4. Set up the frontend:
   ```bash
   cd frontend
   npm install
   ```

5. Start the application:
   ```bash
   # Terminal 1: Backend
   cd backend
   python run.py

   # Terminal 2: Frontend
   cd frontend
   npm run dev
   ```

### Verification

- The API should be accessible at `http://localhost:8000`
- The frontend should be accessible at `http://localhost:5173`

## Configuration

Create a `.env` file in the project root directory:

```env
# Application
APP_NAME=CryptoWatcher
APP_VERSION=1.0.0
DEBUG=false

# Database (PostgreSQL)
DATABASE_URL=postgresql://postgres:password@localhost:5432/cryptowatcher

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram Bot (get from @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# CORS origins (comma-separated)
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000

# CoinGecko API key (optional, for higher rate limits)
COINGECKO_API_KEY=
```

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `REDIS_URL` | Redis connection string | ✅ |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | ✅ |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | ✅ |
| `COINGECKO_API_KEY` | CoinGecko API key for higher rate limits | ❌ |

## Usage

### API Endpoints

**Coins:**
- `GET /api/v1/coins/list` — Get cryptocurrency list with prices
- `GET /api/v1/coins/{coin_id}` — Get coin details
- `GET /api/v1/coins/{coin_id}/chart?period=7d` — Get price chart

**Notifications:**
- `GET /api/v1/notifications/?user_id={id}` — Get user notifications
- `POST /api/v1/notifications/` — Create notification
- `PUT /api/v1/notifications/{id}` — Update notification
- `DELETE /api/v1/notifications/{id}` — Delete notification

**Users:**
- `POST /api/v1/users/register` — Register user
- `GET /api/v1/users/{id}/dnd-settings` — Get DND settings
- `PUT /api/v1/users/{id}/dnd-settings` — Update DND settings

## Components

### Backend

| Component | Description |
|-----------|-------------|
| **API** | REST endpoints for coins, notifications, and users |
| **WebSocket Workers** | Real-time price collection from Binance, OKX, MEXC |
| **Notification Checker** | Background task that checks alert conditions every 60s |
| **Bot Polling** | Telegram bot for `/start` command and sending alerts |
| **Aggregation Service** | Unified interface for multi-source data with fallback |

### Frontend

| Component | Description |
|-----------|-------------|
| **Pages** | Main, ChooseCoin, CreateNotification, Settings |
| **Components** | Reusable UI components (Charts, Dropdowns, etc.) |
| **Services** | API client for backend communication |
| **Context** | Theme provider for dark/light mode |

## Project Structure

```
CryptoWatcher/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST API endpoints
│   │   ├── core/            # Config, database, redis, coin registry
│   │   ├── models/          # SQLAlchemy models (User, Notification)
│   │   ├── providers/       # Exchange adapters (Binance, OKX, MEXC)
│   │   ├── services/        # Business logic layer
│   │   └── utils/           # Helpers (cache, formatters, http client)
│   ├── alembic/             # Database migrations
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable React components
│   │   ├── pages/           # Page components
│   │   ├── services/        # API client
│   │   ├── context/         # React context providers
│   │   └── common/          # Hooks, utils, styles
│   └── package.json
└── README.md
```

## Contributing

We welcome contributions to CryptoWatcher! Here's how you can contribute:

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature-name`
3. Make your changes
4. Run linting: `cd frontend && npm run lint`
5. Commit your changes: `git commit -m "Add some feature"`
6. Push to the branch: `git push origin feat/your-feature-name`
7. Submit a pull request

### Adding New Exchange

1. Create WebSocket adapter in `backend/app/providers/`
2. Implement `BaseWebSocketWorker` for real-time prices
3. Implement `BaseChartAdapter` for historical data
4. Add to `coins.json` configuration
5. Register in `aggregation_service.py`

### Coding Standards

- Python code should follow PEP 8 guidelines
- TypeScript code should follow the project's ESLint configuration
- Commit messages should be clear and descriptive

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Binance API](https://binance-docs.github.io/apidocs/)
- [OKX API](https://www.okx.com/docs-v5/)
- [MEXC API](https://mexcdevelop.github.io/apidocs/)
- [CoinGecko API](https://www.coingecko.com/en/api)

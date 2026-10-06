# options_bot

A starter bot that sells Bitcoin **put spreads** on the [Deribit testnet](https://test.deribit.com), where all money is fake. It only talks to the testnet.

## The strategy

A put spread is two trades on the same expiry date:

- **Sell** a put about 20 delta below the price. You get paid for it.
- **Buy** a put $2,000 lower. This caps how much you can lose.

You keep the payment if Bitcoin stays above the short strike until expiry. The most you can lose is the $2,000 gap times the size, minus what you were paid. With the default size of 0.1 BTC, that's at most $200 per spread.

## What each run does

1. Checks your account. If equity has fallen 20% below where it started, the **kill switch** stops all trading.
2. If a spread is already open, it waits for it to expire. Deribit settles expired options automatically.
3. Picks the nearest expiry 7 to 21 days away and the strikes for the spread.
4. Skips the trade if the payment is too small or the possible loss is above the limit.
5. Buys the protective put first, then sells the other put. Both are fill-or-kill orders, so you're never left holding only the risky short put.

You can change the limits in `Settings` in `strategy.py`.

## Setup

1. Create a free account at https://test.deribit.com. It's separate from the real Deribit site.
2. Go to **Account → API** and create a key with **trade** permission.
3. Set the key in your terminal. Never put it in code or commit it.

   Windows (PowerShell):
   ```
   $env:DERIBIT_CLIENT_ID="your id"
   $env:DERIBIT_CLIENT_SECRET="your secret"
   ```
   Mac/Linux:
   ```
   export DERIBIT_CLIENT_ID="your id"
   export DERIBIT_CLIENT_SECRET="your secret"
   ```

## Run

From the project folder:

```
.venv\Scripts\python.exe -m options_bot.bot           # dry run: shows the trade, places nothing
.venv\Scripts\python.exe -m options_bot.bot --trade   # places the orders on the testnet
```

A dry run works without API keys, but then it skips the account checks.

Each run does one round and exits. To run it every hour, use Windows Task Scheduler, or `cron` on Mac/Linux.

## Not built yet

- Closing a spread early, for example to take profit at 50% of the payment
- Alerts when the bot trades or something fails
- A backtest on past prices

Run it on the testnet for weeks before thinking about real money. It's a starting point for learning, not a proven strategy.

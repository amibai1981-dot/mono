#!/usr/bin/env python3
"""
XRP Scalping Bot - Binance
استراتيجية: EMA Cross + RSI + Bollinger Bands على إطار 1 دقيقة
"""

import os
import time
import logging
from datetime import datetime
from decimal import Decimal, ROUND_DOWN

import pandas as pd
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv()

# ─── إعداد السجلات ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("xrp_scalper.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("XRP-Scalper")

# ─── الإعدادات ───────────────────────────────────────────────────
SYMBOL = "XRPUSDT"
INTERVAL = Client.KLINE_INTERVAL_1MINUTE
KLINES_LIMIT = 100

# مؤشرات
EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65
BB_PERIOD = 20
BB_STD = 2.0

# إدارة الصفقات
TRADE_AMOUNT_USDT = float(os.getenv("TRADE_AMOUNT_USDT", 10))
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PERCENT", 0.5)) / 100
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PERCENT", 1.0)) / 100
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", 3))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS_USDT", 30))
TESTNET = os.getenv("TESTNET", "true").lower() == "true"

LOOP_INTERVAL = 60  # ثانية


class XRPScalper:
    def __init__(self):
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_API_SECRET", "")

        if not api_key or api_key == "your_api_key_here":
            raise ValueError("❌ يرجى إضافة مفاتيح API في ملف .env")

        self.client = Client(api_key, api_secret, testnet=TESTNET)
        self.open_trades: list[dict] = []
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.start_time = datetime.now()

        mode = "🟡 TESTNET" if TESTNET else "🔴 LIVE"
        log.info(f"{Fore.CYAN}=== XRP Scalping Bot بدأ [{mode}] ===")
        log.info(f"الزوج: {SYMBOL} | الصفقة: {TRADE_AMOUNT_USDT}$ | SL: {STOP_LOSS_PCT*100}% | TP: {TAKE_PROFIT_PCT*100}%")

    # ─── جلب البيانات ────────────────────────────────────────────
    def get_klines(self) -> pd.DataFrame:
        raw = self.client.get_klines(symbol=SYMBOL, interval=INTERVAL, limit=KLINES_LIMIT)
        df = pd.DataFrame(raw, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore",
        ])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        return df

    # ─── المؤشرات الفنية ─────────────────────────────────────────
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"]

        # EMA
        df["ema_fast"] = close.ewm(span=EMA_FAST, adjust=False).mean()
        df["ema_slow"] = close.ewm(span=EMA_SLOW, adjust=False).mean()

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
        loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
        rs = gain / loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        # Bollinger Bands
        df["bb_mid"] = close.rolling(BB_PERIOD).mean()
        std = close.rolling(BB_PERIOD).std()
        df["bb_upper"] = df["bb_mid"] + BB_STD * std
        df["bb_lower"] = df["bb_mid"] - BB_STD * std

        # حجم المتوسط
        df["vol_ma"] = df["volume"].rolling(20).mean()

        return df

    # ─── إشارات الدخول ───────────────────────────────────────────
    def get_signal(self, df: pd.DataFrame) -> str:
        """يُعيد 'BUY', 'SELL', أو 'HOLD'"""
        last = df.iloc[-1]
        prev = df.iloc[-2]

        ema_cross_up = prev["ema_fast"] < prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]
        ema_cross_dn = prev["ema_fast"] > prev["ema_slow"] and last["ema_fast"] < last["ema_slow"]

        rsi_ok_buy = last["rsi"] < RSI_OVERBOUGHT and last["rsi"] > RSI_OVERSOLD
        rsi_ok_sell = last["rsi"] > RSI_OVERSOLD and last["rsi"] < RSI_OVERBOUGHT

        price_near_lower = last["close"] <= last["bb_lower"] * 1.002
        price_near_upper = last["close"] >= last["bb_upper"] * 0.998

        volume_ok = last["volume"] > last["vol_ma"] * 0.8

        # شرط الشراء: تقاطع EMA للأعلى + RSI معقول + قرب BB السفلي + حجم
        if ema_cross_up and rsi_ok_buy and (price_near_lower or last["close"] < last["bb_mid"]) and volume_ok:
            return "BUY"

        # شرط البيع: تقاطع EMA للأسفل + RSI معقول + قرب BB العلوي + حجم
        if ema_cross_dn and rsi_ok_sell and (price_near_upper or last["close"] > last["bb_mid"]) and volume_ok:
            return "SELL"

        return "HOLD"

    # ─── الكمية المتاحة ──────────────────────────────────────────
    def calc_quantity(self, price: float) -> float:
        qty = TRADE_AMOUNT_USDT / price
        # تقريب لـ 2 خانة عشرية (XRP precision on Binance)
        qty = float(Decimal(str(qty)).quantize(Decimal("0.01"), rounding=ROUND_DOWN))
        return qty

    # ─── فتح صفقة ────────────────────────────────────────────────
    def open_trade(self, side: str, price: float):
        if len(self.open_trades) >= MAX_OPEN_TRADES:
            return
        if self.daily_pnl <= -MAX_DAILY_LOSS:
            log.warning(f"{Fore.RED}⛔ تم الوصول للحد اليومي للخسارة ({MAX_DAILY_LOSS}$). البوت متوقف.")
            return

        qty = self.calc_quantity(price)
        if qty <= 0:
            return

        try:
            if side == "BUY":
                order = self.client.order_market_buy(symbol=SYMBOL, quantity=qty)
                sl = price * (1 - STOP_LOSS_PCT)
                tp = price * (1 + TAKE_PROFIT_PCT)
            else:
                order = self.client.order_market_sell(symbol=SYMBOL, quantity=qty)
                sl = price * (1 + STOP_LOSS_PCT)
                tp = price * (1 - TAKE_PROFIT_PCT)

            trade = {
                "id": order["orderId"],
                "side": side,
                "entry": price,
                "qty": qty,
                "sl": sl,
                "tp": tp,
                "time": datetime.now(),
            }
            self.open_trades.append(trade)
            self.total_trades += 1

            log.info(
                f"{Fore.GREEN if side=='BUY' else Fore.RED}"
                f"✅ {side} | السعر: {price:.4f} | الكمية: {qty} XRP "
                f"| SL: {sl:.4f} | TP: {tp:.4f}"
            )
        except BinanceAPIException as e:
            log.error(f"❌ خطأ في فتح الصفقة: {e}")

    # ─── إغلاق الصفقة ────────────────────────────────────────────
    def close_trade(self, trade: dict, current_price: float, reason: str):
        try:
            if trade["side"] == "BUY":
                self.client.order_market_sell(symbol=SYMBOL, quantity=trade["qty"])
                pnl = (current_price - trade["entry"]) * trade["qty"]
            else:
                self.client.order_market_buy(symbol=SYMBOL, quantity=trade["qty"])
                pnl = (trade["entry"] - current_price) * trade["qty"]

            self.daily_pnl += pnl
            if pnl > 0:
                self.winning_trades += 1

            color = Fore.GREEN if pnl > 0 else Fore.RED
            log.info(
                f"{color}🔒 إغلاق [{reason}] | PnL: {pnl:+.4f}$ "
                f"| اليومي: {self.daily_pnl:+.4f}$"
            )
        except BinanceAPIException as e:
            log.error(f"❌ خطأ في إغلاق الصفقة: {e}")

    # ─── إدارة الصفقات المفتوحة ──────────────────────────────────
    def manage_open_trades(self, current_price: float):
        closed = []
        for trade in self.open_trades:
            if trade["side"] == "BUY":
                if current_price <= trade["sl"]:
                    self.close_trade(trade, current_price, "STOP LOSS")
                    closed.append(trade)
                elif current_price >= trade["tp"]:
                    self.close_trade(trade, current_price, "TAKE PROFIT")
                    closed.append(trade)
            else:  # SELL
                if current_price >= trade["sl"]:
                    self.close_trade(trade, current_price, "STOP LOSS")
                    closed.append(trade)
                elif current_price <= trade["tp"]:
                    self.close_trade(trade, current_price, "TAKE PROFIT")
                    closed.append(trade)

        for t in closed:
            self.open_trades.remove(t)

    # ─── طباعة الإحصائيات ────────────────────────────────────────
    def print_stats(self, price: float, signal: str, df: pd.DataFrame):
        last = df.iloc[-1]
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades else 0
        uptime = str(datetime.now() - self.start_time).split(".")[0]

        print(
            f"\r{Fore.CYAN}[{datetime.now().strftime('%H:%M:%S')}] "
            f"XRP: {Fore.YELLOW}{price:.4f}$ "
            f"{Fore.WHITE}| RSI: {last['rsi']:.1f} "
            f"| EMA9/21: {last['ema_fast']:.4f}/{last['ema_slow']:.4f} "
            f"| إشارة: {Fore.GREEN if signal=='BUY' else Fore.RED if signal=='SELL' else Fore.WHITE}{signal} "
            f"{Fore.WHITE}| صفقات مفتوحة: {len(self.open_trades)} "
            f"| PnL اليوم: {Fore.GREEN if self.daily_pnl>=0 else Fore.RED}{self.daily_pnl:+.4f}$ "
            f"{Fore.WHITE}| Win%: {win_rate:.0f}% "
            f"| Uptime: {uptime}",
            end="",
            flush=True,
        )

    # ─── الحلقة الرئيسية ─────────────────────────────────────────
    def run(self):
        log.info("🚀 البوت يعمل... اضغط Ctrl+C للإيقاف")
        while True:
            try:
                df = self.get_klines()
                df = self.add_indicators(df)
                current_price = df.iloc[-1]["close"]

                # إدارة الصفقات المفتوحة
                self.manage_open_trades(current_price)

                # الحصول على الإشارة
                signal = self.get_signal(df)

                # تنفيذ الإشارة
                if signal == "BUY":
                    self.open_trade("BUY", current_price)
                elif signal == "SELL":
                    self.open_trade("SELL", current_price)

                self.print_stats(current_price, signal, df)
                time.sleep(LOOP_INTERVAL)

            except BinanceAPIException as e:
                log.error(f"Binance API Error: {e}")
                time.sleep(10)
            except KeyboardInterrupt:
                print()
                log.info("⏹️ إيقاف البوت...")
                # إغلاق جميع الصفقات المفتوحة
                price = float(self.client.get_symbol_ticker(symbol=SYMBOL)["price"])
                for trade in self.open_trades[:]:
                    self.close_trade(trade, price, "إيقاف يدوي")
                log.info(f"📊 إجمالي الصفقات: {self.total_trades} | Win Rate: {(self.winning_trades/self.total_trades*100) if self.total_trades else 0:.1f}% | PnL: {self.daily_pnl:+.4f}$")
                break
            except Exception as e:
                log.error(f"خطأ غير متوقع: {e}")
                time.sleep(15)


if __name__ == "__main__":
    bot = XRPScalper()
    bot.run()

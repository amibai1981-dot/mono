"""
بوت التداول الفوري على Bitget
يدعم: مراقبة السوق | تحليل فني | تداول DCA | مراقبة الرصيد
"""

import time, sys, os
from datetime import datetime

import bitget_api as api
import indicators as ind
from config import (
    TRADING_PAIRS, DCA, RISK, INDICATORS, TIMEFRAMES, MONITOR, FEES
)


# ── عرض الرصيد ────────────────────────────────────────────────

def show_balance():
    assets = api.get_spot_assets()
    if not assets:
        print("لا يوجد رصيد أو خطأ في الاتصال")
        return
    print(f"\n{'العملة':<10} {'المتاح':>16} {'مجمّد':>16}")
    print("─" * 46)
    for a in assets:
        avail  = float(a.get("available", 0))
        locked = float(a.get("frozen", 0))
        print(f"{a['coin']:<10} {avail:>16.6f} {locked:>16.6f}")


# ── مراقبة السوق ──────────────────────────────────────────────

def show_market():
    tickers = api.get_tickers(TRADING_PAIRS)
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n[ أسعار السوق الفوري — {now} ]")
    print(f"{'الزوج':<12} {'السعر':>14} {'24h%':>9} {'حجم USDT':>20}")
    print("─" * 60)
    for t in tickers:
        price  = float(t.get("lastPr", 0))
        change = float(t.get("change24h", 0)) * 100
        vol    = float(t.get("quoteVolume", 0))
        arrow  = "▲" if change >= 0 else "▼"
        clr    = "\033[92m" if change >= 0 else "\033[91m"
        rst    = "\033[0m"
        print(f"{t['symbol']:<12} {price:>14.4f} {clr}{arrow}{abs(change):>7.2f}%{rst} {vol:>20,.0f}")


# ── التحليل الفني ─────────────────────────────────────────────

def show_analysis():
    print(f"\n[ تحليل فني — {TIMEFRAMES['primary']} ]")
    print(f"{'الزوج':<12} {'إشارة':>8} {'RSI':>7} {'اتجاه':>8} {'BB':>6} {'أسباب'}")
    print("─" * 80)
    for symbol in TRADING_PAIRS:
        candles = api.get_candles(symbol, TIMEFRAMES["primary"], TIMEFRAMES["candles"])
        if not candles:
            print(f"{symbol:<12} {'خطأ':>8}")
            continue
        result = ind.analyze(candles, INDICATORS)
        sig    = result["signal"]
        sig_ar = {"buy": "شراء ✓", "sell": "بيع ✗", "neutral": "انتظار"}.get(sig, sig)
        trend  = "صاعد" if result["trend"] == "bull" else "هابط"
        bb_pos = "أسفل" if result.get("bb_lower") else "—"
        reasons = " | ".join(result.get("reasons", [])[:2])
        clr = "\033[92m" if sig == "buy" else ("\033[91m" if sig == "sell" else "")
        rst = "\033[0m" if clr else ""
        print(f"{symbol:<12} {clr}{sig_ar:>8}{rst} {result['rsi']:>7.1f} {trend:>8} {bb_pos:>6}  {reasons}")


# ── فحص إدارة المخاطر ────────────────────────────────────────

def check_risk(usdt_balance: float, target_size_usdt: float, symbol: str) -> tuple[bool, str]:
    open_orders = api.get_open_orders(symbol)
    if len(open_orders) >= RISK["max_concurrent_positions"]:
        return False, f"تجاوز الحد الأقصى للصفقات المفتوحة ({RISK['max_concurrent_positions']})"
    if usdt_balance < RISK["min_usdt_balance"] + target_size_usdt:
        return False, f"الرصيد غير كافٍ (احتياطي: {RISK['min_usdt_balance']} USDT)"
    max_trade = usdt_balance * RISK["max_risk_per_trade_pct"] / 100
    if target_size_usdt > max_trade:
        return False, f"الصفقة أكبر من حد المخاطرة ({max_trade:.2f} USDT)"
    return True, "OK"


# ── تنفيذ صفقة DCA ────────────────────────────────────────────

def execute_dca(symbol: str, price: float, usdt_amount: float) -> bool:
    usdt_bal = api.get_usdt_balance()
    ok, reason = check_risk(usdt_bal, usdt_amount, symbol)
    if not ok:
        print(f"  ✗ رفضت الصفقة: {reason}")
        return False

    size = usdt_amount / price
    size_str  = f"{size:.6f}"
    price_str = f"{price:.6f}"

    result = api.place_order(symbol, "buy", size_str, price_str, "limit")
    if result.get("code") == "00000":
        order_id = result["data"]["orderId"]
        fee_est  = usdt_amount * FEES["spot_maker"]
        print(f"  ✓ أمر شراء: {symbol} | الحجم: {size:.6f} | السعر: {price:.4f} | الرسوم~{fee_est:.4f} USDT")
        print(f"    رقم الأمر: {order_id}")
        return True
    else:
        print(f"  ✗ فشل الأمر: {result.get('msg', 'خطأ غير معروف')}")
        return False


# ── المراقبة الكاملة (وضع البوت) ─────────────────────────────

def run_bot():
    print("=" * 70)
    print("  بوت التداول الفوري — Bitget")
    print("  اضغط Ctrl+C للإيقاف")
    print("=" * 70)

    dca_state = {pair: {"orders": 0, "entry_price": None} for pair in TRADING_PAIRS}

    while True:
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n\033[1m[{ts}]\033[0m")

            show_market()

            tickers = api.get_tickers(TRADING_PAIRS)
            prices  = {t["symbol"]: float(t.get("lastPr", 0)) for t in tickers}

            for symbol in TRADING_PAIRS:
                price = prices.get(symbol, 0)
                if price == 0:
                    continue

                candles = api.get_candles(symbol, TIMEFRAMES["primary"], TIMEFRAMES["candles"])
                result  = ind.analyze(candles, INDICATORS) if candles else {"signal": "neutral"}

                state = dca_state[symbol]

                if result["signal"] == "buy" and DCA["enabled"]:
                    if state["orders"] == 0:
                        # أمر DCA أول
                        print(f"\n  [{symbol}] إشارة شراء DCA أولية")
                        if execute_dca(symbol, price, DCA["base_order_usdt"]):
                            state["orders"]      = 1
                            state["entry_price"] = price

                    elif state["entry_price"] and state["orders"] < DCA["max_safety_orders"] + 1:
                        # حساب سعر أمر الأمان
                        drop = DCA["price_deviation_pct"] * (
                            DCA["deviation_multiplier"] ** (state["orders"] - 1)
                        )
                        safety_price = state["entry_price"] * (1 - drop / 100)

                        if price <= safety_price:
                            order_size = DCA["safety_order_usdt"] * (
                                DCA["safety_order_multiplier"] ** (state["orders"] - 1)
                            )
                            print(f"\n  [{symbol}] أمر أمان #{state['orders']} عند {price:.4f}")
                            if execute_dca(symbol, price, order_size):
                                state["orders"] += 1

                elif result["signal"] == "sell" and state["orders"] > 0:
                    print(f"\n  [{symbol}] إشارة بيع — إيقاف الدورة")
                    state["orders"]      = 0
                    state["entry_price"] = None

            time.sleep(MONITOR["refresh_seconds"])

        except KeyboardInterrupt:
            print("\n\nتم إيقاف البوت.")
            break
        except Exception as e:
            print(f"\n  [خطأ] {e}")
            time.sleep(30)


# ── نقطة الدخول ──────────────────────────────────────────────

MODES = {
    "balance":  show_balance,
    "market":   show_market,
    "analysis": show_analysis,
    "bot":      run_bot,
}

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "market"
    if mode not in MODES:
        print(f"الأوضاع المتاحة: {' | '.join(MODES)}")
        sys.exit(1)
    MODES[mode]()


if __name__ == "__main__":
    main()

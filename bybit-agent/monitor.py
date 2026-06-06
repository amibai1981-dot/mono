import time, base64, json, urllib.request, subprocess, os, sys
from datetime import datetime

API_KEY = os.getenv("BYBIT_API_KEY", "OOtP0fbulyroD2LAHI")
PRIVATE_KEY_PATH = os.getenv("BYBIT_API_PRIVATE_KEY_PATH", "./private.pem")
ENV = os.getenv("BYBIT_ENV", "mainnet")
BASE_URL = "https://api-testnet.bybit.com" if ENV == "testnet" else "https://api.bybit.com"
REFRESH = int(os.getenv("REFRESH_SECONDS", "10"))


def sign(payload: str) -> str:
    result = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", PRIVATE_KEY_PATH],
        input=payload.encode(), capture_output=True
    )
    return base64.b64encode(result.stdout).decode()


def get(path: str, params: str = "", auth: bool = False) -> dict:
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"
    url = f"{BASE_URL}{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "bybit-agent/1.0")
    if auth:
        signature = sign(timestamp + API_KEY + recv_window + (params or ""))
        req.add_header("X-BAPI-API-KEY", API_KEY)
        req.add_header("X-BAPI-TIMESTAMP", timestamp)
        req.add_header("X-BAPI-RECV-WINDOW", recv_window)
        req.add_header("X-BAPI-SIGN", signature)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def show_balance():
    data = get("/v5/account/wallet-balance", "accountType=UNIFIED", auth=True)
    if data["retCode"] != 0:
        print(f"خطأ: {data['retMsg']}")
        return
    coins = data["result"]["list"][0]["coin"]
    coins = [c for c in coins if float(c.get("walletBalance", 0)) > 0]
    print(f"\n{'العملة':<10} {'الرصيد':>15} {'القيمة USD':>15}")
    print("-" * 42)
    for c in coins:
        print(f"{c['coin']:<10} {float(c['walletBalance']):>15.6f} {float(c.get('usdValue', 0)):>14.2f}$")


def show_top10():
    data = get("/v5/market/tickers", "category=spot")
    tickers = data["result"]["list"]
    tickers.sort(key=lambda x: float(x.get("turnover24h", 0)), reverse=True)
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n[ أعلى 10 عملات — {now} ]")
    print(f"{'#':<4} {'الرمز':<12} {'السعر':>12} {'24h':>10} {'حجم USD':>18}")
    print("-" * 60)
    for i, t in enumerate(tickers[:10], 1):
        price = float(t["lastPrice"])
        change = float(t["price24hPcnt"]) * 100
        volume = float(t["turnover24h"])
        arrow = "▲" if change >= 0 else "▼"
        color = "\033[92m" if change >= 0 else "\033[91m"
        reset = "\033[0m"
        print(f"{i:<4} {t['symbol']:<12} {price:>12.4f} {color}{arrow}{abs(change):>8.2f}%{reset} {volume:>18,.0f}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "monitor"

    if mode == "balance":
        show_balance()
    elif mode == "monitor":
        print("مراقبة أعلى 10 عملات — اضغط Ctrl+C للإيقاف\n")
        while True:
            try:
                show_top10()
                time.sleep(REFRESH)
            except KeyboardInterrupt:
                print("\nتم الإيقاف.")
                break
    elif mode == "all":
        show_balance()
        show_top10()


if __name__ == "__main__":
    main()

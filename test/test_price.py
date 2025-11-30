# test_price.py
from finance_mcp_server.database.models import (
    get_current_price,
    validate_ticker,
    format_currency
)

# Test lấy giá VN
print("=== TEST VCI API ===")
tickers = ['VNM', 'VCB', 'HPG', 'FPT']

for ticker in tickers:
    price = get_current_price(ticker, market='VN')
    if price:
        print(f"✅ {ticker}: {format_currency(price)}")
    else:
        print(f"❌ {ticker}: Không lấy được giá")

# Test validate ticker
print("\n=== TEST VALIDATE ===")
print(f"VNM tồn tại: {validate_ticker('VNM')}")
print(f"KHONGCOMA tồn tại: {validate_ticker('KHONGCOMA')}")

# Test cache (gọi lại ngay → phải dùng cache)
print("\n=== TEST CACHE ===")
print("Gọi lần 1 (fetch API):")
price1 = get_current_price('VNM')
print(f"VNM: {format_currency(price1)}")

print("Gọi lần 2 (dùng cache):")
price2 = get_current_price('VNM')
print(f"VNM: {format_currency(price2)}")
print(f"Cache hoạt động: {price1 == price2}")
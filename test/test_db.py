# test_db.py
from finance_mcp_server.database.models import add_transaction, get_all_positions

# Test MUA
result = add_transaction('VNM', 'BUY', 100, 85000, notes='Test mua')
print(result)

# Xem positions
positions = get_all_positions()
print(positions)
import sys
import os
import subprocess
import time

# Path setup
script_dir = os.path.dirname(os.path.abspath(__file__))
finance_mcp_dir = os.path.join(script_dir, "finance_mcp_server")
portfolio_server_path = os.path.join(finance_mcp_dir, "portfolio_server.py")

print("="*60)
print("🔍 Testing MCP Portfolio Server Connection")
print("="*60)
print(f"Script dir: {script_dir}")
print(f"Portfolio server: {portfolio_server_path}")
print(f"Python: {sys.executable}")
print()

# Test 1: Check file exists
print("Test 1: File existence")
if os.path.exists(portfolio_server_path):
    print(f"✅ portfolio_server.py exists")
else:
    print(f"❌ portfolio_server.py NOT FOUND")
    sys.exit(1)

# Test 2: Check database
db_path = os.path.join(finance_mcp_dir, "database", "portfolio.db")
print(f"\nTest 2: Database file")
print(f"Expected path: {db_path}")
if os.path.exists(db_path):
    print(f"✅ portfolio.db exists")
else:
    print(f"⚠️ portfolio.db not found (will be created)")

# Test 3: Try to spawn server process
print(f"\nTest 3: Spawn server process")
print("Starting server...")

try:
    proc = subprocess.Popen(
        [sys.executable, portfolio_server_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1  # Line buffered
    )
    
    print(f"✅ Process spawned (PID: {proc.pid})")
    print("Waiting 2 seconds for initialization...")
    time.sleep(2)
    
    # Check if process is still alive
    poll_result = proc.poll()
    if poll_result is None:
        print(f"✅ Process still running")
    else:
        print(f"❌ Process exited with code {poll_result}")
    
    # Read stderr (where our debug messages go)
    print("\n" + "="*60)
    print("📋 STDERR OUTPUT:")
    print("="*60)
    
    # Try to read stderr (non-blocking)
    import select
    if sys.platform != 'win32':
        # Unix/Mac
        ready, _, _ = select.select([proc.stderr], [], [], 0.1)
        if ready:
            stderr_output = proc.stderr.read()
            print(stderr_output)
    else:
        # Windows - just try to read
        try:
            # Read available data without blocking
            stderr_data = os.read(proc.stderr.fileno(), 4096).decode('utf-8')
            print(stderr_data)
        except:
            print("(No stderr output yet or not readable)")
    
    # Terminate
    print("\n" + "="*60)
    print("Terminating server...")
    proc.terminate()
    proc.wait(timeout=2)
    print("✅ Server terminated cleanly")
    
except subprocess.TimeoutExpired:
    print("⚠️ Process didn't terminate, forcing kill")
    proc.kill()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("🎯 Diagnosis:")
print("="*60)
print("If you see '[INIT]' messages above, server is starting correctly.")
print("If you see '[FATAL]' messages, check the error details.")
print("If you see nothing, there's an import error happening silently.")
print()
print("Next step: Run 'python agent.py' and compare the output.")
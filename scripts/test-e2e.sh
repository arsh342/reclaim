#!/bin/bash
# Reclaim E2E Test Script
# Runs full end-to-end test: fires webhook, verifies explanation, verifies recovery

set -e

echo "=== Starting E2E Test ==="

# Configuration
DB_URL="postgresql://postgres:postgres@localhost:5432/reclaim_test"
BACKEND_URL="http://127.0.0.1:8000"
BACKEND_CMD="./backend/venv/bin/uvicorn backend.api.main:app --host 127.0.0.1 --port 8000"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${YELLOW}$1${NC}"; }
log_pass() { echo -e "${GREEN}$1${NC}"; }
log_fail() { echo -e "${RED}$1${NC}"; }

cleanup() {
    log_info "7. Stopping backend..."
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Create payload files
cat > /tmp/payload_failed.json << 'JSONEOF'
{"entity":"event","account_id":"acc_test","event":"payment.failed","contains":["payment"],"payload":{"payment":{"entity":{"id":"pay_e2e_001","order_id":"order_e2e_001","amount":25000,"currency":"INR","method":"card","status":"failed","attempt_number":1,"error_code":"BAD_REQUEST_PAYMENT_FAILED","error_description":"Payment failed","error_reason":"insufficient_funds","error_source":"customer","error_step":"payment_authentication"}}}}
JSONEOF

cat > /tmp/payload_captured.json << 'JSONEOF'
{"entity":"event","account_id":"acc_test","event":"payment.captured","contains":["payment"],"payload":{"payment":{"entity":{"id":"pay_e2e_002","order_id":"order_e2e_001","amount":25000,"currency":"INR","method":"card","status":"captured","attempt_number":1}}}}
JSONEOF

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${YELLOW}$1${NC}"; }
log_pass() { echo -e "${GREEN}$1${NC}"; }
log_fail() { echo -e "${RED}$1${NC}"; }

cleanup() {
    log_info "7. Stopping backend..."
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

# 1. Clean database
log_info "1. Cleaning test database..."
DATABASE_URL=$DB_URL ./backend/venv/bin/python -c "
from backend.db.session import SessionLocal
from backend.db.models import Order, PaymentAttempt, RecoveryAction, WebhookEvent
from sqlalchemy import delete
s = SessionLocal()
try:
    s.execute(delete(WebhookEvent))
    s.execute(delete(RecoveryAction))
    s.execute(delete(PaymentAttempt))
    s.execute(delete(Order))
    s.commit()
    print('   Database cleaned')
finally:
    s.close()
"

# 2. Start backend
log_info "2. Starting backend server..."
DATABASE_URL=$DB_URL $BACKEND_CMD > /tmp/e2e-backend.log 2>&1 &
BACKEND_PID=$!
log_info "   Backend PID: $BACKEND_PID"
sleep 3

# 3. Fire payment.failed webhook
log_info "3. Firing payment.failed webhook..."
curl -s -X POST $BACKEND_URL/webhooks/simulate \
  -H "Content-Type: application/json" \
  -d @/tmp/payload_failed.json | python3 -m json.tool

# 4. Verify explanation in order detail
log_info "4. Verifying explanation in order detail..."
sleep 1
curl -s $BACKEND_URL/orders/order_e2e_001 | python3 -c "
import sys, json
data = json.load(sys.stdin)
actions = data.get('recovery_actions', [])
if not actions:
    print('   FAIL: No recovery actions found')
    sys.exit(1)
action = actions[0]
explanation = action.get('explanation')
model = action.get('explanation_model')
if not explanation:
    print('   FAIL: No explanation field')
    sys.exit(1)
if not model:
    print('   FAIL: No explanation_model field')
    sys.exit(1)
print(f'   PASS: Explanation found (model: {model})')
print(f'   Text: {explanation[:80]}...')
"

# 5. Fire payment.captured webhook
log_info "5. Firing payment.captured webhook..."
curl -s -X POST $BACKEND_URL/webhooks/simulate \
  -H "Content-Type: application/json" \
  -d @/tmp/payload_captured.json | python3 -m json.tool

# 6. Verify order recovered and action cancelled
log_info "6. Verifying order recovered and action cancelled..."
sleep 1
curl -s $BACKEND_URL/orders/order_e2e_001 | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('status') != 'recovered':
    print(f'   FAIL: Order status is {data.get(\"status\")}, expected recovered')
    sys.exit(1)
actions = data.get('recovery_actions', [])
if not actions:
    print('   FAIL: No recovery actions found')
    sys.exit(1)
if actions[0].get('status') != 'cancelled':
    print(f'   FAIL: Action status is {actions[0].get(\"status\")}, expected cancelled')
    sys.exit(1)
print('   PASS: Order recovered, action cancelled')
"

log_pass "=== E2E Test PASSED ==="
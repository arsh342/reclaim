# Reclaim — Makefile for common development tasks

.PHONY: help test test-e2e build backend-test frontend-build dev-backend dev-frontend clean

# Default target
help:
	@echo "Reclaim — Development Commands"
	@echo ""
	@echo "  make test           Run all backend tests (46 tests)"
	@echo "  make test-e2e       Run full end-to-end test (starts backend, fires webhook, verifies explanation)"
	@echo "  make backend-test   Alias for test"
	@echo "  make frontend-build Build frontend for production"
	@echo "  make dev-backend    Start backend dev server (uvicorn with reload)"
	@echo "  make dev-frontend   Start frontend dev server (next dev)"
	@echo "  make clean          Clean build artifacts and test databases"
	@echo ""

# Run all backend tests (requires local Postgres)
test backend-test:
	DATABASE_URL=postgresql://postgres:postgres@localhost:5432/reclaim_test \
	./backend/venv/bin/pytest backend/tests -q

# Full end-to-end test: start backend, fire webhook, verify explanation
test-e2e:
	@echo "=== Starting E2E Test ==="
	@echo "1. Cleaning test database..."
	DATABASE_URL=postgresql://postgres:postgres@localhost:5432/reclaim_test \
	./backend/venv/bin/python -c "from backend.db.session import SessionLocal; from backend.db.models import Order, PaymentAttempt, RecoveryAction, WebhookEvent; from sqlalchemy import delete; s = SessionLocal(); s.execute(delete(WebhookEvent)); s.execute(delete(RecoveryAction)); s.execute(delete(PaymentAttempt)); s.execute(delete(Order)); s.commit(); print('   Database cleaned'); s.close()"
	@echo "2. Starting backend server..."
	DATABASE_URL=postgresql://postgres:postgres@localhost:5432/reclaim_test \
	./backend/venv/bin/uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 > /tmp/e2e-backend.log 2>&1 & \
	BACKEND_PID=$$!; \
	echo "   Backend PID: $$BACKEND_PID"; \
	sleep 3; \
	@echo "3. Firing payment.failed webhook..."; \
	curl -s -X POST http://127.0.0.1:8000/webhooks/simulate \
	  -H "Content-Type: application/json" \
	  -d '{"entity":"event","account_id":"acc_test","event":"payment.failed","contains":["payment"],"payload":{"payment":{"entity":{"id":"pay_e2e_001","order_id":"order_e2e_001","amount":25000,"currency":"INR","method":"card","status":"failed","attempt_number":1,"error_code":"BAD_REQUEST_PAYMENT_FAILED","error_description":"Payment failed","error_reason":"insufficient_funds","error_source":"customer","error_step":"payment_authentication"}}}' | python3 -m json.tool; \
	@echo "4. Verifying explanation in order detail..."; \
	sleep 1; \
	curl -s http://127.0.0.1:8000/orders/order_e2e_001 | python3 -c "import sys, json; data = json.load(sys.stdin); actions = data.get('recovery_actions', []); assert actions, 'FAIL: No recovery actions'; action = actions[0]; explanation = action.get('explanation'); model = action.get('explanation_model'); assert explanation, 'FAIL: No explanation'; assert model, 'FAIL: No explanation_model'; print(f'   PASS: Explanation found (model: {model})'); print(f'   Text: {explanation[:80]}...')"; \
	@echo "5. Firing payment.captured webhook..."; \
	curl -s -X POST http://127.0.0.1:8000/webhooks/simulate \
	  -H "Content-Type: application/json" \
	  -d '{"entity":"event","account_id":"acc_test","event":"payment.captured","contains":["payment"],"payload":{"payment":{"entity":{"id":"pay_e2e_002","order_id":"order_e2e_001","amount":25000,"currency":"INR","method":"card","status":"captured","attempt_number":1}}}' | python3 -m json.tool; \
	@echo "6. Verifying order recovered and action cancelled..."; \
	sleep 1; \
	curl -s http://127.0.0.1:8000/orders/order_e2e_001 | python3 -c "import sys, json; data = json.load(sys.stdin); assert data.get('status') == 'recovered', f'FAIL: status is {data.get(\"status\")}'; actions = data.get('recovery_actions', []); assert actions, 'FAIL: No recovery actions'; assert actions[0].get('status') == 'cancelled', f'FAIL: status is {actions[0].get(\"status\")}'; print('   PASS: Order recovered, action cancelled')"; \
	@echo "7. Stopping backend..."; \
	kill $$BACKEND_PID 2>/dev/null || true; \
	@echo "=== E2E Test PASSED ==="

# Frontend production build
frontend-build:
	cd frontend && npm run build

# Start backend dev server with reload
dev-backend:
	DATABASE_URL=postgresql://postgres:postgres@localhost:5432/reclaim_test \
	./backend/venv/bin/uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload

# Start frontend dev server
dev-frontend:
	cd frontend && npm run dev

# Clean build artifacts and test databases
clean:
	rm -rf frontend/.next
	rm -rf backend/__pycache__
	rm -rf backend/agent/__pycache__
	rm -rf backend/api/__pycache__
	rm -rf backend/agent/__pycache__
	rm -rf backend/policy/__pycache__
	rm -rf backend/simulator/__pycache__
	rm -rf backend/eval/__pycache__
	rm -rf backend/executor/__pycache__
	rm -rf backend/demo/__pycache__
	rm -rf backend/db/__pycache__
	rm -rf backend/tests/__pycache__
	rm -rf backend/tests/support/__pycache__
	rm -rf /tmp/e2e-backend.log
	rm -rf /tmp/backend_test.log
	@echo "Cleaned build artifacts"
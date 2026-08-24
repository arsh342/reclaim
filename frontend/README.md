# Reclaim — Frontend

Next.js 16 dashboard for the Reclaim recovery policy. It includes the
Overview, Orders list, Decision Inspector, and payment-failure simulator.

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local   # adjust NEXT_PUBLIC_API_URL if backend is elsewhere
```

## Run

```bash
npm run dev
```

Open http://localhost:3000 — the dashboard reads orders, policy decisions,
recovery actions, and evaluation metrics from the FastAPI backend.

## Build / lint

```bash
npm run lint
npm run build
```

## Stack

- Next.js 16 (App Router, Turbopack)
- React 19
- Tailwind v4
- Recharts (Overview bar chart and Decision Inspector ERV comparison)

## Notes

- The Decision Inspector displays ERV in INR. ERV is a risk-adjusted policy
  value used to compare actions, not a partial refund or guaranteed recovery.
- When `alternate_method` wins, the inspector displays the recommended
  method, currently UPI or another card.
- The simulator form accepts order amounts in rupees and sends the webhook
  amount in paise, matching the Razorpay-shaped payload.
- `params` and `searchParams` in route segments are Promises and must be
  `await`ed under Next 16.

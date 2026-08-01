# Zepto AI Review Engine — Frontend

Modern React + Next.js dashboard for the AI Review Engine.

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000

## Build

```bash
npm run build
npm start
```

## Tech Stack

- **Next.js 14** — React framework
- **Tailwind CSS** — Utility-first styling
- **shadcn/ui** — Component primitives
- **Lucide React** — Icon library
- **Framer Motion** — Animations (via Tailwind animate plugin)
- **Recharts** — Data visualizations
- **next-themes** — Dark mode support

## Pages

| Route | Description |
|-------|-------------|
| `/overview` | KPI cards, pipeline health, rating distribution chart |
| `/insights` | Expandable AI insight cards with evidence and segments |
| `/themes` | Theme taxonomy with representative quotes |
| `/segments` | Customer persona cards with behavioral insights |
| `/reviews` | Searchable/filterable review browser with pagination |
| `/questions` | Research questions with evidence and opportunities |

## Deployment

Deploy to Vercel:

```bash
vercel --prod
```

The frontend proxies `/api/*` requests to the Flask backend at `localhost:5000`.

## Branding

- Purple primary (`#7c3aed`)
- Lavender accents
- White backgrounds
- Soft shadows and rounded corners (20px+)
- Inter font

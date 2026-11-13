# HK Funding & Procurement ChessMaster

An intelligent AI procurement and government funding advisor that maps Hong Kong funding schemes (TVP, BUD Fund, EMF) and multi-tier corporate procurement into strategic, tactical chess mechanics.

Built with Google Agent Development Kit (ADK), Gemini, Vertex AI Agent Platform, and A2A Protocol.

---

## Overview

Applying for Hong Kong government technology funding and managing corporate procurement requires strict compliance: mandatory quotation thresholds, vendor vetting, multi-currency bid conversions, and audit-ready RFQ documentation.

**HK Funding & Procurement ChessMaster** acts as a virtual Chief Procurement Officer, categorizing vendors into chess pieces:
- **King / Queen**: Government Compliant Tier (pre-qualified, ISO-certified, audit-ready)
- **Rook / Bishop**: Enterprise Tier (scalable, established regional providers)
- **Knight / Pawn**: SME Tier (flexible, cost-effective agile vendors)

---

## Features & Implemented Tools

1. **Approved Vendor Database & Quotation Search** (`search_vendors`, `get_vendor_details`, `add_vendor`)
   - Backed by Google Cloud Firestore.
   - Filters by vendor tier, category (Cloud ERP, CRM, Cybersecurity, HRMS), and budget range.
   - Registers new vendor bids with live timestamps.

2. **Funding Quotation Rule Evaluator** (`check_funding_quotation_rules`)
   - Enforces Hong Kong statutory quotation minimums:
     - <= HK$50,000: Minimum 2 supplier quotations
     - > HK$50,000 to HK$300,000: Minimum 3 supplier quotations
     - > HK$300,000 to HK$1,400,000: Minimum 5 supplier quotations
     - > HK$1,400,000: Formal competitive tender

3. **Funding Grant & Cashflow Milestones** (`calculate_funding_cashflow`)
   - Calculates 75% TVP matching grants (up to HK$600k cap) and milestone disbursement schedules.

4. **Audit-Ready RFQ Specification Generator** (`generate_rfq_spec`)
   - Generates structured Request for Quotation documents compliant with government audit standards.

5. **Cross-Border Multi-Currency FX Converter** (`convert_procurement_currency`)
   - Fetches live exchange rates via open API to normalize USD, EUR, GBP, JPY, CNY vendor bids into HKD.

6. **Agent Engine Sandbox Code Execution** (`execute_python_in_sandbox` & `code_executor`)
   - Runs isolated Python scripts inside Vertex AI Agent Engine Sandbox for exact mathematical modeling, discounted cashflow projections, and vendor scoring matrix weighting.

7. **Omni Video Generation Tool** (`generate_procurement_video`)
   - Uses Google's Omni model (`gemini-omni-flash-preview`) in Vertex AI global region.
   - Generates dynamic short video clips illustrating procurement bid showcases and tactical chess milestone positioning.
   - Saves video bytes as ADK session artifacts and uploads directly to Google Cloud Storage.

8. **A2UI Rich Card Rendering** (`a2ui_callback`)
   - System prompt built with `A2uiSchemaManager` (version 0.8) and `BasicCatalog`.
   - Emits structured A2UI JSON surfaces rendered natively in both ADK Web and the custom chat frontend.

9. **Cross-Session Long-Term Memory** (`PreloadMemoryTool` & Memory Bank)
   - Integrated with Vertex AI Memory Bank.
   - Automatically remembers company profile, budget preferences, quotation history, and user dietary/health allergies across separate sessions.

---

## Project Structure

```
hk-procure-chess/
├── app/                          # Core ADK Agent
│   ├── agent.py                  # Agent tools, A2UI prompt, root_agent definition
│   ├── a2ui_utils.py             # A2UI after_model_callback
│   ├── fast_api_app.py           # Backend app entrypoint
│   └── app_utils/                # Helpers and lifecycle handlers
├── frontend/                     # Custom Web Frontend
│   ├── main.py                   # FastAPI proxy talking A2A protocol to Agent Engine
│   ├── Dockerfile                # Cloud Run container definition
│   └── static/                   # Pure HTML/JS Chat UI with built-in A2UI renderer
├── tests/                        # Unit and integration test suite
├── pyproject.toml                # Project dependencies managed by uv
└── agents-cli-manifest.yaml      # Agent Engine deployment manifest
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Google Cloud SDK (`gcloud`) with an active GCP project

### Local Development

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Run Local ADK Playground (with Memory Bank attached):**
   ```bash
   uv run adk web --port 8080 --reload_agents --memory_service_uri=agentengine://<MEMORY_BANK_ID>
   ```

3. **Run Local Frontend Proxy & UI:**
   ```bash
   cd frontend
   uv run uvicorn main:app --host 0.0.0.0 --port 8080
   ```

---

## Deployment

### Agent Deployment (Vertex AI Agent Platform)
```bash
agents-cli deploy --update-env-vars
```

### Frontend Deployment (Google Cloud Run)
```bash
cd frontend
gcloud run deploy hk-procure-chess-frontend \
  --source . \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME=<AGENT_ENGINE_RESOURCE_NAME>,AGENT_DIRECTORY=app
```

# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os
import urllib.request
import uuid
from typing import Any
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from .a2ui_utils import a2ui_callback

MODEL = "gemini-3.8-flash"

# IMPORTANT: Hardcode project ID as string. Do NOT use google.auth.default() or GOOGLE_CLOUD_PROJECT
# which return the numeric project number on Agent Platform, breaking Firestore.
PROJECT_ID = "qwiklabs-gcp-03-73dfb5377ddb"

# Public Cloud Storage bucket for generated assets
ASSET_BUCKET_NAME = "hk-procure-chess-assets-e72eb6"

_firestore_client: firestore.Client | None = None
_storage_client: storage.Client | None = None
_genai_global_client: genai.Client | None = None


def get_firestore_client() -> firestore.Client:
    """Returns a singleton Firestore client with the hardcoded GCP project ID."""
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client(project=PROJECT_ID)
    return _firestore_client


def get_storage_client() -> storage.Client:
    """Returns a singleton Cloud Storage client with the hardcoded GCP project ID."""
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client(project=PROJECT_ID)
    return _storage_client


def get_genai_global_client() -> genai.Client:
    """Returns a singleton GenAI client in global region for omni video generation."""
    global _genai_global_client
    if _genai_global_client is None:
        _genai_global_client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="global",
        )
    return _genai_global_client


def search_vendors(
    tier: str = "",
    category: str = "",
    max_budget_hkd: float = 0.0,
) -> list[dict[str, Any]]:
    """Search Hong Kong procurement vendors from the Firestore database.

    Args:
        tier: Filter by vendor procurement tier: 'government_compliant',
              'big_company', or 'medium_sme'. Leave empty for all tiers.
        category: Filter by service category (e.g., 'Cloud ERP', 'Cybersecurity',
                  'AI Automation', 'E-Commerce', 'POS'). Partial match is supported.
        max_budget_hkd: Maximum quotation price in HKD. If 0.0, no budget cap is applied.

    Returns:
        List of matching vendor records including ID, name, tier, chess_role,
        category, typical_quote_hkd, rating, and description.
    """
    db = get_firestore_client()
    collection_ref = db.collection("vendors")
    docs = collection_ref.stream()

    results: list[dict[str, Any]] = []
    for doc in docs:
        data = doc.to_dict()
        if not data:
            continue

        # Filter by tier if specified
        if tier and data.get("tier", "").lower() != tier.lower():
            continue

        # Filter by category if specified
        if category and category.lower() not in data.get("category", "").lower():
            continue

        # Filter by max budget if specified
        if max_budget_hkd > 0 and float(data.get("typical_quote_hkd", 0)) > max_budget_hkd:
            continue

        results.append({
            "id": data.get("id"),
            "name": data.get("name"),
            "tier": data.get("tier"),
            "chess_role": data.get("chess_role"),
            "category": data.get("category"),
            "typical_quote_hkd": data.get("typical_quote_hkd"),
            "rating": data.get("rating"),
            "hk_funding_eligible": data.get("hk_funding_eligible", True),
            "description": data.get("description"),
        })

    return results


def get_vendor_details(vendor_id: str) -> dict[str, Any]:
    """Retrieve full details and sample quotation breakdown for a specific vendor from Firestore.

    Args:
        vendor_id: The unique vendor ID (e.g. 'VND-HK-001', 'VND-HK-005').

    Returns:
        Dictionary with complete vendor profile, BR number, line-item quotation,
        lead time, and compliance statements.
    """
    db = get_firestore_client()
    doc_ref = db.collection("vendors").document(vendor_id)
    doc = doc_ref.get()

    if not doc.exists:
        return {"error": f"Vendor with ID '{vendor_id}' not found in database."}

    return doc.to_dict() or {}


def add_vendor(
    name: str,
    tier: str,
    category: str,
    typical_quote_hkd: float,
    br_number: str = "",
    chess_role: str = "Knight",
    description: str = "",
) -> dict[str, Any]:
    """Add a new vendor with quotation details to the Firestore 'vendors' collection.

    Args:
        name: Full company name (e.g. 'Admiralty Cloud Innovations Ltd').
        tier: Procurement tier: 'government_compliant', 'big_company', or 'medium_sme'.
        category: Solution category (e.g. 'Cloud ERP', 'Cybersecurity', 'CRM').
        typical_quote_hkd: Typical quotation amount in HKD.
        br_number: Hong Kong Business Registration number (e.g. '98765432-000').
        chess_role: Visual chess piece role ('King', 'Queen', 'Rook', 'Bishop', 'Knight', 'Pawn').
        description: Brief overview of capabilities and past track record.

    Returns:
        Status dictionary confirming the created vendor record and assigned vendor ID.
    """
    valid_tiers = ["government_compliant", "big_company", "medium_sme"]
    tier_normalized = tier.lower().strip()
    if tier_normalized not in valid_tiers:
        tier_normalized = "medium_sme"

    db = get_firestore_client()
    vendor_id = f"VND-HK-{uuid.uuid4().hex[:6].upper()}"

    new_vendor: dict[str, Any] = {
        "id": vendor_id,
        "name": name,
        "tier": tier_normalized,
        "chess_role": chess_role,
        "category": category,
        "br_number": br_number or "Pending Verification",
        "hk_funding_eligible": True,
        "typical_quote_hkd": typical_quote_hkd,
        "rating": 5.0,
        "description": description or f"Newly registered {category} supplier under {tier_normalized} tier.",
        "sample_quotation": {
            "quotation_ref": f"QT-NEW-{uuid.uuid4().hex[:4].upper()}",
            "items": [
                {"item": f"{category} Implementation & Setup", "unit_price_hkd": typical_quote_hkd * 0.8, "qty": 1},
                {"item": "Annual Maintenance & Support", "unit_price_hkd": typical_quote_hkd * 0.2, "qty": 1},
            ],
            "total_hkd": typical_quote_hkd,
            "lead_time_weeks": 4,
            "compliance_statement": "Standard non-collusion declaration and competitive quotation clause attached.",
        },
    }

    db.collection("vendors").document(vendor_id).set(new_vendor)
    return {"status": "success", "message": f"Vendor '{name}' successfully registered.", "vendor": new_vendor}


def check_funding_quotation_rules(budget_hkd: float, scheme: str = "TVP") -> dict[str, Any]:
    """Check Hong Kong government funding procurement compliance rules for a project budget.

    Evaluates mandatory written quotation thresholds, non-collusion declaration rules,
    and subsidy grant ratio according to Hong Kong Government procurement guidelines
    (TVP - Technology Voucher Programme, BUD Fund, and EMF).

    Args:
        budget_hkd: Total estimated procurement/project budget in HKD.
        scheme: The funding scheme name ('TVP', 'BUD', or 'EMF'). Defaults to 'TVP'.

    Returns:
        Compliance requirements dictionary including minimum quotations needed,
        tender threshold, subsidy ratio, max funding cap, and mandatory clauses.
    """
    scheme_clean = scheme.upper().strip()

    # Standard Hong Kong Government procurement quotation tiers:
    # <= HK$50,000: Min 2 written quotations
    # HK$50,001 - HK$300,000: Min 3 written quotations
    # HK$300,001 - HK$1,400,000: Min 5 written quotations
    # > HK$1,400,000: Open tender required
    if budget_hkd <= 50000:
        min_quotes = 2
        tier_desc = "Low Value Procurement (<= HK$50,000): Minimum 2 written quotations required."
    elif budget_hkd <= 300000:
        min_quotes = 3
        tier_desc = "Medium Value Procurement (HK$50,001 - HK$300,000): Minimum 3 written quotations required."
    elif budget_hkd <= 1400000:
        min_quotes = 5
        tier_desc = "High Value Procurement (HK$300,001 - HK$1,400,000): Minimum 5 written quotations required."
    else:
        min_quotes = 5
        tier_desc = "Major Procurement (> HK$1,400,000): Formal Open Competitive Tendering required."

    scheme_info = {
        "TVP": {
            "name": "Technology Voucher Programme (TVP)",
            "subsidy_ratio": "75% government funding (3:1 matching)",
            "max_grant_hkd": 600000,
            "max_projects": 6,
            "eligible_expenses": "Custom technology systems, cloud software, hardware, audit fees (up to HK$3,000).",
        },
        "BUD": {
            "name": "BUD Fund (Branding, Upgrading and Domestic Sales)",
            "subsidy_ratio": "50% government funding (1:1 matching)",
            "max_grant_hkd": 7000000,
            "max_projects": 70,
            "eligible_expenses": "Branding, business expansion in Mainland & FTA economies, automation machinery.",
        },
        "EMF": {
            "name": "SME Export Marketing Fund (EMF)",
            "subsidy_ratio": "50% government funding (1:1 matching)",
            "max_grant_hkd": 1000000,
            "max_projects": "Cumulative cap",
            "eligible_expenses": "Export trade exhibitions, digital marketing, website development.",
        },
    }

    current_scheme = scheme_info.get(scheme_clean, scheme_info["TVP"])

    return {
        "budget_hkd": budget_hkd,
        "scheme": current_scheme["name"],
        "min_quotations_required": min_quotes,
        "procurement_tier_rule": tier_desc,
        "subsidy_grant_ratio": current_scheme["subsidy_ratio"],
        "scheme_funding_cap_hkd": current_scheme["max_grant_hkd"],
        "mandatory_compliance_clauses": [
            "Signed Non-Collusion Declaration by all bidders",
            "Independent Supplier Certification (no common ownership/directors)",
            "Valid Hong Kong Business Registration (BR) certificate",
            "Quotation must remain valid for at least 90 days",
        ],
    }


def generate_rfq_spec(
    project_title: str,
    category: str,
    budget_hkd: float,
    deliverables: list[str],
    scheme: str = "TVP",
    deadline_days: int = 14,
) -> dict[str, Any]:
    """Generate an audit-ready Request for Quotation (RFQ) specification package.

    Creates a complete, compliant RFQ document containing project scope,
    deliverables, submission deadlines, and mandatory Hong Kong government
    statutory compliance declarations (Non-Collusion clause, Prevention of Bribery
    Ordinance Cap. 201 warning, and 90-day quotation validity).

    Args:
        project_title: Title of the project or procurement package.
        category: Technical category (e.g. 'Cloud ERP', 'Cybersecurity', 'POS').
        budget_hkd: Total target budget in HKD.
        deliverables: List of key required deliverables and milestone outputs.
        scheme: Hong Kong funding scheme ('TVP', 'BUD', or 'EMF'). Defaults to 'TVP'.
        deadline_days: Days given to suppliers to submit quotations. Defaults to 14.

    Returns:
        Structured dictionary with RFQ reference ID, scope breakdown, statutory
        clauses, and a ready-to-copy Markdown RFQ invitation letter.
    """
    rfq_id = f"RFQ-{scheme.upper()}-{uuid.uuid4().hex[:6].upper()}"
    min_quotes = 2 if budget_hkd <= 50000 else (3 if budget_hkd <= 300000 else 5)

    deliverables_fmt = (
        "\n".join(f"- [ ] {d}" for d in deliverables)
        if deliverables
        else "- [ ] Turnkey system implementation and deployment\n- [ ] 12-Month maintenance and technical support"
    )

    document = (
        f"# REQUEST FOR QUOTATION (RFQ)\n\n"
        f"**RFQ Reference:** `{rfq_id}`  \n"
        f"**Target Scheme:** {scheme.upper()} (Hong Kong Government Funding)  \n"
        f"**Project Title:** {project_title}  \n"
        f"**Category:** {category}  \n"
        f"**Estimated Value Tier:** HKD {budget_hkd:,.2f}  \n"
        f"**Quotation Submission Window:** {deadline_days} Calendar Days  \n"
        f"**Audit Rule:** Minimum {min_quotes} competitive quotations required  \n\n"
        f"### 1. Scope of Work & Key Deliverables\n"
        f"{deliverables_fmt}\n\n"
        f"### 2. Mandatory Submission Requirements\n"
        f"1. Valid Hong Kong Business Registration (BR) certificate copy.\n"
        f"2. Itemized quotation breakdown (Hardware, Software, Implementation, Maintenance).\n"
        f"3. Quotation validity period: Must remain valid for at least 90 calendar days.\n\n"
        f"### 3. Statutory Compliance & Non-Collusion Declarations\n"
        f"- **Non-Collusion Clause:** Bidders certify this quotation is submitted independently without agreement or communication with any other bidder.\n"
        f"- **Prevention of Bribery (Cap. 201):** Any offering of advantage to the applicant's directors or staff will result in immediate disqualification and reporting to the ICAC.\n"
        f"- **Supplier Independence:** Bidder certifies no shared directors or controlling shareholders with the applicant organization.\n"
    )

    return {
        "rfq_id": rfq_id,
        "scheme": scheme.upper(),
        "project_title": project_title,
        "category": category,
        "budget_hkd": budget_hkd,
        "min_quotations_required": min_quotes,
        "deadline_days": deadline_days,
        "deliverables": deliverables,
        "rfq_document": document,
    }


def calculate_funding_cashflow(
    total_budget_hkd: float,
    scheme: str = "TVP",
    initial_working_capital_advance: bool = True,
) -> dict[str, Any]:
    """Calculate the cash flow requirement and retrospective reimbursement schedule for HK funding.

    Computes applicant upfront cash outlay, optional government working capital
    advance (up to 25%), interim milestone payments, final retrospective reimbursement,
    and statutory audit fee allowance under Hong Kong funding guidelines (TVP / BUD).

    Args:
        total_budget_hkd: Total estimated project expenditure in HKD.
        scheme: Hong Kong funding scheme name ('TVP', 'BUD', 'EMF'). Defaults to 'TVP'.
        initial_working_capital_advance: Whether to apply for initial working capital advance.

    Returns:
        Dictionary with upfront capital required, government subsidy breakdown,
        disbursement milestone stages, and required company net contribution.
    """
    scheme_clean = scheme.upper().strip()
    if scheme_clean == "BUD":
        grant_ratio = 0.50
        max_cap = 7000000.0
        audit_allowance = 0.0
    elif scheme_clean == "EMF":
        grant_ratio = 0.50
        max_cap = 1000000.0
        audit_allowance = 0.0
    else:  # TVP default
        grant_ratio = 0.75
        max_cap = 600000.0
        audit_allowance = 3000.0

    expected_grant = min(total_budget_hkd * grant_ratio, max_cap)
    applicant_share = total_budget_hkd - expected_grant

    initial_advance = (expected_grant * 0.25) if initial_working_capital_advance else 0.0
    final_reimbursement = expected_grant - initial_advance

    return {
        "scheme": scheme_clean,
        "total_budget_hkd": total_budget_hkd,
        "government_grant_hkd": expected_grant,
        "applicant_net_cost_hkd": applicant_share,
        "initial_advance_hkd": initial_advance,
        "final_reimbursement_hkd": final_reimbursement,
        "audit_fee_subsidy_hkd": audit_allowance,
        "milestones": [
            {
                "stage": "Stage 1: Application Approval & Agreement Signing",
                "cash_flow": (
                    f"Disburse initial 25% working capital advance: HKD {initial_advance:,.2f}"
                    if initial_advance > 0
                    else "Self-fund initial procurement deposit"
                ),
            },
            {
                "stage": "Stage 2: Implementation & Interim Milestone",
                "cash_flow": f"Applicant pays vendor milestone instalments (estimated HKD {total_budget_hkd * 0.5:,.2f})",
            },
            {
                "stage": "Stage 3: Final Acceptance & Statutory Audit",
                "cash_flow": (
                    f"Submit final audit report (audit fee subsidy up to HKD {audit_allowance:,.0f}); "
                    f"receive final grant reimbursement: HKD {final_reimbursement:,.2f}"
                ),
            },
        ],
    }


def convert_procurement_currency(
    amount: float,
    from_currency: str = "USD",
    to_currency: str = "HKD",
) -> dict[str, Any]:
    """Convert cross-border vendor quotation amounts into HKD (or another currency) using real-time foreign exchange data.

    Essential for Hong Kong government funding applications (such as BUD Fund projects
    in Mainland China or international IT suppliers in USD/EUR) where overseas quotations
    must be converted to HKD to determine procurement threshold tiers and grant subsidies.
    Uses ExchangeRate-API from public-apis (reads optional EXCHANGE_RATE_API_KEY from environment).

    Args:
        amount: Quotation amount in the source currency.
        from_currency: 3-letter source currency code (e.g. 'USD', 'CNY', 'EUR', 'GBP', 'JPY'). Defaults to 'USD'.
        to_currency: 3-letter target currency code (defaults to 'HKD').

    Returns:
        Dictionary with original amount, converted amount in target currency,
        exchange rate, provider timestamp, and procurement threshold tier note.
    """
    from_curr = from_currency.upper().strip()
    to_curr = to_currency.upper().strip()

    api_key = os.getenv("EXCHANGE_RATE_API_KEY")
    if api_key:
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{from_curr}"
    else:
        url = f"https://open.er-api.com/v6/latest/{from_curr}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HKProcureChess/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        if data.get("result") != "success":
            return {"error": f"Failed to fetch exchange rates: {data.get('error-type', 'unknown')}"}

        rates = data.get("rates", {})
        if to_curr not in rates:
            return {"error": f"Target currency '{to_curr}' not found in exchange rates."}

        rate = rates[to_curr]
        converted_amount = round(amount * rate, 2)

        # Determine HK funding procurement quotation tier if converted to HKD
        tier_rule = ""
        if to_curr == "HKD":
            if converted_amount <= 50000:
                tier_rule = "Low Value Procurement (<= HK$50k): Min 2 written quotations required."
            elif converted_amount <= 300000:
                tier_rule = "Medium Value Procurement (HK$50,001 - HK$300,000): Min 3 written quotations required."
            elif converted_amount <= 1400000:
                tier_rule = "High Value Procurement (HK$300,001 - HK$1,400,000): Min 5 written quotations required."
            else:
                tier_rule = "Major Procurement (> HK$1.4M): Open competitive tender required."

        return {
            "source_amount": amount,
            "source_currency": from_curr,
            "target_amount": converted_amount,
            "target_currency": to_curr,
            "exchange_rate": rate,
            "rate_last_updated": data.get("time_last_update_utc", "latest"),
            "hk_procurement_tier_rule": tier_rule,
        }
    except Exception as e:
        return {"error": f"Failed to retrieve currency rates: {str(e)}"}


# Agent Engine Sandbox Code Executor
# Secure sandbox created from deployment_metadata.json reasoningEngine:
# projects/76992949608/locations/us-east1/reasoningEngines/1652600061407789056
SANDBOX_RESOURCE_NAME = (
    "projects/76992949608/locations/us-east1/reasoningEngines/1652600061407789056/sandboxEnvironments/6215913065771171840"
)

sandbox_code_executor = AgentEngineSandboxCodeExecutor(
    sandbox_resource_name=SANDBOX_RESOURCE_NAME,
)


def execute_python_in_sandbox(code: str) -> dict[str, Any]:
    """Execute Python code safely in the Agent Engine cloud sandbox environment.

    Use this tool whenever you need to execute Python scripts for mathematical modeling,
    compound depreciation schedules, multi-tier vendor evaluation scoring, financial cashflow
    projections, or data transformation.

    Args:
        code: Complete Python script to execute. Use print() to output results.

    Returns:
        Dictionary containing stdout, stderr, exit_code, success flag, and sandbox resource name.
    """
    try:
        from vertexai import _genai

        client = _genai.Client(project=PROJECT_ID, location="us-east1")
        res = client.agent_engines.sandboxes.execute_code(
            name=SANDBOX_RESOURCE_NAME,
            input_data={"code": code},
        )
        stdout = ""
        stderr = ""
        exit_code = 0
        for output in res.outputs:
            if output.mime_type == "application/json":
                out_data = json.loads(output.data.decode("utf-8"))
                stdout = out_data.get("msg_out", "")
                stderr = out_data.get("msg_err", "")
                exit_code = out_data.get("exit_status_int", 0)
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "success": exit_code == 0,
            "sandbox_resource": SANDBOX_RESOURCE_NAME,
        }
    except Exception as e:
        return {"error": f"Sandbox execution failed: {str(e)}"}


async def generate_procurement_video(
    item_description: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Generate a short video for a procurement item, vendor pitch, or chess milestone.

    Uses Google's Omni model (gemini-omni-flash-preview) in the global region to create
    a dynamic short video illustrating the specified procurement scenario, funding
    milestone, or tactical chess-themed vendor bid positioning. Saves the generated video
    bytes as a session artifact for the Playground's Artifacts panel, and uploads them directly
    to public Cloud Storage returning the public https URL.

    Args:
        item_description: Description of the procurement item, vendor pitch, funding milestone,
                          or tactical chess bidding scene (e.g. '3D gold chess King piece representing
                          Government Compliant tier vendor with audit certificate').
        tool_context: ADK ToolContext to record the video artifact in the Playground.

    Returns:
        Dictionary containing the public Cloud Storage https URL, artifact filename, and status.
    """
    try:
        client = get_genai_global_client()
        prompt = (
            f"A dynamic, cinematic short video depicting {item_description}. "
            "Professional Hong Kong corporate procurement and tactical chess theme, 3D render, smooth motion."
        )

        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )

        output_video = getattr(interaction, "output_video", None)
        if not output_video:
            steps = getattr(interaction, "steps", []) or []
            for step in steps:
                content = getattr(step, "content", None) or []
                if isinstance(step, dict):
                    content = step.get("content", [])
                for item in content:
                    item_type = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
                    if item_type == "video":
                        output_video = item
                        break
                if output_video:
                    break

        if not output_video:
            return {"error": "No video was returned by gemini-omni-flash-preview."}

        raw_data = output_video.get("data") if isinstance(output_video, dict) else getattr(output_video, "data", None)
        if not raw_data:
            return {"error": "Video data payload was empty in the interaction response."}

        video_bytes = base64.b64decode(raw_data) if isinstance(raw_data, str) else raw_data

        filename = f"procure_video_{uuid.uuid4().hex[:8]}.mp4"

        # 1. Save with tool_context.save_artifact so it shows up in Playground's Artifacts panel
        if tool_context is not None:
            try:
                artifact_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
                await tool_context.save_artifact(
                    filename=filename,
                    artifact=artifact_part,
                )
            except Exception as e:
                print(f"Warning: tool_context.save_artifact failed: {e}")

        # 2. Upload video bytes directly to public Cloud Storage bucket
        storage_client = get_storage_client()
        bucket = storage_client.bucket(ASSET_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type="video/mp4")

        public_url = f"https://storage.googleapis.com/{ASSET_BUCKET_NAME}/{filename}"

        return {
            "status": "success",
            "video_url": public_url,
            "artifact_filename": filename,
            "description": item_description,
            "message": f"Generated short video and uploaded to {public_url}",
        }
    except Exception as e:
        return {"error": f"Failed to generate video with gemini-omni-flash-preview: {str(e)}"}


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except ValueError:
        # Gracefully handle runs where no memory service is attached
        pass
    return None


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are the HK Funding & Procurement ChessMaster, an expert AI assistant specializing in "
        "Hong Kong government funding applications (such as TVP, BUD Fund, and EMF) and multi-tier corporate procurement "
        "(Government Compliant, Big Company/Enterprise, and Medium/SME). "
        "You remember the user's company profile, past quotation inquiries, stated budget preferences, project goals, "
        "and all user allergies, dietary restrictions, and health sensitivities across sessions (e.g., food, medication, or environmental allergies). "
        "Whenever a user shares an allergy or restriction, explicitly acknowledge and remember it. "
        "You help businesses search approved vendors and quotations stored in Firestore, evaluate quotation tier rules "
        "(mandatory minimum quotations: 2 quotes for <=$50k, 3 quotes for $50k-$300k, 5 quotes for $300k-$1.4M), "
        "calculate grant subsidies and cashflow milestones, register new vendor quotations, generate audit-ready RFQ specification documents, "
        "and convert cross-border foreign currency vendor quotes into HKD using real-time exchange rates. "
        "You also have a secure Agent Engine Sandbox Python code execution environment (via execute_python_in_sandbox and code_executor) "
        "to run Python scripts for exact mathematical modeling, discounted cash flows, vendor score matrix weighting, and statistical procurement analysis. "
        "You can also generate short cinematic domain showcase videos (via generate_procurement_video) using Google's Omni model. "
        "Structure your advice strategically, highlighting vendor tiers and their chess roles "
        "(King/Queen for Gov Compliant, Rook/Bishop for Enterprise, Knight/Pawn for SME)."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        client_kwargs={"location": "global"},
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        search_vendors,
        get_vendor_details,
        add_vendor,
        check_funding_quotation_rules,
        generate_rfq_spec,
        calculate_funding_cashflow,
        convert_procurement_currency,
        execute_python_in_sandbox,
        generate_procurement_video,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
    code_executor=sandbox_code_executor,
)

app = App(
    root_agent=root_agent,
    name="app",
)





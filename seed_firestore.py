#!/usr/bin/env python3
"""Seed Firestore with Hong Kong procurement vendors across Gov, Big Co, and SME tiers."""

import sys
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-73dfb5377ddb"

VENDORS = [
    {
        "id": "VND-HK-001",
        "name": "Pacific Tech Solutions Ltd",
        "tier": "government_compliant",
        "chess_role": "Queen",
        "category": "Cloud ERP & CRM",
        "br_number": "38291048-000",
        "hk_funding_eligible": True,
        "typical_quote_hkd": 280000,
        "rating": 4.9,
        "description": "Pre-qualified IT vendor for HK Government TVP and BUD Fund implementations. Full ISO9001 compliance.",
        "sample_quotation": {
            "quotation_ref": "QT-PTS-2026-101",
            "items": [
                {"item": "Core Cloud ERP System Deployment", "unit_price_hkd": 180000, "qty": 1},
                {"item": "Data Migration & Custom Workflow Integration", "unit_price_hkd": 60000, "qty": 1},
                {"item": "12-Month SLA & Gov Audit Support", "unit_price_hkd": 40000, "qty": 1},
            ],
            "total_hkd": 280000,
            "lead_time_weeks": 8,
            "compliance_statement": "Contains mandatory HK Government non-collusion clause and independent supplier certification.",
        },
    },
    {
        "id": "VND-HK-002",
        "name": "Kowloon Digital & Security Corp",
        "tier": "government_compliant",
        "chess_role": "King",
        "category": "Cybersecurity & Infrastructure",
        "br_number": "49102938-000",
        "hk_funding_eligible": True,
        "typical_quote_hkd": 420000,
        "rating": 4.9,
        "description": "Accredited government cybersecurity supplier with ISO 27001 certification. Specializes in TVP / ITF projects.",
        "sample_quotation": {
            "quotation_ref": "QT-KDS-2026-204",
            "items": [
                {"item": "Zero-Trust Endpoint & Network Security", "unit_price_hkd": 250000, "qty": 1},
                {"item": "Automated Penetration Testing & Audit Report", "unit_price_hkd": 100000, "qty": 1},
                {"item": "24/7 SOC Incident Response Monitoring", "unit_price_hkd": 70000, "qty": 1},
            ],
            "total_hkd": 420000,
            "lead_time_weeks": 10,
            "compliance_statement": "Complies with HK Office of the Government Chief Information Officer (OGCIO) baseline security standards.",
        },
    },
    {
        "id": "VND-HK-003",
        "name": "Harbour Enterprise Systems Ltd",
        "tier": "big_company",
        "chess_role": "Rook",
        "category": "AI Automation & Analytics",
        "br_number": "58291039-000",
        "hk_funding_eligible": True,
        "typical_quote_hkd": 190000,
        "rating": 4.8,
        "description": "Enterprise-tier solutions provider for Hang Seng Index listed corporations and multinational APAC headquarters.",
        "sample_quotation": {
            "quotation_ref": "QT-HES-2026-302",
            "items": [
                {"item": "Enterprise AI Analytics Pipeline", "unit_price_hkd": 120000, "qty": 1},
                {"item": "BI Executive Dashboard & Warehouse Link", "unit_price_hkd": 50000, "qty": 1},
                {"item": "High-Availability Deployment Setup", "unit_price_hkd": 20000, "qty": 1},
            ],
            "total_hkd": 190000,
            "lead_time_weeks": 6,
            "compliance_statement": "Enterprise MSA ready with 99.9% uptime SLA guarantee.",
        },
    },
    {
        "id": "VND-HK-004",
        "name": "Victoria Peak Software Group",
        "tier": "big_company",
        "chess_role": "Bishop",
        "category": "Supply Chain & Logistics",
        "br_number": "67192038-000",
        "hk_funding_eligible": True,
        "typical_quote_hkd": 150000,
        "rating": 4.7,
        "description": "Tier-1 logistics and supply chain digital transformation partner across Greater Bay Area and Hong Kong.",
        "sample_quotation": {
            "quotation_ref": "QT-VPS-2026-405",
            "items": [
                {"item": "Warehouse RFID Tracking Integration", "unit_price_hkd": 95000, "qty": 1},
                {"item": "Cross-Border Logistics Manifest API", "unit_price_hkd": 40000, "qty": 1},
                {"item": "Staff Training & Onboarding (4 sessions)", "unit_price_hkd": 15000, "qty": 1},
            ],
            "total_hkd": 150000,
            "lead_time_weeks": 5,
            "compliance_statement": "Complies with Greater Bay Area customs e-manifest data protocols.",
        },
    },
    {
        "id": "VND-HK-005",
        "name": "Lion Rock Agile Works",
        "tier": "medium_sme",
        "chess_role": "Knight",
        "category": "E-Commerce & WebGL",
        "br_number": "78192049-000",
        "hk_funding_eligible": True,
        "typical_quote_hkd": 48000,
        "rating": 4.8,
        "description": "Boutique digital agency providing agile e-commerce storefronts, 3D WebGL experiences, and mobile responsiveness.",
        "sample_quotation": {
            "quotation_ref": "QT-LRA-2026-501",
            "items": [
                {"item": "Next.js + WebGL2 3D Showcase Storefront", "unit_price_hkd": 35000, "qty": 1},
                {"item": "FPS / Stripe Payment Gateway Integration", "unit_price_hkd": 8000, "qty": 1},
                {"item": "SME SEO & Social Commerce Setup", "unit_price_hkd": 5000, "qty": 1},
            ],
            "total_hkd": 48000,
            "lead_time_weeks": 3,
            "compliance_statement": "Under HK$50k tier (requires minimum 2 written quotations for HK funding compliance).",
        },
    },
    {
        "id": "VND-HK-006",
        "name": "Mong Kok Creative Web & POS",
        "tier": "medium_sme",
        "chess_role": "Pawn",
        "category": "Retail POS & Digitalization",
        "br_number": "89102948-000",
        "hk_funding_eligible": True,
        "typical_quote_hkd": 38000,
        "rating": 4.6,
        "description": "Rapid digital deployment for retail, restaurants, and local Hong Kong SMEs seeking simple, cost-effective POS upgrades.",
        "sample_quotation": {
            "quotation_ref": "QT-MKC-2026-602",
            "items": [
                {"item": "Cloud POS & Tablet Terminals Setup", "unit_price_hkd": 24000, "qty": 1},
                {"item": "Inventory Barcode Sync & Receipt Printer Link", "unit_price_hkd": 9000, "qty": 1},
                {"item": "On-Site Shop Setup & Staff Tutorial", "unit_price_hkd": 5000, "qty": 1},
            ],
            "total_hkd": 38000,
            "lead_time_weeks": 2,
            "compliance_statement": "Under HK$50k tier (requires minimum 2 written quotations for HK funding compliance).",
        },
    },
]


def seed():
    print(f"Connecting to Firestore for project: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection("vendors")

    count = 0
    for vendor in VENDORS:
        doc_ref = collection_ref.document(vendor["id"])
        doc_ref.set(vendor)
        print(f"  [+] Seeded vendor: {vendor['id']} - {vendor['name']} (Tier: {vendor['tier']}, Chess: {vendor['chess_role']})")
        count += 1

    print(f"\nSuccessfully seeded {count} vendors into 'vendors' collection!")


if __name__ == "__main__":
    seed()

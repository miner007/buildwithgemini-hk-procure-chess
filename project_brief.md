# My agent: hk-procure-chess
One-liner: A conversational agent that helps Hong Kong businesses plan compliant government funding applications and multi-tier procurement (Gov -> Enterprise -> SME) with a catalog of approved vendors and quotations mapped like a tactical chess board.

Tool coverage:
- Memory: Applicant company profile (SME status, BR number, applied schemes like TVP/BUD, historical budgets, preferred vendors)
- Tools: Check quotation tier rules (2, 3, or 5 quotes based on HKD value), search vetted vendor catalog, validate quotation compliance clauses (non-collusion, supplier independence)
- Catalog/UI: Multi-tier vendor catalog and quotation comparison tables rendered as rich A2UI cards, procurement milestone checklist
- Image gen: Generates tactical procurement milestone visuals and stylized 3D chess board diagrams of vendor bid positioning
- Sandbox: Computes grant matching ratios (e.g. 75% TVP funding up to HK$600k cap, BUD Fund cumulative caps, reimbursement schedules)

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch (pick what fits): code sandbox for funding ratio and reimbursement calculations, WebGL2 3D chess board frontend visualization

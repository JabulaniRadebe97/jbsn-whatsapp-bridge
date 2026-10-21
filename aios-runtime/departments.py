"""JBSN AI OS department registry and safe activation manifest."""
DEPARTMENTS = [
    {"id":"executive","name":"Executive Office","agent":"Jabu","role":"Chief of Staff","mode":"approval_gated","capabilities":["prioritisation","KPI summaries","approval routing"],"live_actions":False},
    {"id":"sales","name":"Sales & Revenue","agent":"Thando","role":"AI SDR and sales assistant","mode":"voice_ready_guarded","capabilities":["lead qualification dialogue","outbound call initiation when enabled","meeting handoff"],"live_actions":False},
    {"id":"marketing","name":"Marketing & Growth","agent":"Zinhle","role":"Growth strategist","mode":"planning_only","capabilities":["campaign plans","content briefs","SEO plans"],"live_actions":False},
    {"id":"creative","name":"Creative Production","agent":"Lerato","role":"Creative producer","mode":"planning_only","capabilities":["website briefs","brand and design briefs","delivery checklists"],"live_actions":False},
    {"id":"client_success","name":"Client Success & Support","agent":"Simphiwe","role":"Client success coordinator","mode":"approval_gated","capabilities":["support triage plans","follow-up drafts","escalation routing"],"live_actions":False},
    {"id":"operations","name":"Operations & Delivery","agent":"Mandla","role":"Operations manager","mode":"planning_only","capabilities":["SOPs","delivery plans","workflow checklists"],"live_actions":False},
    {"id":"finance","name":"Finance & Billing","agent":"Nandi","role":"Finance operations assistant","mode":"approval_gated","capabilities":["invoice checks","reconciliation checklists","cash-flow plans"],"live_actions":False},
    {"id":"people","name":"People & Recruitment","agent":"Ayanda","role":"People operations coordinator","mode":"planning_only","capabilities":["role briefs","onboarding plans","training checklists"],"live_actions":False},
    {"id":"engineering","name":"Engineering & AI OS","agent":"Sibusiso","role":"AI systems engineer","mode":"approval_gated","capabilities":["implementation plans","test plans","release checklists"],"live_actions":False},
    {"id":"security","name":"Security, Privacy & Compliance","agent":"Nomsa","role":"Risk and compliance reviewer","mode":"approval_gated","capabilities":["risk checks","consent checks","release gate reviews"],"live_actions":False},
    {"id":"analytics","name":"Analytics & Intelligence","agent":"Kagiso","role":"Business intelligence analyst","mode":"planning_only","capabilities":["KPI definitions","performance summaries","experiment plans"],"live_actions":False},
    {"id":"reputation","name":"SEO & Reputation","agent":"Lindiwe","role":"SEO and reputation specialist","mode":"planning_only","capabilities":["SEO audits plans","review-response drafts","reputation monitoring plans"],"live_actions":False},
]


def department_manifest():
    """Return a copy of the workforce manifest without secrets or customer data."""
    return {
        "workforce": "JBSN AI OS",
        "activation": "registered_safe_mode",
        "departments_total": len(DEPARTMENTS),
        "departments_with_live_external_actions": 0,
        "voice_outbound_enabled": False,
        "note": "Departments are registered and visible; most actions remain planning-only until tools, credentials, tests, and permissions are configured.",
        "departments": [dict(d, capabilities=list(d["capabilities"])) for d in DEPARTMENTS],
    }

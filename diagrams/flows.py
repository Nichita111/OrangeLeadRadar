"""Source of the per-flow sequence diagrams: python3 diagrams/flows.py writes diagrams/src/fl-nn.json.

Each flow restates the steps of its FL- heading in docs/features/ by hand; the spec stays the source of truth.
REVIEWED records the spec text each diagram was last checked against, and
python3 diagrams/flows.py --check lists the diagrams whose spec text has changed since.
"""
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

P = {
    "sales": ("external", "Sales", "user"),
    "admin": ("external", "Admin", "user"),
    "team": ("external", "Team member", "Sales or Admin"),
    "user": ("external", "User", "Sales or Admin"),
    "api": ("backend", "api", "FastAPI"),
    "db": ("database", "PostgreSQL", "store + job queue"),
    "worker": ("backend", "worker", "job loop"),
    "sched": ("backend", "scheduler", "in the worker"),
    "emb": ("backend", "embedder", "bge-m3"),
    "llm": ("cloud", "OpenRouter", "LLM + Jev"),
    "src": ("external", "Sources", "news, sites, careers"),
    "hub": ("external", "HubSpot", "CRM"),
}

FEATURE = {
    "service-configuration": "Service configuration",
    "accounts-and-discovery": "Accounts and discovery",
    "signal-pipeline": "Signal pipeline",
    "prospect-dashboard": "Prospect dashboard",
    "evaluation-and-feedback": "Evaluation and feedback",
    "outreach-and-crm": "Outreach and CRM",
    "identity-and-access": "Identity and access",
    "audit-trail": "Audit trail",
}

# (id, title, feature, web screen or None, participants, segments[(label, [messages])], cards)
# message: (from, to, label[, variant])
FLOWS = [
    ("fl-01", "Define a service and its signal questions", "service-configuration", "Services, Service editor",
     ["admin", "web", "api", "db", "worker", "llm"],
     [("Create the service", [
         ("admin", "web", "create service"),
         ("web", "api", "POST service (API-08)", "emphasis"),
         ("api", "db", "service + default scoring draft"),
         ("api", "web", "service", "return")]),
      ("Add a question", [
         ("admin", "web", "add signal question"),
         ("web", "api", "create question (API-12)", "emphasis"),
         ("api", "db", "revision 1, draft weight MEDIUM"),
         ("api", "db", "RECLASSIFY run queued", "dashed"),
         ("worker", "db", "claim the run"),
         ("worker", "llm", "ask it of stored passages"),
         ("worker", "db", "findings, then rescore")]),
      ("Revise or retire", [
         ("admin", "web", "edit text, options, sources"),
         ("web", "api", "update question (API-13)"),
         ("api", "db", "revision + 1, RECLASSIFY run")])],
     [("cyan", "Spec", ["FL-01 in Service configuration", "S-CFG-01, S-CFG-02, S-SIG-07"]),
      ("amber", "Counting", ["Hint-term edits keep the revision", "Signals count once a scoring version with the question is active"])]),

    ("fl-02", "Edit and activate scoring settings", "service-configuration", "Scoring settings",
     ["admin", "web", "api", "db", "worker"],
     [("Edit the draft", [
         ("admin", "web", "edit ICP, weights, disqualifiers"),
         ("web", "api", "PUT draft (API-17)", "emphasis"),
         ("api", "db", "validate, save, audit")]),
      ("Preview", [
         ("admin", "web", "Preview impact"),
         ("web", "api", "preview (API-19)"),
         ("api", "web", "rank, band, standing changes", "return")]),
      ("Activate", [
         ("admin", "web", "Activate with a change note", "emphasis"),
         ("web", "api", "activate (API-18)", "emphasis"),
         ("api", "db", "ACTIVE, previous RETIRED, RESCORE"),
         ("worker", "db", "rescore from stored findings"),
         ("web", "api", "poll run (API-35)", "dashed")])],
     [("cyan", "Spec", ["FL-02 in Service configuration", "S-CFG-03, S-CFG-04, S-CFG-06"]),
      ("emerald", "No refetch", ["Activation rescores without fetching or classifying", "Every score names the version that computed it"])]),

    ("fl-03", "Try a question", "service-configuration", "Service editor: Try it",
     ["admin", "web", "api", "emb", "db", "llm"],
     [("Ask", [
         ("admin", "web", "pasted text or an account"),
         ("web", "api", "preview (API-14)", "emphasis")]),
      ("Retrieve", [
         ("api", "emb", "embed the question"),
         ("api", "db", "rank the account's passages")]),
      ("Answer", [
         ("api", "llm", "classify, escalate, quote", "emphasis"),
         ("llm", "api", "strength, confidence, quote", "return"),
         ("api", "db", "AI_CALL audit rows only", "dashed"),
         ("api", "web", "top PREVIEW_MAX_PASSAGES", "return")])],
     [("cyan", "Spec", ["FL-03 in Service configuration", "S-CFG-05 (P1)"]),
      ("amber", "Stores nothing", ["The same rules as the pipeline", "Only the audit of its AI calls is written"])]),

    ("fl-04", "Import accounts from a CSV file", "accounts-and-discovery", "Account import",
     ["sales", "web", "api", "db", "sched"],
     [("Dry run", [
         ("sales", "web", "choose CSV file"),
         ("web", "api", "import, dry run (API-22)", "emphasis"),
         ("api", "web", "created, updated, duplicate, invalid", "return")]),
      ("Import", [
         ("sales", "web", "Import", "emphasis"),
         ("web", "api", "import (API-22)", "emphasis"),
         ("api", "db", "accounts, aliases, sources, audit")]),
      ("Schedule", [
         ("sched", "db", "enqueue refresh of new accounts", "dashed")])],
     [("cyan", "Spec", ["FL-04 in Accounts and discovery", "S-ACC-02"]),
      ("emerald", "Safe import", ["Nothing is written on a dry run", "Changed attributes rescore their account"])]),

    ("fl-05", "Maintain an account and its contacts", "accounts-and-discovery", "Accounts, Account profile",
     ["sales", "web", "api", "db", "llm", "worker"],
     [("Account", [
         ("sales", "web", "add or edit account"),
         ("web", "api", "create (API-21) or update (API-24)", "emphasis"),
         ("api", "db", "MANUAL values, RESCORE run"),
         ("worker", "db", "rescore the account", "dashed")]),
      ("Contacts", [
         ("sales", "web", "add contact with source page"),
         ("web", "api", "create contact (API-26)"),
         ("api", "llm", "map persona from job title"),
         ("api", "db", "contact, no email or phone")]),
      ("Erasure", [
         ("sales", "web", "erase contact", "security"),
         ("web", "api", "delete contact (API-28)", "security"),
         ("api", "db", "deleted, audit without personal data", "security")])],
     [("cyan", "Spec", ["FL-05 in Accounts and discovery", "S-ACC-01, S-ACC-03, S-ACC-04"]),
      ("rose", "Minimal contact data", ["A manual value is never overwritten", "Contacts are erased on request or at retention"])]),

    ("fl-06", "Discover and accept suggested accounts", "accounts-and-discovery", "Suggested accounts",
     ["sales", "web", "api", "db", "worker", "src", "llm"],
     [("Find", [
         ("sales", "web", "Find new accounts"),
         ("web", "api", "discovery run (API-29)", "emphasis"),
         ("api", "db", "DISCOVERY run queued"),
         ("worker", "src", "ICP search, news by hint terms"),
         ("worker", "llm", "triage, name the companies"),
         ("worker", "db", "candidates PENDING, fit estimate")]),
      ("Decide", [
         ("web", "api", "list candidates (API-30)"),
         ("sales", "web", "Accept or Reject", "emphasis"),
         ("web", "api", "accept (API-31), reject (API-32)", "emphasis"),
         ("api", "db", "account DISCOVERED, refresh queued")])],
     [("cyan", "Spec", ["FL-06 in Accounts and discovery", "S-DSC-01, S-DSC-02 (P1)"]),
      ("amber", "A person decides", ["No candidate is fetched or scored before acceptance", "A rejected company is never proposed again"])]),

    ("fl-07", "Refresh one account", "signal-pipeline", "Account detail",
     ["sales", "web", "api", "db", "worker", "src", "emb", "llm"],
     [("Request", [
         ("sales", "web", "Refresh now", "emphasis"),
         ("web", "api", "refresh (API-33)", "emphasis"),
         ("api", "db", "run QUEUED, FETCH jobs")]),
      ("Fetch + process", [
         ("worker", "src", "fetch within the window"),
         ("src", "worker", "items", "return"),
         ("worker", "emb", "embed passages"),
         ("worker", "db", "documents, passages")]),
      ("Signal", [
         ("worker", "llm", "triage, classify (Jev or LLM)", "emphasis"),
         ("worker", "llm", "escalate, extract quote"),
         ("worker", "db", "findings with verbatim quotes")]),
      ("Score", [
         ("worker", "db", "scores for every service, alerts", "emphasis"),
         ("web", "api", "poll run (API-35)", "dashed")])],
     [("cyan", "Spec", ["FL-07 in Signal pipeline", "S-ING-01 to S-ING-04, S-SIG-01 to S-SIG-09"]),
      ("emerald", "Evidence first", ["No quote, no finding", "A failing source ends the run PARTIAL, never faked"])]),

    ("fl-08", "Scheduled refresh cycle", "signal-pipeline", None,
     ["sched", "db", "worker"],
     [("Every tick", [
         ("sched", "db", "take the advisory lock"),
         ("sched", "db", "find due active accounts"),
         ("sched", "db", "enqueue SCHEDULE refreshes", "emphasis")]),
      ("Refresh", [
         ("worker", "db", "claim at lower priority", "emphasis"),
         ("worker", "db", "run the refresh as FL-07"),
         ("worker", "db", "set next_refresh_at")]),
      ("Daily", [
         ("sched", "db", "housekeeping: purge, erase", "dashed")])],
     [("cyan", "Spec", ["FL-08 in Signal pipeline", "S-PIP-02 (P1)"]),
      ("amber", "One at a time", ["Never a second refresh of one account", "Decay is applied every interval"])]),

    ("fl-09", "Reclassify after a question change", "signal-pipeline", "Service editor",
     ["admin", "web", "api", "db", "worker", "llm"],
     [("Change", [
         ("admin", "web", "revise the question"),
         ("web", "api", "update question (API-13)", "emphasis"),
         ("api", "db", "revision + 1, RECLASSIFY run")]),
      ("Reclassify", [
         ("worker", "db", "old findings SUPERSEDED"),
         ("worker", "db", "retrieve passages for it", "emphasis"),
         ("worker", "llm", "classify, escalate, quote"),
         ("worker", "db", "new findings")]),
      ("Rescore", [
         ("worker", "db", "rescore the service", "emphasis")])],
     [("cyan", "Spec", ["FL-09 in Signal pipeline", "S-SIG-07"]),
      ("emerald", "Only this question", ["Nothing is fetched", "Stored passages are retrieved by keyword and meaning"])]),

    ("fl-10", "Rescore after a scoring or data change", "signal-pipeline", "any change screen",
     ["user", "web", "api", "db", "worker"],
     [("Trigger", [
         ("user", "web", "activate, edit, feedback, exception"),
         ("web", "api", "API-18, 24, 44 to 47", "emphasis"),
         ("api", "db", "RESCORE run queued")]),
      ("Rescore", [
         ("worker", "db", "read findings, settings, feedback"),
         ("worker", "db", "new current score if changed", "emphasis"),
         ("worker", "db", "alerts on a band rise", "dashed")])],
     [("cyan", "Spec", ["FL-10 in Signal pipeline", "S-SCO-07"]),
      ("emerald", "Reproducible", ["Same inputs and as-of time give the same row", "Earlier scores stay as history"])]),

    ("fl-11", "Work the prospect list", "prospect-dashboard", "Prospects",
     ["sales", "web", "api", "db"],
     [("Rank", [
         ("sales", "web", "open Prospects for a service"),
         ("web", "api", "prospects (API-39)", "emphasis"),
         ("api", "db", "current scores"),
         ("api", "web", "band, Priority, Fit, Intent", "return")]),
      ("Narrow", [
         ("sales", "web", "filter band, country, industry"),
         ("web", "api", "prospects with filters")]),
      ("Read", [
         ("sales", "web", "select a row: signals drawer"),
         ("sales", "web", "open Account detail", "emphasis")])],
     [("cyan", "Spec", ["FL-11 in Prospect dashboard", "S-PRO-01"]),
      ("amber", "Ranked only", ["Excluded and customer accounts show their reason", "Two top signals per row"])]),

    ("fl-12", "Explain a lead", "prospect-dashboard", "Account detail",
     ["sales", "web", "api", "db"],
     [("Why", [
         ("sales", "web", "open account for a service"),
         ("web", "api", "score view (API-40)", "emphasis"),
         ("web", "api", "findings (API-42)"),
         ("api", "db", "breakdown, findings"),
         ("api", "web", "criteria, quoted signals", "return")]),
      ("Evidence", [
         ("sales", "web", "Evidence on a signal"),
         ("web", "api", "evidence (API-43)", "emphasis"),
         ("api", "web", "excerpt, quote, original link", "return")]),
      ("History", [
         ("sales", "web", "History tab"),
         ("web", "api", "score history (API-41)"),
         ("api", "web", "each change with its cause", "return")])],
     [("cyan", "Spec", ["FL-12 in Prospect dashboard", "S-PRO-02 to S-PRO-04"]),
      ("emerald", "Every point traced", ["The summary is composed from the breakdown", "Every signal opens its source"])]),

    ("fl-13", "Override a disqualifier", "prospect-dashboard", "Account detail",
     ["admin", "web", "api", "db", "worker"],
     [("See why", [
         ("admin", "web", "open an excluded account"),
         ("web", "api", "score view (API-40)"),
         ("api", "web", "disqualifier and matching fact", "return")]),
      ("Exception", [
         ("admin", "web", "add exception with note", "security"),
         ("web", "api", "override (API-44)", "security"),
         ("api", "db", "ACTIVE override, audit, RESCORE"),
         ("worker", "db", "account ranked again", "emphasis")]),
      ("Revoke", [
         ("admin", "web", "revoke", "security"),
         ("web", "api", "revoke (API-45)", "security"),
         ("api", "db", "REVOKED, RESCORE")])],
     [("cyan", "Spec", ["FL-13 in Prospect dashboard", "S-PRO-05, S-SCO-04"]),
      ("rose", "Admin only", ["A note is required", "Both changes are audited"])]),

    ("fl-14", "Act on an alert", "prospect-dashboard", "Alerts",
     ["worker", "db", "api", "web", "sales"],
     [("Raise", [
         ("worker", "db", "strong signal or band rise", "emphasis")]),
      ("Read", [
         ("web", "api", "unread count, poll", "dashed"),
         ("sales", "web", "open Alerts"),
         ("web", "api", "alerts (API-48)", "emphasis"),
         ("api", "web", "what happened, with quote", "return")]),
      ("Acknowledge", [
         ("sales", "web", "Mark read"),
         ("web", "api", "acknowledge (API-49)"),
         ("api", "db", "read for the whole team")])],
     [("cyan", "Spec", ["FL-14 in Prospect dashboard", "S-PRO-06 (P1)"]),
      ("amber", "In the product only", ["No email or chat delivery", "One alert per finding or score row"])]),

    ("fl-15", "Give feedback on a lead or a signal", "evaluation-and-feedback", "Account detail",
     ["sales", "web", "api", "db", "worker"],
     [("Verdict", [
         ("sales", "web", "Wrong on a signal, or a lead verdict"),
         ("web", "api", "API-47 or API-46", "emphasis"),
         ("api", "db", "feedback, REJECTED, label, RESCORE")]),
      ("Rescore", [
         ("worker", "db", "rescore without the signal", "emphasis"),
         ("web", "api", "score view (API-40)"),
         ("api", "web", "Intent without it", "return")])],
     [("cyan", "Spec", ["FL-15 in Evaluation and feedback", "S-EVL-01, S-EVL-02 (P1)"]),
      ("emerald", "Feedback teaches", ["A signal verdict becomes a label", "Already a customer leaves the ranking"])]),

    ("fl-16", "Label passages and run a quality check", "evaluation-and-feedback", "Labelling, Quality report",
     ["team", "admin", "web", "api", "db", "worker", "llm"],
     [("Label", [
         ("team", "web", "open Labelling"),
         ("web", "api", "label queue (API-50)", "emphasis"),
         ("api", "db", "pairs from four strata"),
         ("team", "web", "No, Weak, Clear, Strong"),
         ("web", "api", "label (API-51)"),
         ("api", "db", "MANUAL label")]),
      ("Check", [
         ("admin", "web", "Run quality check", "emphasis"),
         ("web", "api", "evaluation run (API-53)", "emphasis"),
         ("worker", "llm", "replay classification"),
         ("worker", "db", "metrics, passed or not"),
         ("web", "api", "results (API-54, API-55)")])],
     [("cyan", "Spec", ["FL-16 in Evaluation and feedback", "S-EVL-03, S-EVL-04"]),
      ("emerald", "Measured, not assumed", ["Labels are made blind", "The gate needs EVAL_MIN_PRECISION on EVAL_MIN_ITEMS labels"])]),

    ("fl-17", "Draft outreach", "outreach-and-crm", "Outreach composer",
     ["sales", "web", "api", "db", "llm"],
     [("Generate", [
         ("sales", "web", "channel and optional contact"),
         ("web", "api", "generate (API-56)", "emphasis"),
         ("api", "db", "budget guard, top signals"),
         ("api", "llm", "draft from signals", "emphasis"),
         ("llm", "api", "subject, body, cited ids", "return"),
         ("api", "db", "validated draft stored")]),
      ("Export", [
         ("sales", "web", "edit, Copy or Download"),
         ("web", "api", "update, EXPORTED (API-58)")])],
     [("cyan", "Spec", ["FL-17 in Outreach and CRM", "S-OUT-01 (P1)"]),
      ("rose", "Never sent", ["A person sends the message", "Only the signals given may be cited"])]),

    ("fl-18", "Push to HubSpot", "outreach-and-crm", "HubSpot push dialog",
     ["sales", "web", "api", "hub", "db"],
     [("Review", [
         ("sales", "web", "Push to HubSpot"),
         ("sales", "web", "confirm the values", "emphasis")]),
      ("Push", [
         ("web", "api", "push (API-59)", "emphasis"),
         ("api", "hub", "find by domain, update or create"),
         ("hub", "api", "company id", "return"),
         ("api", "db", "crm_sync outcome"),
         ("api", "web", "outcome", "return")])],
     [("cyan", "Spec", ["FL-18 in Outreach and CRM", "S-OUT-02 (P2)"]),
      ("amber", "Optional", ["Without a token the push answers NOT_CONFIGURED", "Every attempt is recorded"])]),

    ("fl-19", "Sign in and sign out", "identity-and-access", "Sign in",
     ["user", "web", "api", "db"],
     [("Sign in", [
         ("user", "web", "open a page"),
         ("web", "user", "Sign in, with return path", "return"),
         ("user", "web", "email and password", "security"),
         ("web", "api", "sign in (API-01)", "security"),
         ("api", "db", "argon2id check, lock on failures"),
         ("api", "web", "HTTP-only session cookie", "return")]),
      ("Sign out", [
         ("user", "web", "Sign out"),
         ("web", "api", "sign out (API-02)"),
         ("api", "db", "session revoked")])],
     [("cyan", "Spec", ["FL-19 in Identity and access", "S-SEC-01, S-SEC-02"]),
      ("rose", "Security", ["Only token hashes are stored", "Locked after LOGIN_MAX_FAILURES failures"])]),

    ("fl-20", "Manage users", "identity-and-access", "Users",
     ["admin", "web", "api", "db"],
     [("Create", [
         ("admin", "web", "New user"),
         ("web", "api", "create user (API-05)", "emphasis"),
         ("api", "db", "user, password hash, audit")]),
      ("Change", [
         ("admin", "web", "role, disable, reset password"),
         ("web", "api", "update user (API-06)", "security"),
         ("api", "db", "disabling revokes sessions"),
         ("api", "web", "no self-demotion", "return")])],
     [("cyan", "Spec", ["FL-20 in Identity and access", "S-SEC-03"]),
      ("rose", "Admin only", ["An Admin cannot demote or disable themselves", "Every change is audited"])]),

    ("fl-21", "Review the audit trail", "audit-trail", "Audit log",
     ["admin", "web", "api", "db"],
     [("Filter", [
         ("admin", "web", "kind, action, user, run, dates"),
         ("web", "api", "audit (API-60)", "emphasis"),
         ("api", "db", "append-only audit_event"),
         ("api", "web", "entries, AI call costs", "return")]),
      ("Follow", [
         ("admin", "web", "expand an entry, open its run"),
         ("web", "api", "run (API-35)")])],
     [("cyan", "Spec", ["FL-21 in Audit trail", "S-AUD-02 (P1)"]),
      ("amber", "Append-only", ["No row is updated or deleted", "No password, token or contact name"])]),

    ("fl-22", "Maintain industries and markets", "service-configuration", "Industries and markets",
     ["admin", "web", "api", "db"],
     [("Add", [
         ("admin", "web", "new industry or market"),
         ("web", "api", "API-72 or API-75", "emphasis"),
         ("api", "db", "ACTIVE entry, audit")]),
      ("Use", [
         ("admin", "web", "choose a market in the ICP"),
         ("web", "api", "save draft (API-17)"),
         ("api", "db", "criterion stores its countries", "emphasis")]),
      ("Retire", [
         ("admin", "web", "retire"),
         ("web", "api", "API-73 or API-76"),
         ("api", "db", "leaves pickers, values kept")])],
     [("cyan", "Spec", ["FL-22 in Service configuration", "S-CFG-07"]),
      ("emerald", "Reproducible", ["A market edit never changes a saved version", "Retired industries stay on their accounts"])]),
]

# Fingerprint of the spec text each diagram was last checked against. The architecture diagram,
# diagrams/src/architecture.json, is written by hand and follows the Topology section of the overview.
REVIEWED = {
    "architecture": "00e0ebc3733a",
    "FL-01": "81661c1aec6d",
    "FL-02": "9e5f8067e7c5",
    "FL-03": "0e87d6c00566",
    "FL-04": "4f9968b69aa1",
    "FL-05": "88939004fd9b",
    "FL-06": "f1091f5001d8",
    "FL-07": "01b6d83be6ae",
    "FL-08": "40129c19a522",
    "FL-09": "4fb45cdc9d22",
    "FL-10": "7fb7e28f6846",
    "FL-11": "826448b42bc6",
    "FL-12": "53d70b3fdd00",
    "FL-13": "37f31fa5fc7c",
    "FL-14": "5b118e45f35b",
    "FL-15": "12b50b475bb7",
    "FL-16": "dbd06d6f2c00",
    "FL-17": "c01c69a93d92",
    "FL-18": "73c8a881a844",
    "FL-19": "03cb2ac514f8",
    "FL-20": "623a8ba73703",
    "FL-21": "11d8217fdecb",
    "FL-22": "cef19bb5e843",
}

STEP = 42
SEG_GAP = 26
TOP = 186


def build(flow):
    fid, title, feature, screen, parts, segments, cards = flow
    participants = []
    for pid in parts:
        if pid == "web":
            participants.append({"id": "web", "type": "frontend", "label": "web", "sublabel": screen})
        else:
            t, label, sub = P[pid]
            participants.append({"id": pid, "type": t, "label": label, "sublabel": sub})
    y = TOP
    messages, segs = [], []
    for label, msgs in segments:
        start = y - 30
        for m in msgs:
            msg = {"from": m[0], "to": m[1], "y": y, "label": m[2]}
            if len(m) > 3:
                msg["variant"] = m[3]
            messages.append(msg)
            y += STEP
        segs.append({"from": start, "to": y - STEP + 14, "label": label})
        y += SEG_GAP
    width = min(1080, max(820, 150 * len(parts) + 120))  # wider falls under 6px text at 1440px
    height = y + 40
    return {
        "schema_version": 1,
        "diagram_type": "sequence",
        "meta": {
            "title": f"{fid.upper()} {title}",
            "quality_profile": "showcase",
            "column_fit": "spread",
            "viewBox": [width, height],
        },
        "participants": participants,
        "segments": segs,
        "messages": messages,
        "cards": [{"dot": d, "title": t, "items": items} for d, t, items in cards],
    }


def sections(path, level):
    """Heading -> body of every heading of the given level in a Markdown file, code fences skipped."""
    out, key, fence = {}, None, False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fence = not fence
        elif not fence and line.startswith("#"):
            key = line[level + 1:] if line.startswith("#" * level + " ") else None
            if key is not None:
                out[key] = []
            continue
        if key is not None:
            out[key].append(line.rstrip())
    return {k: "\n".join(v).strip() for k, v in out.items()}


def spec_fingerprints():
    """Diagram id -> fingerprint of the spec text it restates, heading title included."""
    text = {"architecture": sections(ROOT / "docs/architecture/overview.md", 2)["Topology"]}
    for path in sorted((ROOT / "docs/features").glob("*.md")):
        for heading, body in sections(path, 3).items():
            if re.fullmatch(r"FL-\d\d .+", heading):
                text[heading[:5]] = f"{heading}\n{body}"
    return {k: hashlib.sha256(v.encode("utf-8")).hexdigest()[:12] for k, v in text.items()}


def check():
    current = spec_fingerprints()
    behind = sorted(k for k in current.keys() | REVIEWED.keys() if current.get(k) != REVIEWED.get(k))
    for k in behind:
        if k not in current:
            print(f"{k}: no longer in the specification; remove its diagram and its REVIEWED entry")
        elif k not in REVIEWED:
            print(f"{k}: no diagram yet; add it, then record {current[k]} in REVIEWED")
        else:
            print(f"{k}: the specification changed; update the diagram, then record {current[k]} in REVIEWED")
    print(f"{len(current)} diagrams, {len(behind)} behind the specification")
    return 1 if behind else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        sys.exit(check())
    out = pathlib.Path(__file__).parent / "src"
    out.mkdir(exist_ok=True)
    for flow in FLOWS:
        (out / f"{flow[0]}.json").write_text(json.dumps(build(flow), indent=2) + "\n")
    print(len(FLOWS), "flows written")

#!/usr/bin/env python3
"""
llminteractionlog_explorer.py
------------------------------
CLI debug tool for LlmInteractionLog records — inspect RAG pipeline failures.

Connects to the Django database and lets you drill into any interaction log
at multiple levels of detail to determine whether an error is caused by the
prompt, the retrieved context, the schema, or model behaviour.

Commands:
    list                      All logs (table view)
    list --failed             Only failed interactions
    list --workflow rec|edge  Filter by pipeline
    list --limit N            Show N most recent
    show   <id>               Summary of one log
    prompt <id>               Full reconstructed prompt sent to LLM
    profile <id>              User profile block injected into the prompt
    places  <id>              Candidate place/node documents passed to LLM
    response <id>             Raw LLM output (unmodified)
    diff     <id>             Expected schema vs actual response, field-by-field
    diagnose <id>             Structured failure diagnosis (prompt/context/schema/model)

Usage examples:
    python llminteractionlog_explorer.py list
    python llminteractionlog_explorer.py list --failed
    python llminteractionlog_explorer.py list --workflow rec --limit 10
    python llminteractionlog_explorer.py show 3
    python llminteractionlog_explorer.py diagnose 3
    python llminteractionlog_explorer.py diff 3
    python llminteractionlog_explorer.py --debug list --failed
"""

import argparse
import json
import logging
import os
import shlex
import sys
from pathlib import Path

# ── Django bootstrap ───────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "ferv_project"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ferv_project.settings")

import django  # noqa: E402
django.setup()

from recommendation.models import LlmInteractionLog  #type: ignore  # noqa: E402
from places.models import Place                       #type: ignore  # noqa: E402
from graph.models import GraphNode                    #type: ignore  # noqa: E402

log = logging.getLogger(__name__)

PROMPTS_DIR = REPO_ROOT / "ferv_project" / "prompts"

VALID_REASON_TYPES = {"food", "ambiance", "activity", "neighborhood", "social", "other"}

WORKFLOW_SCHEMAS = {
    "recommendation": (
        '{"recommendations": [{"place_id": "<str>", "rationale": "<str>"}]}'
    ),
    "edge_building": (
        '{"edges": [{"from_node_id": <int>, "to_node_id": <int>, '
        '"weight": <float 0–1>, "reason": "<str ≤5 words>", '
        '"reason_type": "<food|ambiance|activity|neighborhood|social|other>"}]}'
    ),
}


# ── Logging ────────────────────────────────────────────────────────────────────

def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


# ── Display helpers ────────────────────────────────────────────────────────────

SEP_WIDTH = 76


def _sep(title: str = "") -> None:
    if title:
        line = f"── {title} " + "─" * max(0, SEP_WIDTH - len(title) - 4)
    else:
        line = "─" * SEP_WIDTH
    print(line)


def _failed(entry: LlmInteractionLog) -> bool:
    return entry.outcome != "success"


def _outcome_str(entry: LlmInteractionLog) -> str:
    if _failed(entry):
        return f"FAILED [{entry.outcome}]"
    return "success"


def _short_ts(entry: LlmInteractionLog) -> str:
    return entry.created_at.strftime("%Y-%m-%d %H:%M")


def _load_template(prompt_version: str) -> str | None:
    path = PROMPTS_DIR / f"{prompt_version}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else None


def _fetch_log(log_id: int) -> LlmInteractionLog:
    try:
        return LlmInteractionLog.objects.select_related("user").get(pk=log_id)
    except LlmInteractionLog.DoesNotExist:
        print(f"No LlmInteractionLog with id={log_id}.")
        sys.exit(1)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


def _candidates_block_from_place_ids(place_ids: list[str]) -> str:
    """Rebuild the candidates block the same way recommendation_service.py does."""
    lines = []
    places = Place.objects.filter(place_id__in=place_ids).prefetch_related("tags")
    place_map = {p.place_id: p for p in places}
    for pid in place_ids:
        place = place_map.get(pid)
        if not place:
            lines.append(f"place_id: {pid}\n  [NOT FOUND IN DB]")
            continue
        tags = ", ".join(t.tag for t in place.tags.all())
        summary = place.editorial_summary or "No description available."
        document = place.document.text if hasattr(place, "document") else "No document available."
        lines.append(
            f"place_id: {place.place_id}\n"
            f"  name: {place.name}\n"
            f"  neighborhood: {place.neighborhood or 'unknown'}\n"
            f"  rating: {place.rating}\n"
            f"  tags: {tags}\n"
            f"  summary: {summary}\n"
            f"  document: {document}"
        )
    return "\n\n".join(lines)


def _node_block(node: GraphNode) -> str:
    """Rebuild a single node block the same way graph_builder.py does."""
    place = node.place
    tags = ", ".join(t.tag for t in place.tags.all())
    summary = place.editorial_summary or "No description available."
    document = place.document.text if hasattr(place, "document") else "No document available."
    return (
        f"node_id: {node.pk}\n"
        f"  place_id: {place.place_id}\n"
        f"  name: {place.name}\n"
        f"  neighborhood: {place.neighborhood or 'unknown'}\n"
        f"  rating: {place.rating}\n"
        f"  tags: {tags}\n"
        f"  summary: {summary}\n"
        f"  document: {document}"
    )


def _candidates_block_from_node_ids(node_ids: list[int]) -> str:
    """Rebuild the candidates block the same way graph_builder.py does."""
    lines = []
    nodes = (
        GraphNode.objects.filter(pk__in=node_ids)
        .select_related("place")
        .prefetch_related("place__tags")
    )
    node_map = {n.pk: n for n in nodes}
    for nid in node_ids:
        node = node_map.get(nid)
        lines.append(_node_block(node) if node else f"node_id: {nid}\n  [NOT FOUND IN DB]")
    return "\n\n".join(lines)


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_list(args: argparse.Namespace) -> None:
    """Table of interaction logs, newest first."""
    qs = LlmInteractionLog.objects.select_related("user").order_by("-created_at")

    if args.failed:
        qs = qs.exclude(outcome="success")
    if args.workflow:
        mapping = {"rec": "recommendation", "edge": "edge_building"}
        qs = qs.filter(workflow=mapping.get(args.workflow, args.workflow))
    if args.limit:
        qs = qs[: args.limit]

    entries = list(qs)
    if not entries:
        print("No logs found.")
        return

    header = f"{'ID':>5}  {'WORKFLOW':<16}  {'PROMPT VER':<20}  {'MODEL':<26}  {'OUTCOME':<26}  {'CREATED':<16}  USER"
    print()
    print(header)
    print("─" * len(header))
    for entry in entries:
        flag = "  ←" if _failed(entry) else ""
        user_label = entry.user.username if entry.user else "deleted"
        print(
            f"{entry.pk:>5}  {entry.workflow:<16}  {entry.prompt_version:<20}  "
            f"{entry.language_model:<26}  {_outcome_str(entry):<26}  "
            f"{_short_ts(entry):<16}  {user_label}{flag}"
        )

    print()
    failed_count = sum(1 for e in entries if _failed(e))
    print(f"{len(entries)} log(s)  —  {failed_count} failed")


def cmd_show(args: argparse.Namespace) -> None:
    """Structured summary of one log."""
    entry = _fetch_log(args.id)
    payload = entry.input_payload or {}

    _sep(f"Log #{entry.pk}")
    print(f"  Workflow:        {entry.workflow}")
    print(f"  Prompt version:  {entry.prompt_version}")
    print(f"  Embedding model: {entry.embedding_model}")
    print(f"  LLM:             {entry.language_model}")
    print(f"  Outcome:         {_outcome_str(entry)}")
    print(f"  User:            {entry.user_id}")
    print(f"  Created:         {entry.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    print()
    _sep("Input payload")
    if entry.workflow == "recommendation":
        print(f"  prompt_text:  {payload.get('prompt_text', 'n/a')!r}")
        print(f"  n:            {payload.get('n', 'n/a')}")
        print(f"  candidates:   {len(payload.get('candidate_place_ids', []))} place(s)")
        profile = payload.get("profile_snapshot", "")
        snippet = profile[:100] + ("…" if len(profile) > 100 else "") if profile else "(empty)"
        print(f"  profile:      {snippet}")
    elif entry.workflow == "edge_building":
        print(f"  new_node_id:  {payload.get('new_node_id', 'n/a')}")
        print(f"  new_place_id: {payload.get('new_place_id', 'n/a')}")
        print(f"  candidates:   {len(payload.get('candidate_node_ids', []))} node(s)")
        profile = payload.get("profile_snapshot", "")
        snippet = profile[:100] + ("…" if len(profile) > 100 else "") if profile else "(empty)"
        print(f"  profile:      {snippet}")

    print()
    _sep("Raw LLM response (first 600 chars)")
    raw = entry.raw_llm_response or "(empty)"
    print(raw[:600])
    if len(raw) > 600:
        print(f"\n  … [{len(raw) - 600} more chars — use `response {entry.pk}` to see all]")

    if entry.parsed_output:
        print()
        _sep("Parsed output")
        print(json.dumps(entry.parsed_output, indent=2))

    print()
    if _failed(entry):
        print(f"  Tip: run `diagnose {entry.pk}` for a structured failure breakdown.")
    print()


def cmd_prompt(args: argparse.Namespace) -> None:
    """Reconstruct and print the full prompt that was sent to the LLM."""
    entry = _fetch_log(args.id)
    payload = entry.input_payload or {}
    template = _load_template(entry.prompt_version)

    _sep(f"Reconstructed prompt — Log #{entry.pk}  [{entry.prompt_version}]")

    if not template:
        print(f"  Template file not found: {PROMPTS_DIR / entry.prompt_version}.txt")
        print("  Cannot reconstruct prompt. The template may have been renamed or deleted.")
        return

    if entry.workflow == "recommendation":
        candidate_ids = payload.get("candidate_place_ids", [])
        candidates_block = _candidates_block_from_place_ids(candidate_ids)
        filled = template.format(
            prompt_text=payload.get("prompt_text", "(missing)"),
            profile_text=payload.get("profile_snapshot", "(missing)"),
            candidates_block=candidates_block,
            candidate_count=len(candidate_ids),
            n=payload.get("n", 5),
        )

    elif entry.workflow == "edge_building":
        candidate_ids = payload.get("candidate_node_ids", [])
        new_node_id = payload.get("new_node_id")
        candidates_block = _candidates_block_from_node_ids(candidate_ids)
        try:
            new_node = (
                GraphNode.objects.select_related("place")
                .prefetch_related("place__tags")
                .get(pk=new_node_id)
            )
            new_node_block = _node_block(new_node)
        except GraphNode.DoesNotExist:
            new_node_block = f"node_id: {new_node_id}\n  [NOT FOUND IN DB]"
        filled = template.format(
            profile_text=payload.get("profile_snapshot", "(missing)"),
            new_node_id=new_node_id,
            new_node_block=new_node_block,
            candidates_block=candidates_block,
        )

    else:
        print(f"  Unknown workflow: {entry.workflow!r}. Showing raw template.")
        filled = template

    print(filled)
    print()


def cmd_profile(args: argparse.Namespace) -> None:
    """Print only the user profile block that was injected into the prompt."""
    entry = _fetch_log(args.id)
    profile = (entry.input_payload or {}).get("profile_snapshot", "")

    _sep(f"Profile block — Log #{entry.pk}")
    if not profile:
        print("  (empty — no profile was available at call time)")
        print("  This means the LLM had no user signal. Recommendations will be generic.")
    else:
        print(profile)
    print()


def cmd_places(args: argparse.Namespace) -> None:
    """Print the candidate documents passed to the LLM."""
    entry = _fetch_log(args.id)
    payload = entry.input_payload or {}

    _sep(f"Candidate documents — Log #{entry.pk}  [{entry.workflow}]")

    if entry.workflow == "recommendation":
        candidate_ids = payload.get("candidate_place_ids", [])
        if not candidate_ids:
            print("  No candidates in payload.")
            return
        print(f"  {len(candidate_ids)} place(s) retrieved by vector search\n")
        print(_candidates_block_from_place_ids(candidate_ids))

    elif entry.workflow == "edge_building":
        candidate_ids = payload.get("candidate_node_ids", [])
        new_node_id = payload.get("new_node_id")

        print(f"  {len(candidate_ids)} existing in_graph node(s)  +  new node #{new_node_id}\n")

        _sep(f"New node (#{new_node_id})")
        try:
            new_node = (
                GraphNode.objects.select_related("place")
                .prefetch_related("place__tags")
                .get(pk=new_node_id)
            )
            print(_node_block(new_node))
        except GraphNode.DoesNotExist:
            print(f"  node #{new_node_id} not found in DB")

        print()
        _sep("Existing nodes (candidates for edges)")
        if candidate_ids:
            print(_candidates_block_from_node_ids(candidate_ids))
        else:
            print("  (none)")

    print()


def cmd_response(args: argparse.Namespace) -> None:
    """Print the full raw LLM response, unmodified."""
    entry = _fetch_log(args.id)
    _sep(f"Raw LLM response — Log #{entry.pk}  [{entry.outcome}]")
    print(entry.raw_llm_response or "(empty)")
    print()


def cmd_diff(args: argparse.Namespace) -> None:
    """
    Field-by-field comparison of the expected schema against the actual response.
    Most useful for validation_error outcomes.
    """
    entry = _fetch_log(args.id)
    raw = entry.raw_llm_response or ""
    payload = entry.input_payload or {}

    _sep(f"Schema diff — Log #{entry.pk}  [{entry.workflow}]")

    print("EXPECTED SCHEMA:")
    print(f"  {WORKFLOW_SCHEMAS.get(entry.workflow, '(unknown workflow)')}")
    print()
    print(f"OUTCOME: {_outcome_str(entry)}")
    print()
    print("RAW RESPONSE:")
    print(raw)
    print()

    cleaned = _strip_fences(raw)
    print("PARSE ANALYSIS:")

    if raw.strip().startswith("```"):
        print("  Note: Response had markdown fences — stripped before parsing.")

    try:
        parsed = json.loads(cleaned)
        print("  JSON: valid")
    except json.JSONDecodeError as e:
        print(f"  JSON: INVALID — {e}")
        print(f"  First 300 chars of cleaned text: {cleaned[:300]!r}")
        print()
        return

    print()
    print("FIELD CHECKS:")

    if entry.workflow == "recommendation":
        candidate_ids = set(payload.get("candidate_place_ids", []))
        recs = parsed.get("recommendations")
        if recs is None:
            print("  FAIL  top-level key 'recommendations' missing")
        elif not isinstance(recs, list):
            print(f"  FAIL  'recommendations' is {type(recs).__name__}, expected list")
        else:
            print(f"  OK    'recommendations' present — {len(recs)} item(s)")
            for i, item in enumerate(recs):
                issues = []
                if "place_id" not in item:
                    issues.append("missing 'place_id'")
                if "rationale" not in item:
                    issues.append("missing 'rationale'")
                pid = item.get("place_id", "")
                if pid and candidate_ids and pid not in candidate_ids:
                    issues.append(f"place_id {pid!r} not in candidate set (hallucination)")
                status = "FAIL  " if issues else "OK   "
                detail = f"  → {', '.join(issues)}" if issues else f"  place_id={pid!r}"
                print(f"    {status} item[{i}]{detail}")

    elif entry.workflow == "edge_building":
        candidate_ids = set(payload.get("candidate_node_ids", []))
        new_node_id = payload.get("new_node_id")
        valid_ids = candidate_ids | {new_node_id}
        edges = parsed.get("edges")
        if edges is None:
            print("  FAIL  top-level key 'edges' missing")
        elif not isinstance(edges, list):
            print(f"  FAIL  'edges' is {type(edges).__name__}, expected list")
        else:
            print(f"  OK    'edges' present — {len(edges)} edge(s)")
            for i, edge in enumerate(edges):
                issues = []
                for field in ("from_node_id", "to_node_id", "weight", "reason", "reason_type"):
                    if field not in edge:
                        issues.append(f"missing '{field}'")
                rt = edge.get("reason_type", "")
                if rt and rt not in VALID_REASON_TYPES:
                    issues.append(f"reason_type={rt!r} not in enum")
                w = edge.get("weight")
                if w is not None and not (0.0 <= float(w) <= 1.0):
                    issues.append(f"weight={w} out of [0,1]")
                for field in ("from_node_id", "to_node_id"):
                    nid = edge.get(field)
                    if nid is not None and valid_ids and nid not in valid_ids:
                        issues.append(f"{field}={nid} not in valid node set")
                status = "FAIL  " if issues else "OK   "
                detail = (
                    f"  → {', '.join(issues)}"
                    if issues
                    else f"  {edge.get('from_node_id')} → {edge.get('to_node_id')}  [{rt}]  w={w}"
                )
                print(f"    {status} edge[{i}]{detail}")
    print()


def cmd_diagnose(args: argparse.Namespace) -> None:
    """
    Structured failure diagnosis.
    Surfaces which layer likely caused the error:
      CONTEXT  — retrieval breadth, empty profile, too few candidates
      PROMPT   — template issues, LLM ignoring instructions
      SCHEMA   — JSON structure, missing keys, hallucinated IDs, bad enum values
      MODEL    — noisy weights, generic rationales, unexpected behaviour
    """
    entry = _fetch_log(args.id)
    payload = entry.input_payload or {}
    raw = entry.raw_llm_response or ""

    _sep(f"Diagnosis — Log #{entry.pk}  [{entry.workflow}]")
    print(f"  Outcome: {_outcome_str(entry)}\n")

    signals: list[tuple[str, str, str]] = []  # (layer, level, message)

    # ── CONTEXT signals ────────────────────────────────────────────────────────
    profile = payload.get("profile_snapshot", "")
    if not profile:
        signals.append((
            "CONTEXT", "WARNING",
            "Profile was empty at call time. LLM had no user signal — output will be generic.",
        ))

    if entry.workflow == "recommendation":
        n_cands = len(payload.get("candidate_place_ids", []))
        n_req = payload.get("n", 5)
        if n_cands == 0:
            signals.append(("CONTEXT", "ERROR", "Zero candidates retrieved. Retrieval failed before LLM call."))
        elif n_cands < n_req:
            signals.append((
                "CONTEXT", "WARNING",
                f"Only {n_cands} candidates retrieved but {n_req} picks requested. "
                "LLM may hallucinate place_ids to fill the count.",
            ))

    elif entry.workflow == "edge_building":
        n_cands = len(payload.get("candidate_node_ids", []))
        if n_cands == 0:
            signals.append((
                "CONTEXT", "INFO",
                "Zero candidate nodes — LLM call should have been skipped (status transition only path).",
            ))

    # ── PROMPT signals ─────────────────────────────────────────────────────────
    template = _load_template(entry.prompt_version)
    if not template:
        signals.append((
            "PROMPT", "WARNING",
            f"Template {entry.prompt_version}.txt not found locally. Cannot verify prompt structure.",
        ))

    if raw.strip().startswith("```"):
        signals.append((
            "PROMPT", "WARNING",
            "LLM returned markdown fences despite 'Return ONLY valid JSON' instruction. "
            "Fence stripping handled it but indicates instruction-following drift.",
        ))

    # ── SCHEMA signals ─────────────────────────────────────────────────────────
    cleaned = _strip_fences(raw)
    parsed = None
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        signals.append(("SCHEMA", "ERROR", f"Response is not valid JSON: {e}"))

    if parsed is not None:
        if entry.workflow == "recommendation":
            if "recommendations" not in parsed:
                signals.append(("SCHEMA", "ERROR", "Top-level key 'recommendations' missing from response."))
            else:
                candidate_ids = set(payload.get("candidate_place_ids", []))
                for item in parsed.get("recommendations", []):
                    pid = item.get("place_id", "")
                    if pid and candidate_ids and pid not in candidate_ids:
                        signals.append((
                            "SCHEMA", "ERROR",
                            f"place_id {pid!r} not in the candidate set — likely hallucination.",
                        ))

        elif entry.workflow == "edge_building":
            if "edges" not in parsed:
                signals.append(("SCHEMA", "ERROR", "Top-level key 'edges' missing from response."))
            else:
                candidate_ids = set(payload.get("candidate_node_ids", []))
                new_node_id = payload.get("new_node_id")
                valid_ids = candidate_ids | {new_node_id}
                for edge in parsed.get("edges", []):
                    rt = edge.get("reason_type", "")
                    if rt and rt not in VALID_REASON_TYPES:
                        signals.append(("SCHEMA", "WARNING", f"reason_type={rt!r} outside allowed enum."))
                    for field in ("from_node_id", "to_node_id"):
                        nid = edge.get(field)
                        if nid is not None and valid_ids and nid not in valid_ids:
                            signals.append((
                                "SCHEMA", "ERROR",
                                f"{field}={nid} not in this user's node set — authorization issue or hallucination.",
                            ))

    # ── MODEL signals ──────────────────────────────────────────────────────────
    if parsed is not None and entry.workflow == "edge_building":
        weights = [
            e.get("weight")
            for e in parsed.get("edges", [])
            if e.get("weight") is not None
        ]
        if weights:
            avg_w = sum(weights) / len(weights)
            if avg_w > 0.85:
                signals.append((
                    "MODEL", "INFO",
                    f"Average edge weight {avg_w:.2f} — weights cluster high (expected per design; treat as ordinal, not precise).",
                ))

    if parsed is not None and entry.workflow == "recommendation":
        recs = parsed.get("recommendations", [])
        if recs:
            rationales = [r.get("rationale", "") for r in recs]
            generic = [r for r in rationales if len(r.split()) < 4]
            if len(generic) > len(recs) // 2:
                signals.append((
                    "MODEL", "INFO",
                    f"{len(generic)}/{len(recs)} rationales are very short (<4 words). "
                    "May indicate thin profile signal or retrieval candidates that don't match the prompt well.",
                ))

    # ── Output ─────────────────────────────────────────────────────────────────
    layer_order = ["CONTEXT", "PROMPT", "SCHEMA", "MODEL"]
    grouped: dict[str, list[tuple[str, str]]] = {layer: [] for layer in layer_order}
    for layer, level, msg in signals:
        grouped.setdefault(layer, []).append((level, msg))

    if not signals:
        if entry.outcome == "success":
            print("  No issues detected — interaction succeeded.")
        else:
            print("  Outcome is failed but no specific signal identified.")
            print("  Run `response` and `diff` for manual inspection.")
    else:
        for layer in layer_order:
            items = grouped[layer]
            if not items:
                continue
            print(f"  [{layer}]")
            for level, msg in items:
                print(f"    {level}: {msg}")

    print()
    print("  Drill-down commands:")
    for cmd in ("prompt", "places", "profile", "response", "diff"):
        print(f"    {cmd} {entry.pk}")
    print()


# ── Argument parsing ───────────────────────────────────────────────────────────

class _ReplParser(argparse.ArgumentParser):
    """ArgumentParser that raises instead of calling sys.exit so the REPL can recover."""

    def error(self, message: str) -> None:
        raise argparse.ArgumentError(None, message)

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if message:
            print(message, end="")
        if status:
            raise SystemExit(status)


def _build_parser(prog: str = "ferv", require_command: bool = True) -> _ReplParser:
    p = _ReplParser(prog=prog, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--debug", action="store_true", help="Enable debug logging")

    sub = p.add_subparsers(dest="command")
    if require_command:
        sub.required = True

    p_list = sub.add_parser("list", help="Table of all interaction logs")
    p_list.add_argument("--failed", action="store_true", help="Show only failed interactions")
    p_list.add_argument("--workflow", choices=["rec", "edge"], help="Filter by pipeline (rec|edge)")
    p_list.add_argument("--limit", type=int, help="Max rows to show")

    p_show = sub.add_parser("show", help="Structured summary of one log")
    p_show.add_argument("id", type=int, metavar="ID")

    p_prompt = sub.add_parser("prompt", help="Full reconstructed prompt sent to LLM")
    p_prompt.add_argument("id", type=int, metavar="ID")

    p_profile = sub.add_parser("profile", help="User profile block injected into the prompt")
    p_profile.add_argument("id", type=int, metavar="ID")

    p_places = sub.add_parser("places", help="Candidate place/node documents passed to LLM")
    p_places.add_argument("id", type=int, metavar="ID")

    p_response = sub.add_parser("response", help="Raw LLM output (unmodified)")
    p_response.add_argument("id", type=int, metavar="ID")

    p_diff = sub.add_parser("diff", help="Expected schema vs actual response, field-by-field")
    p_diff.add_argument("id", type=int, metavar="ID")

    p_diagnose = sub.add_parser("diagnose", help="Structured failure diagnosis")
    p_diagnose.add_argument("id", type=int, metavar="ID")

    return p


# ── Entry point ────────────────────────────────────────────────────────────────

COMMAND_MAP = {
    "list":     cmd_list,
    "show":     cmd_show,
    "prompt":   cmd_prompt,
    "profile":  cmd_profile,
    "places":   cmd_places,
    "response": cmd_response,
    "diff":     cmd_diff,
    "diagnose": cmd_diagnose,
}

COMMANDS_HELP = "  " + "  ".join(COMMAND_MAP.keys()) + "  help  quit"


def _repl(debug: bool) -> None:
    parser = _build_parser(prog="", require_command=False)
    print("Ferv LLM log explorer — type a command or 'help' / 'quit'")
    print(COMMANDS_HELP)
    print()

    while True:
        try:
            line = input("ferv> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue
        if line in ("quit", "exit", "q"):
            break
        if line in ("help", "?", "h"):
            parser.print_help()
            continue

        try:
            tokens = shlex.split(line)
            args = parser.parse_args(tokens)
            if args.command is None:
                parser.print_help()
                continue
            if not hasattr(args, "debug"):
                args.debug = debug
            log.debug("Parsed args: %s", args)
            COMMAND_MAP[args.command](args)
        except argparse.ArgumentError as e:
            print(f"  Error: {e}")
        except SystemExit:
            pass  # argparse printed its own error or help; just continue
        except Exception as e:
            print(f"  Error: {e}")
            if debug:
                import traceback
                traceback.print_exc()


def main() -> None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--debug", action="store_true")
    top, _ = p.parse_known_args()
    setup_logging(top.debug)
    _repl(top.debug)


if __name__ == "__main__":
    main()

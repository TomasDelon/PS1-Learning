#!/usr/bin/env python3
"""Explicit local handoffs and versioned next lessons. No daemon or automatic grading."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent.parent
FENCE = chr(96) * 3
SID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
NODE = re.compile(r"^(?:L\d{2}|D00|X0[12]|A4|S01|F01)$")
ITEM = re.compile(r"^(?:L\d{2}|D00|X0[12]|A4|S01|F01)-(?:E|V|B)\d{2,}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
F01_DEFAULT_ORIGINS = {
    1: {"L02", "L04"}, 2: {"L03", "L04"}, 3: {"L07"},
    4: {"L08", "L09", "L10"}, 5: {"L11", "L12", "L13"},
    6: {"L15", "L16"}, 7: {"L17"},
}
snap_spec = importlib.util.spec_from_file_location("_ps1_snapshot", ROOT / "tools/snapshot_attempt.py")
snapmod = importlib.util.module_from_spec(snap_spec)
snap_spec.loader.exec_module(snapmod)


class AdaptiveError(ValueError):
    pass


def _fail(message):
    raise AdaptiveError(message)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _object_hash(value):
    return _hash(_dump(value).encode("utf-8"))


def _id(value):
    if not isinstance(value, str) or not SID.fullmatch(value):
        _fail("Identifiant dangereux ou invalide : lettres minuscules, chiffres, _ et - seulement.")
    return value


def _keys(obj, required, optional=()):
    if not isinstance(obj, dict):
        _fail("Un objet JSON structuré est requis.")
    missing = set(required) - set(obj)
    extra = set(obj) - set(required) - set(optional)
    if missing or extra:
        _fail(f"Champs JSON invalides, absents={sorted(missing)}, inconnus={sorted(extra)}.")


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        _fail(f"Texte explicite requis : {field}.")


def _safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        _fail("Chemin relatif portable requis.")
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in ("", ".", "..") for x in value.split("/")) or value.startswith("/"):
        _fail("Le chemin ne doit pas sortir de son dossier.")
    return Path(*p.parts)


def _rmd_meta(path):
    path = Path(path)
    if path.suffix.lower() != ".rmd" or not path.is_file():
        _fail("Un document Rmd existant est requis.")
    text = path.read_text(encoding="utf-8")
    front = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    if not front:
        _fail("En-tête YAML Rmd manquant.")
    ps1 = re.search(r"(?m)^ps1:\s*\n((?:^[ \t]+.*(?:\n|$))*)", front.group(1))
    if not ps1:
        _fail("Métadonnées ps1 absentes.")
    result = {}
    for field in ("lesson_id", "document_role", "minutes"):
        m = re.search(r"(?m)^[ \t]+" + field + r":\s*[\"']?([A-Za-z0-9_]+)[\"']?\s*$", ps1.group(1))
        if not m:
            _fail(f"Métadonnée ps1.{field} illisible.")
        result[field] = m.group(1)
    return result


def _catalog(root):
    root = Path(root).resolve()
    curriculum = _json(root / "data/curriculum.json")
    nodes = {}
    lessons = {}
    exercises = {}
    blocks = {}
    for n in curriculum["nodes"]:
        lid = n.get("id", "")
        if not NODE.fullmatch(lid) or lid in nodes:
            _fail("Identifiants de parcours non sûrs ou dupliqués.")
        nodes[lid] = n
        p = root / "lessons" / lid / "lesson.json"
        if not p.is_file():
            continue
        m = _json(p)
        if m.get("lesson_id") != lid:
            _fail("Le manifeste de leçon ne correspond pas au dossier.")
        lessons[lid] = m
        for e in m.get("exercises", []):
            if not ITEM.fullmatch(e["id"]) or not e["id"].startswith(lid + "-E") or e["id"] in exercises:
                _fail("Identifiant d'exercice invalide.")
            exercises[e["id"]] = (lid, e)
        for b in m.get("blocks", []):
            if not ITEM.fullmatch(b["id"]) or b["id"] in blocks:
                _fail("Identifiant de bloc invalide.")
            blocks[b["id"]] = lid
        for v in m.get("variants", []):
            if not ITEM.fullmatch(v["id"]) or not v["id"].startswith(lid + "-V"):
                _fail("Identifiant de variante invalide.")
            if type(v.get("minutes")) is not int or v["minutes"] <= 0:
                _fail("Durée positive entière requise pour une variante.")
    bank_path = root / "adaptive/additional_variants.json"
    if bank_path.is_file():
        bank = _json(bank_path)
        if bank.get("schema_version") != "2.0.0" or bank.get("kind") != "authored_adaptive_variant_bank":
            _fail("Banque adaptative de version inconnue.")
        seen = {v["id"] for m in lessons.values() for v in m.get("variants", [])}
        for v in bank.get("variants", []):
            owner = v.get("lesson_id")
            if (owner not in lessons or not isinstance(v.get("id"), str)
                    or not ITEM.fullmatch(v["id"]) or not v["id"].startswith(owner + "-V") or v["id"] in seen):
                _fail("Identité de variante complémentaire inconnue ou dupliquée.")
            if (type(v.get("minutes")) is not int or not 1 <= v["minutes"] <= 10
                    or not v.get("for_exercise_ids") or not v.get("source_exercise_ids")
                    or not v.get("rubric_fr") or not v.get("block_ids")):
                _fail("Variante complémentaire incomplète.")
            for key in ("prompt_md", "correction_md", "transfer", "provenance_fr"):
                _text(v.get(key), key)
            for eid in v["for_exercise_ids"] + v["source_exercise_ids"]:
                if eid not in exercises or exercises[eid][0] != owner:
                    _fail("Liaison de variante à un exercice non vérifiée.")
            if any(bid not in blocks for bid in v["block_ids"]):
                _fail("Bloc inconnu dans la banque complémentaire.")
            if any(lid not in lessons for lid in v.get("prerequisite_lesson_ids", [])):
                _fail("Prérequis inconnu dans la banque complémentaire.")
            seen.add(v["id"])
            lessons[owner].setdefault("variants", []).append(v)
    links_path = root / "adaptive/approved_variant_links.json"
    if links_path.is_file():
        registry = _json(links_path)
        if registry.get("schema_version") != "2.0.0" or registry.get("kind") != "reviewed_targeted_variant_links":
            _fail("Registre de liens ciblés inconnu.")
        variants = {v["id"]: v for m in lessons.values() for v in m.get("variants", [])}
        original_hashes = {vid: _object_hash(v) for vid,v in variants.items()}
        for link in registry.get("links", []):
            eid, vid = link.get("exercise_id"), link.get("variant_id")
            if eid not in exercises or vid not in variants or link.get("status") != "INDEPENDENTLY_APPROVED":
                _fail("Lien de reprise non approuvé ou inconnu.")
            owner, exercise = exercises[eid]
            if not vid.startswith(owner + "-V"):
                _fail("Un lien ciblé ne peut changer silencieusement de leçon d'origine.")
            if (link.get("variant_content_sha256") != original_hashes[vid]
                    or link.get("exercise_rubric_sha256") != _object_hash(exercise["rubric_fr"])):
                _fail("Le contenu d'un lien ciblé a changé depuis sa revue indépendante.")
            if not link.get("error_tags") or not set(link["error_tags"]) <= set(exercise.get("error_tags", [])):
                _fail("Portée d'erreur non vérifiée pour un lien ciblé.")
            variant = variants[vid]
            if eid not in variant.setdefault("for_exercise_ids", []):
                variant["for_exercise_ids"].append(eid)
            variant.setdefault("approved_link_scopes", {})[eid] = link
    return root, nodes, lessons, exercises, blocks


def _workspace(root, workspace, create=False):
    root = Path(root).resolve()
    ws = Path(workspace).resolve()
    if ws == root or root.is_relative_to(ws):
        _fail("Choisir un dossier de session distinct du projet et de ses parents.")
    for protected in ("lessons", "sources", "pilot", "data", "templates", "tools", "schemas", "tests"):
        if ws.is_relative_to(root / protected):
            _fail("La session ne peut pas être placée dans les originaux ou le code.")
    if create:
        ws.mkdir(parents=True, exist_ok=True)
    return ws


@contextmanager
def _locked(root, workspace):
    ws = _workspace(root, workspace, True)
    lock = ws / ".adapt-lock"
    try:
        lock.mkdir()
    except FileExistsError:
        _fail("Une autre opération utilise cette session; aucun fichier n'a été écrasé.")
    try:
        yield ws
    finally:
        lock.rmdir()


def _seal(folder):
    for p in Path(folder).rglob("*"):
        if p.is_file():
            p.chmod(0o444)
    for p in sorted(Path(folder).rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if p.is_dir():
            p.chmod(0o555)
    Path(folder).chmod(0o555)


def _manifest_files(folder, exclude=()):
    files = []
    for p in sorted(Path(folder).rglob("*")):
        if p.is_symlink():
            _fail("Les liens symboliques ne sont pas acceptés dans une archive.")
        if p.is_file() and p.relative_to(folder).as_posix() not in exclude:
            data = p.read_bytes()
            files.append(dict(path=p.relative_to(folder).as_posix(), size_bytes=len(data), sha256=_hash(data)))
    return files


def _verify_files(folder, entries):
    for entry in entries:
        rel = _safe_relative(entry["path"])
        p = Path(folder) / rel
        if p.is_symlink() or not p.resolve().is_relative_to(Path(folder).resolve()) or not p.is_file():
            _fail(f"Pièce figée absente ou déplacée : {entry['path']}.")
        if len(p.read_bytes()) != entry["size_bytes"] or _hash(p.read_bytes()) != entry["sha256"]:
            _fail(f"Pièce figée modifiée : {entry['path']}.")


def capture_handoff(root, workspace, handoff_id, lesson_id, first, corrected, reference=None):
    root, nodes, lessons, _, _ = _catalog(root)
    _id(handoff_id)
    if lesson_id not in lessons:
        _fail("Leçon inconnue ou non rédigée.")
    if reference is not None:
        reference = Path(reference)
        reference_origin = "explicit_reference"
    else:
        paired = Path(corrected).parent / (lesson_id + "_Corrige.Rmd")
        reference = paired if paired.is_file() else root / "lessons" / lesson_id / (lesson_id + "_Corrige.Rmd")
        reference_origin = "paired_correction" if paired.is_file() else "canonical_fallback"
    inputs = dict(first=Path(first), corrected=Path(corrected), reference=reference)
    for role, p in inputs.items():
        m = _rmd_meta(p)
        if m["lesson_id"] != lesson_id or m["document_role"] != ("correction" if role == "reference" else "work"):
            _fail("Leçon ou rôle incompatible pour une pièce du dossier.")
    with _locked(root, workspace) as ws:
        dest = ws / "handoffs" / handoff_id
        if dest.exists():
            _fail("Ce dossier existe déjà; les premières tentatives sont immuables.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = Path(tempfile.mkdtemp(prefix=".capture-", dir=ws))
        try:
            snapshots = {}
            for role, p in inputs.items():
                manifest = snapmod.snapshot(p, temp / "snapshots" / role)
                manifest["kind"] = role + "_snapshot"
                manifest["automatic_image_grading"] = False
                (temp / "snapshots" / role / "snapshot_manifest.json").write_text(_dump(manifest), encoding="utf-8")
                snapshots[role] = manifest
            signature = _object_hash({r: m["files"] for r, m in snapshots.items()})
            for old in dest.parent.glob("*/handoff.json"):
                if _json(old).get("attempt_signature") == signature:
                    _fail("Ces trois pièces ont déjà un dossier; une copie ne crée pas une nouvelle tentative.")
            receipt = dict(schema_version="2.0.0", kind="adaptive_handoff", handoff_id=handoff_id,
                           lesson_id=lesson_id, created_at=_now(), status="AWAITING_REVIEW",
                           attempt_signature=signature, snapshots=snapshots,
                           reference_origin=reference_origin,
                           files=_manifest_files(temp), learner_mastery_changed=False,
                           automatic_image_grading=False)
            (temp / "handoff.json").write_text(_dump(receipt), encoding="utf-8")
            temp.rename(dest)
            _seal(dest)
            return dict(status="CAPTURED", handoff_id=handoff_id, path=str(dest), images=sum(len(s["image_references"]) for s in snapshots.values()))
        except Exception:
            if temp.exists():
                shutil.rmtree(temp)
            raise


def _handoff(ws, handoff_id):
    _id(handoff_id)
    p = Path(ws) / "handoffs" / handoff_id
    if not (p / "handoff.json").is_file():
        _fail("Dossier de tentative introuvable.")
    h = _json(p / "handoff.json")
    _verify_files(p, h["files"])
    return p, h


def _validate_evidence(base, manifest, e, snapshot_field=True):
    required = ["path", "sha256", "medium", "certainty", "visually_reviewed", "locator_fr"]
    if snapshot_field:
        required += ["snapshot"]
    _keys(e, required, ["quote"])
    _text(e["locator_fr"], "locator_fr")
    if e["medium"] not in ("text", "image") or e["certainty"] not in ("confirmed", "uncertain"):
        _fail("Type ou certitude de preuve invalide.")
    if type(e["visually_reviewed"]) is not bool or not isinstance(e["sha256"], str) or not SHA.fullmatch(e["sha256"]):
        _fail("Empreinte ou constat visuel invalide.")
    if "quote" in e:
        _text(e["quote"], "quote")
    rel = _safe_relative(e["path"])
    listed = {x["path"]: x for x in manifest["files"]}
    if rel.as_posix() not in listed or listed[rel.as_posix()]["sha256"] != e["sha256"]:
        _fail("La preuve ne correspond pas aux octets de l'instantané.")
    if e["medium"] == "text":
        if rel.as_posix() != manifest["document"]:
            _fail("Une image ne peut pas être déclarée lue comme du texte.")
        if "quote" in e and e["quote"] not in (Path(base) / rel).read_text(encoding="utf-8"):
            _fail("La citation ne figure pas dans le document figé.")
    else:
        images = {x["snapshot_path"] for x in manifest["image_references"]}
        if rel.as_posix() not in images:
            _fail("La preuve image n'est pas une pièce image de l'instantané.")
    return e["certainty"] == "confirmed" and (e["medium"] != "image" or e["visually_reviewed"])


def _validate_review(root, ws, review):
    _, nodes, lessons, exercises, _ = _catalog(root)
    _keys(review, ["schema_version", "review_id", "handoff_id", "reviewer", "resume_after_lesson_id", "introduced_lesson_ids", "findings"])
    if review["schema_version"] != "2.0.0" or review["reviewer"] not in ("human", "assistant"):
        _fail("Version ou auteur de revue non valide.")
    _id(review["review_id"])
    hp, h = _handoff(ws, review["handoff_id"])
    if review["resume_after_lesson_id"] not in nodes or nodes[review["resume_after_lesson_id"]]["order"] < nodes[h["lesson_id"]]["order"]:
        _fail("La reprise ne peut pas précéder la tentative.")
    introduced = review["introduced_lesson_ids"]
    if (not isinstance(introduced, list) or not all(isinstance(x, str) for x in introduced)
            or len(set(introduced)) != len(introduced) or not set(introduced) <= set(nodes)):
        _fail("Liste de prérequis introduits invalide; elle n'est pas un constat de maîtrise.")
    if not isinstance(review["findings"], list):
        _fail("findings doit être une liste.")
    finding_ids = set()
    for f in review["findings"]:
        _keys(f, ["finding_id", "exercise_id", "error_tags", "status", "corrected_status", "observation_fr", "evidence"])
        _id(f["finding_id"])
        if f["finding_id"] in finding_ids:
            _fail("Constat dupliqué dans la même revue.")
        finding_ids.add(f["finding_id"])
        if f["exercise_id"] not in exercises or exercises[f["exercise_id"]][0] != h["lesson_id"]:
            _fail("L'exercice ne fait pas partie de cette tentative.")
        if f["status"] not in ("confirmed", "needs_clarification") or f["corrected_status"] not in ("still_present", "self_corrected", "not_evaluated"):
            _fail("État de constat non valide.")
        _text(f["observation_fr"], "observation_fr")
        if (not isinstance(f["error_tags"], list) or not f["error_tags"]
                or not all(isinstance(x, str) for x in f["error_tags"])
                or len(set(f["error_tags"])) != len(f["error_tags"])):
            _fail("Au moins une étiquette d'erreur distincte est requise.")
        for tag in f["error_tags"]:
            _id(tag)
        if not isinstance(f["evidence"], list):
            _fail("Une liste de preuves est requise.")
        roles = set()
        for e in f["evidence"]:
            if not isinstance(e, dict):
                _fail("Chaque preuve doit être un objet JSON.")
            if e.get("snapshot") not in h["snapshots"]:
                _fail("Rôle d'instantané inconnu.")
            role = e["snapshot"]
            roles.add(role)
            _validate_evidence(hp / "snapshots" / role, h["snapshots"][role], e)
        if roles != {"first", "corrected", "reference"}:
            _fail("Relier le constat à la première tentative, à l'autocorrection et à la référence.")
    return h


def _reviews(ws):
    return [_json(p) for p in sorted((Path(ws) / "reviews").glob("*.json"))]


def _generations(ws):
    return [_json(p) for p in sorted((Path(ws) / "prepared").glob("*/*/generation.json"))]


def _f01_config(node, meta):
    config = meta.get("adaptive_replacement_slots", {})
    if not isinstance(config, dict):
        return None
    size, count = config.get("slot_minutes"), config.get("slot_count")
    proposals, defaults = config.get("proposal_exercise_ids"), config.get("default_exercise_ids")
    authored = {e["id"]: e.get("minutes") for e in meta.get("exercises", [])}
    if (type(size) is not int or type(count) is not int or not 1 <= size <= 30 or not 1 <= count <= 20
            or not isinstance(proposals, list) or not all(isinstance(x, str) for x in proposals)
            or not isinstance(defaults, list) or not all(isinstance(x, str) for x in defaults)
            or len(set(defaults)) != count or len(defaults) != count
            or not set(defaults) <= set(proposals) or size*count > node["minutes"]
            or any(eid not in authored or authored[eid] != size for eid in proposals)):
        return None
    return dict(slot_minutes=size, slot_count=count, proposal_exercise_ids=proposals,
                default_exercise_ids=defaults)


def _review_capacity(node, meta):
    if node["id"] == "F01" and node.get("kind") == "review":
        config = _f01_config(node, meta)
        total = config["slot_minutes"]*config["slot_count"] if config else 0
        return dict(total=total, protected=0, replaceable=total, source="F01_explicit_authored_replacement_slots")
    v = node.get("time_breakdown", {}).get("self_correction_review") if isinstance(node.get("time_breakdown"), dict) else None
    if v is None and isinstance(meta.get("time_breakdown"), dict):
        v = meta["time_breakdown"].get("self_correction_review")
    total = v if type(v) is int and 0 < v <= node["minutes"] else 0
    allocation = meta.get("review_allocation", {})
    correction = allocation.get("correction_minutes")
    anki = allocation.get("anki_minutes")
    known = (type(correction) is int and type(anki) is int and correction >= 0 and anki >= 0
             and correction + anki <= total)
    protected = correction + anki if known else total
    return dict(total=total, protected=protected, replaceable=total-protected,
                source="explicit_current_correction_and_anki" if known else "unknown_allocation_all_protected")


def _budget(node, meta):
    return _review_capacity(node, meta)["replaceable"]


def _ancestors(nodes, lid):
    found = set()
    def visit(x):
        if x in found:
            return
        found.add(x)
        for p in nodes[x].get("depends_on", []):
            if p not in nodes:
                _fail("Prérequis de parcours inconnu.")
            visit(p)
    visit(lid)
    return {x for x in found if nodes[x].get("kind") == "lesson"}


def _required(nodes, blocks, owner, variant):
    result = _ancestors(nodes, owner)
    for lid in variant.get("prerequisite_lesson_ids", []):
        if lid not in nodes:
            _fail("Prérequis explicite inconnu.")
        result |= _ancestors(nodes, lid)
    for bid in variant.get("block_ids", []):
        if bid not in blocks:
            _fail(f"Bloc de prérequis inconnu : {bid}.")
        result |= _ancestors(nodes, blocks[bid])
    return sorted(result, key=lambda x: nodes[x]["order"])


def _eligible(meta, exercise, tags):
    candidates = []
    eb = set(exercise.get("block_ids", []))
    for v in meta.get("variants", []):
        if not v.get("transfer", "").strip() or not v.get("rubric_fr") or not v.get("prompt_md") or not v.get("correction_md"):
            continue
        direct = exercise["id"] in v.get("for_exercise_ids", [])
        if not direct:
            continue
        scope = v.get("approved_link_scopes", {}).get(exercise["id"])
        if scope and not set(tags) & set(scope["error_tags"]):
            continue
        overlap = len(eb & set(v.get("block_ids", [])))
        matched = len(set(tags) & set(v.get("error_tags", [])))
        candidates.append((20*matched + 10 + overlap, v))
    return [v for _, v in sorted(candidates, key=lambda pair: (-pair[0], pair[1]["id"]))]


def build_plan(root, workspace, after_lesson_id=None, pending_review=None):
    root, nodes, lessons, exercises, blocks = _catalog(root)
    ws = _workspace(root, workspace)
    latest = {}
    entries = _reviews(ws) + ([pending_review] if pending_review is not None else [])
    for entry in entries:
        review = entry["review"]
        _validate_review(root, ws, review)
        for f in review["findings"]:
            key = _object_hash([review["handoff_id"], f["exercise_id"], sorted(f["error_tags"])])[:20]
            latest[key] = (review, f)
    assigned = {}
    reserved = {}
    f01_used = {}
    spacing_guards = {}
    for g in _generations(ws):
        for t in g.get("tasks", []):
            if t["task_id"] not in assigned:
                assigned[t["task_id"]] = t
                reserved[g["lesson_id"]] = reserved.get(g["lesson_id"], 0) + t.get("reserved_minutes", t["minutes"])
                if g["lesson_id"] == "F01":
                    f01_used[t["scheduled_slot_index"]] = t
                    if t.get("intervening_slot_index"):
                        spacing_guards.setdefault(t["intervening_slot_index"], set()).add(t["origin_lesson_id"])
    verified = {}
    verification_entries = []
    for p in (ws / "verifications").glob("*/verification.json"):
        v = _json(p)
        _verify_files(p.parent, v["files"])
        verification_entries.append(v)
    for v in sorted(verification_entries, key=lambda x: (x["received_at"], x["verification_id"])):
        verified[v["task_id"]] = v
    if after_lesson_id is not None and after_lesson_id not in nodes:
        _fail("Leçon active inconnue.")
    tasks = {}
    findings = []
    available_nodes = sorted([n for n in nodes.values() if (n.get("kind") == "lesson" or n["id"] == "F01") and n["id"] in lessons], key=lambda n: n["order"])
    f01_config = _f01_config(nodes["F01"], lessons["F01"]) if "F01" in lessons else None

    def default_f01_origins(slot_index):
        eid = f01_config["default_exercise_ids"][slot_index-1]
        return F01_DEFAULT_ORIGINS.get(int(eid.rsplit("E", 1)[1])-1, set())

    def schedule(task, after_order, repair_in_f01=None):
        tid = task["task_id"]
        if tid in tasks:
            return tasks[tid]
        if tid in assigned:
            task.update(assigned[tid])
            task["assignment_status"] = "PREPARED"
        else:
            task["assignment_status"] = "NO_SUITABLE_SLOT"
            task["scheduled_lesson_id"] = None
            for node in available_nodes:
                lid = node["id"]
                if node["order"] <= after_order and not (lid == "F01" and repair_in_f01 is not None):
                    continue
                if not all((root / "lessons" / lid / (lid + "_" + r + ".Rmd")).is_file() for r in ("Travail", "Corrige")):
                    continue
                if lid == "F01" and f01_config is None:
                    continue
                cost = f01_config["slot_minutes"] if lid == "F01" else task["minutes"]
                slot = None
                if lid == "F01":
                    if task["minutes"] > cost - 3:
                        continue
                    start = repair_in_f01 + 2 if repair_in_f01 is not None else 1
                    for candidate in range(start, f01_config["slot_count"]+1):
                        if candidate in f01_used or task["origin_lesson_id"] in spacing_guards.get(candidate, set()):
                            continue
                        if repair_in_f01 is not None:
                            gaps = [j for j in range(repair_in_f01+1, candidate)
                                    if task["origin_lesson_id"] not in (
                                        {f01_used[j]["origin_lesson_id"]} if j in f01_used else default_f01_origins(j))]
                            if not gaps:
                                continue
                            task["intervening_slot_index"] = gaps[0]
                        slot = candidate
                        break
                    if slot is None:
                        continue
                if reserved.get(lid, 0) + cost <= _budget(node, lessons[lid]):
                    task["scheduled_lesson_id"] = lid
                    task["assignment_status"] = "SCHEDULED"
                    task["reserved_minutes"] = cost
                    if lid == "F01":
                        task["scheduled_slot_index"] = slot
                        task["replaced_exercise_id"] = f01_config["default_exercise_ids"][slot-1]
                        task["slot_allocation"] = dict(attempt_minutes=task["minutes"],
                                                       correction_minutes=cost-task["minutes"]-1,
                                                       recall_minutes=1)
                        f01_used[slot] = task
                        if repair_in_f01 is not None:
                            task["spacing_kind"] = "within_session_spacing"
                            spacing_guards.setdefault(task["intervening_slot_index"], set()).add(task["origin_lesson_id"])
                    reserved[lid] = reserved.get(lid, 0) + cost
                    break
        tasks[tid] = task
        return task

    for key, (review, f) in latest.items():
        owner, ex = exercises[f["exercise_id"]]
        hp, h = _handoff(ws, review["handoff_id"])
        clear = f["status"] == "confirmed" and f["corrected_status"] != "not_evaluated"
        for e in f["evidence"]:
            clear = _validate_evidence(hp / "snapshots" / e["snapshot"], h["snapshots"][e["snapshot"]], e) and clear
        record = dict(error_id="error-"+key, handoff_id=review["handoff_id"], exercise_id=f["exercise_id"],
                      review_id=review["review_id"], task_ids=[], status="NEEDS_CLARIFICATION")
        if not clear:
            findings.append(record)
            continue
        choices = _eligible(lessons[owner], ex, f["error_tags"])
        if not choices:
            record["status"] = "AUTHORED_VARIANT_REQUIRED"
            findings.append(record)
            continue
        introduced = set(review["introduced_lesson_ids"]) | {owner}
        ready = [v for v in choices if set(_required(nodes, blocks, owner, v)) <= introduced]
        if not ready:
            required = _required(nodes, blocks, owner, choices[0])
            record.update(status="PREREQUISITE_CONFIRMATION_REQUIRED", missing_prerequisites=sorted(set(required)-introduced))
            findings.append(record)
            continue
        prior_repair = next((t for t in assigned.values() if t.get("stage") == "repair"
                             and record["error_id"] in t.get("error_ids", [])), None)
        repair = next((v for v in ready if prior_repair and v["id"] == prior_repair["variant_id"]), ready[0])
        # The second variant must introduce a different authored decision and remain connected to the exercise.
        alternates = [v for v in ready if v["id"] != repair["id"]]
        floor = nodes[review["resume_after_lesson_id"]]["order"]
        if after_lesson_id:
            floor = max(floor, nodes[after_lesson_id]["order"])
        def make(v, stage):
            taskkey = _object_hash([review["handoff_id"], owner, v["id"], stage])[:20]
            return dict(task_id="task-"+taskkey+"-"+stage, error_ids=[record["error_id"]], stage=stage,
                        origin_lesson_id=owner, variant_id=v["id"], minutes=v["minutes"],
                        required_lesson_ids=_required(nodes, blocks, owner, v),
                        transfer_design_fr=v["transfer"], semantic_transfer_review="AUTHOR_DESIGN_NOT_AUTOMATIC_PROOF",
                        human_verification_required=True, spacing_kind="later_curriculum_node" if stage == "delayed_transfer" else "repair")
        r = schedule(make(repair, "repair"), floor)
        if record["error_id"] not in r["error_ids"]:
            r["error_ids"].append(record["error_id"])
        record["task_ids"].append(r["task_id"])
        if not r["scheduled_lesson_id"]:
            record["status"] = "NO_SUITABLE_SLOT"
        elif not alternates:
            future = [v for v in choices if v["id"] != repair["id"]]
            record["status"] = "TRANSFER_PREREQUISITE_CONFIRMATION_REQUIRED" if future else "DISTINCT_TRANSFER_VARIANT_REQUIRED"
            if future:
                record["missing_prerequisites"] = sorted(set(_required(nodes, blocks, owner, future[0]))-introduced)
        else:
            alt = sorted(alternates, key=lambda x: x["id"])[0]
            later_floor = max(floor, nodes[r["scheduled_lesson_id"]]["order"] + 1)
            f01_repair = r.get("scheduled_slot_index") if r["scheduled_lesson_id"] == "F01" else None
            t = schedule(make(alt, "delayed_transfer"), later_floor, f01_repair)
            if record["error_id"] not in t["error_ids"]:
                t["error_ids"].append(record["error_id"])
            record["task_ids"].append(t["task_id"])
            check = verified.get(t["task_id"])
            record["status"] = "TRANSFER_VERIFIED" if check and check["outcome"] == "pass" else (
                "TRANSFER_REVIEW_REQUIRED" if check else "TRANSFER_PENDING")
            if not t["scheduled_lesson_id"]:
                record["status"] = "NO_LATER_REVIEW_SLOT"
        findings.append(record)
    return dict(schema_version="2.0.0", kind="adaptive_plan", findings=findings,
                tasks=list(tasks.values()), review_minutes_reserved=reserved,
                learner_mastery_changed=False, automatic_grading=False,
                policy_fr="La reprise différée combine rappel non adjacent et décision nouvelle; seul un contrôle explicite de la tentative sans aide peut vérifier le transfert.")


def submit_review(root, workspace, review):
    with _locked(root, workspace) as ws:
        _validate_review(root, ws, review)
        digest = _object_hash(review)
        for e in _reviews(ws):
            if e["review"]["review_id"] == review["review_id"]:
                if e["payload_sha256"] != digest:
                    _fail("Un identifiant de revue existant ne peut pas recevoir un autre contenu.")
                return dict(status="ALREADY_RECORDED", review_id=review["review_id"], plan=build_plan(root, ws))
        entry = dict(received_at=_now(), payload_sha256=digest, review=review, automatic_grading=False)
        # Validate the whole resulting plan before committing this immutable review.
        plan = build_plan(root, ws, pending_review=entry)
        folder = ws / "reviews"
        folder.mkdir(exist_ok=True)
        seq = len(list(folder.glob("*.json"))) + 1
        path = folder / (f"{seq:06d}_" + review["review_id"] + ".json")
        path.write_text(_dump(entry), encoding="utf-8")
        path.chmod(0o444)
        plans = ws / "plans"
        plans.mkdir(exist_ok=True)
        (plans / f"plan-{seq:06d}.json").write_text(_dump(plan), encoding="utf-8")
        (plans / f"plan-{seq:06d}.json").chmod(0o444)
        return dict(status="REVIEW_RECORDED", review_id=review["review_id"], plan=plan)

def _rewrite_document_links(text, source_folder, destination, root):
    def repl(m):
        raw = m.group(2)
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", raw) or raw.startswith(("#", "/", "<")):
            return m.group(0)
        target = (Path(source_folder) / raw).resolve()
        # Files inside this lesson, including its paired correction, are copied together.
        if target.is_relative_to(Path(source_folder).resolve()):
            return m.group(0)
        if target.is_file() and target.is_relative_to(root):
            relative = os.path.relpath(target, destination).replace(os.sep, "/")
            return m.group(1) + relative + ")"
        return m.group(0)
    return re.sub(r"(?<!!)(\[[^\]\n]+\]\()([^)\n]+)\)", repl, text)


def _rename_chunks(text, variant_id):
    number = 0
    def replace(m):
        nonlocal number
        number += 1
        options = m.group(2) or ""
        name = "review_" + variant_id.replace("-", "_") + "_" + str(number)
        return FENCE + "{r " + name + options + "}"
    return re.sub(r"(?m)^" + FENCE + r"\{r(?:\s+([^,}\s]+))?([^}]*)\}", replace, text)


def _variant_payload(root, task, lessons):
    owner = task["origin_lesson_id"]
    variant = next((v for v in lessons[owner]["variants"] if v["id"] == task["variant_id"]), None)
    if not variant:
        _fail("La variante prévue n'existe plus; ne pas fabriquer une autre correction.")
    if variant["minutes"] != task["minutes"]:
        _fail("La durée de la variante a changé depuis sa préparation; revue du plan requise.")
    prompt = variant["prompt_md"]
    correction = variant["correction_md"]
    assets = {}
    base = (root / "lessons" / owner).resolve()
    for target in set(snapmod.image_targets(prompt) + snapmod.image_targets(correction)):
        rel = snapmod._safe_relative(target, base)
        out = Path("review_assets") / variant["id"] / rel
        assets[out.as_posix()] = (base / rel).read_bytes()
        prompt = prompt.replace(target, out.as_posix())
        correction = correction.replace(target, out.as_posix())
    return variant, _rename_chunks(prompt, variant["id"]), _rename_chunks(correction, variant["id"]), assets


def _review_insertion(work, correction, selected, root, lessons, capacity):
    spent = sum(t["minutes"] for t in selected)
    review_minutes = capacity["total"]
    if spent > capacity["replaceable"]:
        _fail("Les reprises dépasseraient le temps de révision disponible.")
    match = re.search(r"(?m)^## 6/6[^\n]*\n", work)
    if not match:
        _fail("La section de rappel 6/6 est absente; aucune insertion automatique n'est faite.")
    end = re.search(r"(?m)^## ", work[match.end():])
    stop = match.end() + end.start() if end else len(work)
    content = work[match.start():stop] + "\n### Reprise ciblée dans le temps disponible\n\n"
    content += (f"**Budget inchangé :** {spent} min de reprise remplacent {spent} des "
                f"{capacity['replaceable']} min libres du créneau de {review_minutes} min. "
                f"Les {capacity['protected']} min de correction actuelle et d’Anki sont préservées. "
                f"Il reste {capacity['replaceable']-spent} min libres.\n"
                "Les exercices principaux et la durée totale de la leçon ne changent pas.\n\n")
    extra_correction = "\n## Correction des reprises insérées\n\nConsulter seulement après une tentative conservée. Une correction lue ne valide pas le transfert.\n\n"
    assets = {}
    for t in selected:
        v, prompt, answer, images = _variant_payload(root, t, lessons)
        assets.update(images)
        anchors = re.findall(r"\{#([^}\s]+)\}", work)
        if v["id"] in anchors:
            _fail("La variante figure déjà dans le prochain document; éviter une insertion dupliquée.")
        title = "Rappel différé avec décision nouvelle" if t["stage"] == "delayed_transfer" else "Reprise ciblée"
        content += (f"### {v['id']} · {title} ({v['minutes']} min) {{#{v['id']}}}\n\n"
                    + prompt + "\n\n**Votre tentative sans correction :**\n\n\n")
        if t["stage"] == "delayed_transfer":
            content += "Produire la réponse sans le corrigé ni une indication de méthode. La vérification des critères sera explicite et séparée.\n\n"
        extra_correction += (f"### {v['id']} · Correction {{#{v['id']}}}\n\n"
                             f"<!-- ps1:review id={v['id']} task={t['task_id']} -->\n\n"
                             + answer + "\n\n**Critères observables :**\n\n"
                             + "\n".join("- " + c for c in v["rubric_fr"]) + "\n\n")
    content += "Conserver la correction et les rappels prévus ci-dessus. Aucun résultat de maîtrise n'est déduit automatiquement.\n\n"
    return work[:match.start()] + content + work[stop:], correction + extra_correction, assets


def _f01_insertion(work, correction, selected, root, lessons, config):
    """Replace explicit authored slots, keeping the separate mixed recall."""
    size, count = config["slot_minutes"], config["slot_count"]
    if len(selected) > count or sum(t.get("reserved_minutes", 0) for t in selected) > size*count:
        _fail("Les créneaux de F01 sont épuisés.")
    assets = {}
    for task in sorted(selected, key=lambda t: t["scheduled_slot_index"]):
        v, prompt, answer, images = _variant_payload(root, task, lessons)
        assets.update(images)
        eid = task["replaced_exercise_id"]
        slot = task["scheduled_slot_index"]
        if slot > count or eid != config["default_exercise_ids"][slot-1]:
            _fail("L'allocation F01 a changé; la version précédente reste conservée.")
        title = f"### Créneau {slot} : reprise ciblée {{#{eid}}}\n\n"
        allocation = task["slot_allocation"]
        if allocation["correction_minutes"] < 2 or allocation["recall_minutes"] < 1:
            _fail("La correction et le rappel minimaux du créneau F01 doivent être préservés.")
        timing = (f"**Budget inchangé : {size} min.** Cette variante remplace le problème initial du créneau. "
                  f"Répartition de ce créneau sélectionné : {allocation['attempt_minutes']} min de tentative, "
                  f"{allocation['correction_minutes']} min de correction, {allocation['recall_minutes']} min de rappel ou d’Anki. "
                  "Ne pas ajouter le problème remplacé.\n\n")
        spacing = ""
        if task.get("spacing_kind") == "within_session_spacing":
            spacing = (f"**Espacement dans cette séance :** effectuer d’abord la reprise puis le créneau "
                       f"intermédiaire {task['intervening_slot_index']}, portant sur un autre travail, "
                       "avant cette tentative sans aide. Ce contrôle ne prouve pas une rétention à long terme.\n\n")
        wb = (title + timing + spacing + f"#### {v['id']} {{#{v['id']}}}\n\n" + prompt
              + "\n\n**Votre tentative, sans corrigé ni indication de méthode :**\n\n")
        cb = (title + f"<!-- ps1:solution id={eid} -->\n\n"
              + f"#### {v['id']} · Correction {{#{v['id']}}}\n\n"
              + f"<!-- ps1:review id={v['id']} task={task['task_id']} -->\n\n" + answer
              + "\n\n**Critères observables :**\n\n" + "\n".join("- " + c for c in v["rubric_fr"]) + "\n\n")
        pattern = r"(?ms)^### [^\n]*\{#" + re.escape(eid) + r"\}\n.*?(?=^#{1,3} |\Z)"
        work, count_work = re.subn(pattern, lambda _: wb, work, count=1)
        correction, count_correction = re.subn(pattern, lambda _: cb, correction, count=1)
        if count_work != 1 or count_correction != 1:
            _fail("Le créneau original F01 ne peut pas être remplacé de façon vérifiable.")
    return work, correction, assets


def _verify_generation(ws, generation_id, allow_work_edit=False):
    if not isinstance(generation_id, str) or not re.fullmatch(r"next-(?:L\d{2}|F01)-v\d{4}", generation_id):
        _fail("Identifiant de version non valide.")
    matches = list((Path(ws) / "prepared").glob("*/" + generation_id + "/generation.json"))
    if len(matches) != 1:
        _fail("Version préparée introuvable ou ambiguë.")
    p = matches[0].parent
    g = _json(matches[0])
    entries = g["files"]
    if allow_work_edit:
        entries = [x for x in entries if x["path"] != g["work_document"]]
    _verify_files(p, entries)
    return p, g


def prepare_next(root, workspace, lesson_id, active_documents):
    root, nodes, lessons, _, _ = _catalog(root)
    if lesson_id not in lessons or (nodes[lesson_id].get("kind") != "lesson" and lesson_id != "F01"):
        _fail("Une prochaine leçon rédigée avec un budget de révision est requise.")
    if not active_documents:
        _fail("Indiquer les documents actifs afin de ne pas les modifier.")
    active_ids = []
    for active in active_documents:
        meta = _rmd_meta(active)
        if meta["lesson_id"] not in nodes:
            _fail("Document actif hors du parcours.")
        active_ids.append(meta["lesson_id"])
    last_active = max(active_ids, key=lambda i: nodes[i]["order"])
    if nodes[lesson_id]["order"] <= nodes[last_active]["order"]:
        _fail("Refus de préparer ou remplacer la leçon active ou une leçon antérieure.")
    source = root / "lessons" / lesson_id
    with _locked(root, workspace) as ws:
        plan = build_plan(root, ws, last_active)
        selected = [t for t in plan["tasks"] if t["scheduled_lesson_id"] == lesson_id]
        # One task shared by two findings is inserted once.
        selected = list({t["task_id"]: t for t in selected}.values())
        if len({t["variant_id"] for t in selected}) != len(selected):
            _fail("Deux tâches utiliseraient le même énoncé dans cette version; revue de plan nécessaire.")
        capacity = _review_capacity(nodes[lesson_id], lessons[lesson_id])
        budget = capacity["replaceable"]
        payloads = {}
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                _fail("Un lien symbolique existe dans les ressources de leçon.")
            if path.is_file():
                payloads[path.relative_to(source).as_posix()] = path.read_bytes()
        wn, cn = lesson_id + "_Travail.Rmd", lesson_id + "_Corrige.Rmd"
        if wn not in payloads or cn not in payloads:
            _fail("La paire complète de la prochaine leçon est absente.")
        source_hash = _object_hash({k: _hash(v) for k, v in payloads.items()})
        variant_snapshots = {}
        for task in selected:
            variant, _, _, _ = _variant_payload(root, task, lessons)
            variant_snapshots[variant["id"]] = variant
        fingerprint = _object_hash([lesson_id, source_hash,
                                   [(t["task_id"], t["variant_id"]) for t in selected],
                                   variant_snapshots])
        prior = [g for g in _generations(ws) if g["lesson_id"] == lesson_id]
        for g in prior:
            if g["input_fingerprint"] == fingerprint:
                p, _ = _verify_generation(ws, g["generation_id"])
                return dict(status="ALREADY_PREPARED", generation_id=g["generation_id"], path=str(p), allocation=g["allocation"])
        number = len(prior) + 1
        gid = f"next-{lesson_id}-v{number:04d}"
        destination = ws / "prepared" / lesson_id / gid
        if destination.exists():
            _fail("La destination existe; aucune version n'est écrasée.")
        work = payloads[wn].decode("utf-8")
        correction = payloads[cn].decode("utf-8")
        if selected:
            if lesson_id == "F01":
                work, correction, assets = _f01_insertion(work, correction, selected, root, lessons,
                                                         _f01_config(nodes[lesson_id], lessons[lesson_id]))
            else:
                work, correction, assets = _review_insertion(work, correction, selected, root, lessons, capacity)
            payloads.update(assets)
        work = _rewrite_document_links(work, source, destination, root)
        correction = _rewrite_document_links(correction, source, destination, root)
        payloads[wn] = work.encode("utf-8")
        payloads[cn] = correction.encode("utf-8")
        spent = sum(t.get("reserved_minutes", t["minutes"]) for t in selected)
        allocation = dict(total_lesson_minutes=nodes[lesson_id]["minutes"],
                          original_review_minutes=capacity["total"], protected_current_review_minutes=capacity["protected"],
                          replaceable_review_minutes=budget, inserted_review_minutes=spent,
                          remaining_review_minutes=capacity["total"]-spent,
                          remaining_discretionary_minutes=budget-spent, added_minutes=0,
                          policy_source=capacity["source"])
        temp = Path(tempfile.mkdtemp(prefix=".next-", dir=ws))
        try:
            for rel, data in payloads.items():
                p = temp / _safe_relative(rel)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
            for name in (wn, cn):
                text = (temp / name).read_text(encoding="utf-8")
                anchors = re.findall(r"\{#([^}\s]+)\}", text)
                if len(anchors) != len(set(anchors)):
                    _fail("L'insertion créerait des identifiants dupliqués.")
                for target in snapmod.image_targets(text):
                    snapmod._safe_relative(target, temp.resolve())
            manifest = dict(schema_version="2.0.0", kind="prepared_next_lesson",
                generation_id=gid, lesson_id=lesson_id, created_at=_now(),
                source_folder=source.relative_to(root).as_posix(), source_payload_sha256=source_hash,
                input_fingerprint=fingerprint, predecessor=prior[-1]["generation_id"] if prior else None,
                status="REVIEW_INSERTED" if selected else "BASE_READY_REVIEW_PENDING",
                work_document=wn, correction_document=cn, tasks=selected, allocation=allocation,
                variant_snapshots=variant_snapshots,
                required_next_prerequisites=nodes[lesson_id].get("depends_on", []),
                prerequisites_are_mastery_claim=False, learner_mastery_changed=False,
                r_execution="NOT_RUN", image_grading="NOT_PERFORMED", files=_manifest_files(temp))
            (temp / "generation.json").write_text(_dump(manifest), encoding="utf-8")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp.rename(destination)
            (destination / "generation.json").chmod(0o444)
            return dict(status=manifest["status"], generation_id=gid, path=str(destination),
                        work=str(destination/wn), correction=str(destination/cn), allocation=allocation)
        except Exception:
            if temp.exists():
                shutil.rmtree(temp)
            raise


def verify_transfer(root, workspace, verification, attempt):
    root, _, lessons, _, _ = _catalog(root)
    _keys(verification, ["schema_version", "verification_id", "generation_id", "task_id",
                        "reviewer", "unaided", "new_decision_observed", "outcome",
                        "method_choice_fr", "rubric_results"], ["intervening_task_completed"])
    if verification["schema_version"] != "2.0.0" or verification["reviewer"] not in ("human", "assistant"):
        _fail("Version ou auteur de vérification invalide.")
    _id(verification["verification_id"])
    _id(verification["task_id"])
    if type(verification["unaided"]) is not bool or type(verification["new_decision_observed"]) is not bool:
        _fail("Les conditions de vérification doivent être explicites.")
    if "intervening_task_completed" in verification and type(verification["intervening_task_completed"]) is not bool:
        _fail("Le constat de tâche intermédiaire doit être booléen.")
    if verification["outcome"] not in ("pass", "retry", "uncertain"):
        _fail("Résultat explicite de revue non valide.")
    _text(verification["method_choice_fr"], "method_choice_fr")
    with _locked(root, workspace) as ws:
        generation_path, g = _verify_generation(ws, verification["generation_id"], allow_work_edit=True)
        task = next((t for t in g["tasks"] if t["task_id"] == verification["task_id"]), None)
        if task is None or task["stage"] != "delayed_transfer":
            _fail("Seule une tâche de transfert différé préparée peut recevoir cette vérification.")
        variant = g["variant_snapshots"][task["variant_id"]]
        attempt_meta = _rmd_meta(attempt)
        if attempt_meta["lesson_id"] != g["lesson_id"] or attempt_meta["document_role"] != "work":
            _fail("La nouvelle tentative ne correspond pas à la leçon préparée.")
        if "{#"+variant["id"]+"}" not in Path(attempt).read_text(encoding="utf-8"):
            _fail("L'énoncé de transfert est absent de la tentative.")
        results = verification["rubric_results"]
        if not isinstance(results, list) or len(results) != len(variant["rubric_fr"]):
            _fail("Chaque critère de la variante doit être revu.")
        indices = []
        for r in results:
            _keys(r, ["criterion_index", "result", "evidence"])
            if type(r["criterion_index"]) is not int or r["result"] not in ("met", "not_met", "uncertain"):
                _fail("Résultat de critère invalide.")
            indices.append(r["criterion_index"])
        if sorted(indices) != list(range(1, len(variant["rubric_fr"])+1)):
            _fail("Critères omis ou dupliqués.")
        destination = ws / "verifications" / verification["verification_id"]
        temp = Path(tempfile.mkdtemp(prefix=".transfer-", dir=ws))
        try:
            snapshot = snapmod.snapshot(Path(attempt), temp/"attempt")
            certain = True
            for r in results:
                certain = _validate_evidence(temp/"attempt", snapshot, r["evidence"], False) and certain
            if destination.exists():
                old = _json(destination/"verification.json")
                _verify_files(destination, old["files"])
                if (old["input_sha256"] == _object_hash(verification)
                        and old["snapshot"]["files"] == snapshot["files"]):
                    shutil.rmtree(temp)
                    return dict(status="ALREADY_RECORDED", outcome=old["outcome"])
                _fail("Une vérification existante ne peut pas être remplacée, ni recevoir une tentative modifiée.")
            passed = (verification["outcome"] == "pass" and verification["unaided"]
                      and verification["new_decision_observed"] and certain
                      and (task.get("spacing_kind") != "within_session_spacing"
                           or verification.get("intervening_task_completed") is True)
                      and all(r["result"] == "met" for r in results))
            outcome = "pass" if passed else ("retry" if verification["outcome"] == "retry" else "uncertain")
            report = dict(schema_version="2.0.0", kind="explicit_transfer_review",
                verification_id=verification["verification_id"], task_id=task["task_id"],
                outcome=outcome, input_sha256=_object_hash(verification), received_at=_now(),
                verification_scope=task.get("spacing_kind", "later_curriculum_node"),
                reviewer_input=verification, snapshot=snapshot, files=_manifest_files(temp),
                automatic_grading=False, learner_mastery_changed=False)
            (temp/"verification.json").write_text(_dump(report),encoding="utf-8")
            destination.parent.mkdir(parents=True,exist_ok=True)
            temp.rename(destination)
            _seal(destination)
            return dict(status="TRANSFER_REVIEW_RECORDED", outcome=outcome,
                        learner_mastery_changed=False, path=str(destination))
        except Exception:
            if temp.exists():
                shutil.rmtree(temp)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--workspace", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--handoff-id", required=True)
    capture.add_argument("--lesson", required=True)
    capture.add_argument("--first", type=Path, required=True)
    capture.add_argument("--corrected", type=Path, required=True)
    capture.add_argument("--reference", type=Path)
    review = sub.add_parser("review")
    review.add_argument("--input", type=Path, required=True)
    prepare = sub.add_parser("prepare-next")
    prepare.add_argument("--lesson", required=True)
    prepare.add_argument("--active", type=Path, action="append", required=True)
    verify = sub.add_parser("verify-transfer")
    verify.add_argument("--input", type=Path, required=True)
    verify.add_argument("--attempt", type=Path, required=True)
    sub.add_parser("status")
    args = parser.parse_args()
    try:
        if args.command == "capture":
            result = capture_handoff(args.root, args.workspace, args.handoff_id, args.lesson,
                                     args.first, args.corrected, args.reference)
        elif args.command == "review":
            result = submit_review(args.root, args.workspace, _json(args.input))
        elif args.command == "prepare-next":
            result = prepare_next(args.root, args.workspace, args.lesson, args.active)
        elif args.command == "verify-transfer":
            result = verify_transfer(args.root, args.workspace, _json(args.input), args.attempt)
        else:
            result = build_plan(args.root, args.workspace)
    except (AdaptiveError, snapmod.SnapshotError, OSError, UnicodeError, KeyError, TypeError, json.JSONDecodeError) as e:
        parser.exit(2, "Opération refusée : " + str(e) + "\n")
    print(_dump(result), end="")


if __name__ == "__main__":
    main()

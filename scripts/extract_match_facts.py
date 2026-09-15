#!/usr/bin/env python3
"""Extract a deterministic fact ledger from an OpenDota match JSON.

This script does not grade players. It gathers evidence and reports source-data
gaps so the reviewing agent can finish the mandatory analysis templates before
drafting the final review.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


MINUTES = (0, 1, 2, 3, 4, 5, 6, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60)
STRICT_FIELDS = (
    "players",
    "version",
    "teamfights",
    "objectives",
    "radiant_gold_adv",
    "radiant_xp_adv",
)
PLACEHOLDER_VALUES = {
    "",
    "PENDING",
    "NOT_COMPLETE",
    "NOT_ALLOWED",
    "TODO",
    "TBD",
}
EVIDENCE_MARKERS = (
    "数据明确显示",
    "高概率推断",
    "无法确认",
    "data fact",
    "inference",
    "unknown",
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def unwrap_match(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict) and isinstance(raw.get("players"), list):
        return raw
    if isinstance(raw, dict):
        for key in ("match", "data", "result"):
            value = raw.get(key)
            if isinstance(value, dict) and isinstance(value.get("players"), list):
                return value
    raise ValueError("JSON does not contain an OpenDota match object with players")


def recent_matches(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        for key in ("matches", "data", "results", "items"):
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def value_at(series: Any, minute: int) -> Any:
    if isinstance(series, list) and 0 <= minute < len(series):
        return series[minute]
    return None


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return len(value) > 0
    return True


def substantive(value: Any) -> bool:
    """Return whether an analysis field contains more than a placeholder."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().upper() not in PLACEHOLDER_VALUES
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def evidence_labeled(value: Any) -> bool:
    if not isinstance(value, str) or not substantive(value):
        return False
    lowered = value.lower()
    return any(marker in lowered for marker in EVIDENCE_MARKERS)


def aggregate_damage_targets(raw: Any) -> list[dict[str, Any]]:
    totals: defaultdict[str, float] = defaultdict(float)
    if isinstance(raw, dict):
        for targets in raw.values():
            if not isinstance(targets, dict):
                continue
            for target, amount in targets.items():
                if isinstance(amount, (int, float)):
                    totals[str(target)] += amount
    return [
        {"target": target, "damage": amount}
        for target, amount in sorted(totals.items(), key=lambda item: item[1], reverse=True)
    ]


def purchase_timeline(player: dict[str, Any]) -> list[dict[str, Any]]:
    log = player.get("purchase_log")
    if isinstance(log, list):
        cleaned = [item for item in log if isinstance(item, dict)]
        return sorted(cleaned, key=lambda item: item.get("time", 10**12))
    times = player.get("purchase_time")
    if isinstance(times, dict):
        result = []
        for item, time in times.items():
            if isinstance(time, (int, float)):
                result.append({"key": item, "time": time})
        return sorted(result, key=lambda item: item["time"])
    return []


def minute_points(player: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for minute in MINUTES:
        result[str(minute)] = {
            "gold": value_at(player.get("gold_t"), minute),
            "xp": value_at(player.get("xp_t"), minute),
            "last_hits": value_at(player.get("lh_t"), minute),
            "denies": value_at(player.get("dn_t"), minute),
            "hero_damage": value_at(player.get("hero_damage_t"), minute),
        }
    return result


def lane_damage(player: dict[str, Any]) -> dict[str, Any]:
    series = player.get("hero_damage_t")
    cumulative = {str(minute): value_at(series, minute) for minute in range(7)}
    baseline = cumulative["0"]
    at_six = cumulative["6"]
    net = at_six - baseline if isinstance(baseline, (int, float)) and isinstance(at_six, (int, float)) else None
    return {"cumulative_0_to_6": cumulative, "baseline_0": baseline, "minute_6": at_six, "net_after_horn": net}


def player_fact(player: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "index": index,
        "player_slot": player.get("player_slot"),
        "radiant": player.get("isRadiant", player.get("player_slot", 128) < 128 if isinstance(player.get("player_slot"), int) else None),
        "account_id": player.get("account_id"),
        "hero_id": player.get("hero_id"),
        "name": player.get("personaname") or player.get("name"),
        "lane": player.get("lane"),
        "lane_role": player.get("lane_role"),
        "lane_efficiency_pct": player.get("lane_efficiency_pct"),
        "scoreboard": {
            "kills": player.get("kills"),
            "deaths": player.get("deaths"),
            "assists": player.get("assists"),
            "last_hits": player.get("last_hits"),
            "denies": player.get("denies"),
            "gpm": player.get("gold_per_min"),
            "xpm": player.get("xp_per_min"),
            "level": player.get("level"),
            "net_worth": player.get("net_worth"),
            "hero_damage": player.get("hero_damage"),
            "tower_damage": player.get("tower_damage"),
            "hero_healing": player.get("hero_healing"),
            "stuns": player.get("stuns"),
            "teamfight_participation": player.get("teamfight_participation"),
        },
        "minute_curve": minute_points(player),
        "lane_damage_0_to_6": lane_damage(player),
        "final_items": [player.get(f"item_{slot}") for slot in range(6)],
        "purchases": purchase_timeline(player),
        "item_uses": player.get("item_uses") or {},
        "ability_uses": player.get("ability_uses") or {},
        "ability_targets": player.get("ability_targets") or {},
        "damage_by_target": aggregate_damage_targets(player.get("damage_targets")),
        "killed_by": player.get("killed_by") or {},
        "kills_log": player.get("kills_log") or [],
        "buyback_log": player.get("buyback_log") or [],
        "permanent_buffs": player.get("permanent_buffs") or [],
        "vision": {
            "obs_placed": player.get("obs_placed"),
            "sen_placed": player.get("sen_placed"),
            "observer_kills": player.get("observer_kills"),
            "sentry_kills": player.get("sentry_kills"),
        },
    }


def death_timeline(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deaths: list[dict[str, Any]] = []
    for killer_index, player in enumerate(players):
        for event in player.get("kills_log") or []:
            if isinstance(event, dict):
                deaths.append(
                    {
                        "time": event.get("time"),
                        "victim": event.get("key"),
                        "killer_index": killer_index,
                        "killer_hero_id": player.get("hero_id"),
                    }
                )
    return sorted(deaths, key=lambda event: (event.get("time") is None, event.get("time") or 0))


def advantage_swings(match: dict[str, Any]) -> list[dict[str, Any]]:
    gold = match.get("radiant_gold_adv") or []
    xp = match.get("radiant_xp_adv") or []
    count = max(len(gold), len(xp))
    swings = []
    for minute in range(1, count):
        gold_delta = gold[minute] - gold[minute - 1] if minute < len(gold) else None
        xp_delta = xp[minute] - xp[minute - 1] if minute < len(xp) else None
        magnitude = abs(gold_delta or 0) + abs(xp_delta or 0)
        swings.append({"minute": minute, "gold_delta": gold_delta, "xp_delta": xp_delta, "magnitude": magnitude})
    return sorted(swings, key=lambda row: row["magnitude"], reverse=True)[:12]


def teamfight_facts(match: dict[str, Any], players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for fight_index, fight in enumerate(match.get("teamfights") or [], start=1):
        if not isinstance(fight, dict):
            continue
        fight_players = []
        for index, data in enumerate(fight.get("players") or []):
            if not isinstance(data, dict):
                continue
            fight_players.append(
                {
                    "index": index,
                    "hero_id": players[index].get("hero_id") if index < len(players) else None,
                    "damage": data.get("damage"),
                    "deaths": data.get("deaths"),
                    "killed": data.get("killed") or {},
                    "gold_delta": data.get("gold_delta"),
                    "xp_delta": data.get("xp_delta"),
                    "ability_uses": data.get("ability_uses") or {},
                    "item_uses": data.get("item_uses") or {},
                }
            )
        result.append({"index": fight_index, "start": fight.get("start"), "end": fight.get("end"), "players": fight_players})
    return result


def side_from_team_code(team: Any) -> str | None:
    if team == 2:
        return "radiant"
    if team == 3:
        return "dire"
    return None


def player_index_from_objective(event: dict[str, Any], players: list[dict[str, Any]]) -> int | None:
    slot = event.get("slot")
    if isinstance(slot, int) and 0 <= slot < len(players):
        return slot
    player_slot = event.get("player_slot")
    for index, player in enumerate(players):
        if player.get("player_slot") == player_slot:
            return index
    return None


def roshan_aegis_lifecycles(match: dict[str, Any], players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Separate Roshan kill ownership from Aegis pickup/steal ownership."""
    objectives = [event for event in match.get("objectives") or [] if isinstance(event, dict)]
    roshan_events = [event for event in objectives if event.get("type") == "CHAT_MESSAGE_ROSHAN_KILL"]
    aegis_types = {"CHAT_MESSAGE_AEGIS", "CHAT_MESSAGE_AEGIS_STOLEN"}
    result = []
    for index, roshan in enumerate(roshan_events):
        start = roshan.get("time")
        next_start = roshan_events[index + 1].get("time") if index + 1 < len(roshan_events) else None
        candidates = []
        for event in objectives:
            event_time = event.get("time")
            if event.get("type") not in aegis_types or not isinstance(event_time, (int, float)):
                continue
            if not isinstance(start, (int, float)) or event_time < start:
                continue
            if isinstance(next_start, (int, float)) and event_time >= next_start:
                continue
            candidates.append(event)
        aegis = min(candidates, key=lambda event: event.get("time", 10**12)) if candidates else None
        holder_index = player_index_from_objective(aegis, players) if aegis else None
        holder_side = None
        holder_hero_id = None
        holder_player_slot = None
        if holder_index is not None:
            holder = players[holder_index]
            player_slot = holder.get("player_slot")
            if isinstance(player_slot, int):
                holder_side = "radiant" if player_slot < 128 else "dire"
            holder_hero_id = holder.get("hero_id")
            holder_player_slot = holder.get("player_slot")
        kill_side = side_from_team_code(roshan.get("team"))
        if not aegis:
            relation = "unresolved"
        elif aegis.get("type") == "CHAT_MESSAGE_AEGIS_STOLEN":
            relation = "stolen"
        elif kill_side and holder_side:
            relation = "same_side" if kill_side == holder_side else "opposing_side"
        else:
            relation = "unresolved"
        result.append(
            {
                "sequence": index + 1,
                "roshan_kill_time": start,
                "roshan_kill_team_code": roshan.get("team"),
                "roshan_kill_side": kill_side,
                "aegis_event_time": aegis.get("time") if aegis else None,
                "aegis_event_type": aegis.get("type") if aegis else None,
                "aegis_holder_index": holder_index,
                "aegis_holder_player_slot": holder_player_slot,
                "aegis_holder_hero_id": holder_hero_id,
                "aegis_holder_side": holder_side,
                "ownership_relation": relation,
            }
        )
    return result


def purchased_item(player: dict[str, Any], item_key: str) -> bool:
    return any(event.get("key") == item_key for event in purchase_timeline(player))


def equipment_analysis_template(
    match: dict[str, Any], user_account_id: Any, aegis_facts: list[dict[str, Any]]
) -> dict[str, Any]:
    players = match.get("players") or []
    user_index = next(
        (index for index, player in enumerate(players) if str(player.get("account_id")) == str(user_account_id)),
        None,
    )
    bkb_indices = [index for index, player in enumerate(players) if purchased_item(player, "black_king_bar")]
    player_audits = []
    for index, player in enumerate(players):
        player_audits.append(
            {
                "player_index": index,
                "hero_id": player.get("hero_id"),
                "role": "PENDING",
                "key_items": [],
                "build_conclusion": "PENDING",
                "best_item_decision": "PENDING",
                "biggest_item_issue": "PENDING",
                "resource_fit": "PENDING",
                "evidence_level": "PENDING",
            }
        )
    bkb_audits = [
        {
            "player_index": index,
            "purchase_time": "PENDING",
            "high_value_window": "PENDING",
            "low_value_or_uncovered_window": "PENDING",
            "conclusion": "PENDING",
            "evidence_level": "PENDING",
        }
        for index in bkb_indices
    ]
    aegis_audits = []
    for fact in aegis_facts:
        aegis_audits.append(
            {
                **fact,
                "first_relevant_fight": "PENDING",
                "first_life_result": "PENDING",
                "death_type_boundary": "PENDING",
                "second_life_result": "PENDING",
                "map_conversion": "PENDING",
                "evidence_level": "PENDING",
            }
        )
    return {
        "required_player_indices": list(range(len(players))),
        "required_bkb_player_indices": bkb_indices,
        "user_index": user_index,
        "player_item_audits": player_audits,
        "bkb_player_audits": bkb_audits,
        "aegis_lifecycle_audits": aegis_audits,
        "user_build_path": {
            "first_fight_ready_item": "PENDING",
            "enemy_problem_answered": "PENDING",
            "highest_risk_item": "PENDING",
            "item_gap_consequence": "PENDING",
            "alternative_order": "PENDING",
            "next_game_rule": "PENDING",
            "evidence_level": "PENDING",
        },
        "high_risk_items_buyback_conflict": "PENDING",
        "high_risk_items_buyback_evidence_level": "PENDING",
        "rule": "Timestamps alone do not complete an item audit; every key item needs capability, fight, use, outcome, conversion, and evidence fields.",
    }


def find_recent_status(recent_raw: Any, match_id: Any) -> dict[str, Any]:
    for item in recent_matches(recent_raw):
        if str(item.get("match_id")) == str(match_id):
            return {key: item.get(key) for key in ("parsed", "has_parsed", "parse_status") if key in item}
    return {}


def parse_audit(match: dict[str, Any], recent_status: dict[str, Any]) -> dict[str, Any]:
    presence = {field: nonempty(match.get(field)) for field in STRICT_FIELDS}
    if isinstance(match.get("players"), list):
        presence["players"] = len(match["players"]) == 10
    complete = all(presence.values())
    any_timeline = any(presence.get(field) for field in ("teamfights", "objectives", "radiant_gold_adv", "radiant_xp_adv"))
    tier = "complete" if complete else "partial" if presence["players"] and any_timeline else "summary"
    single_status = {key: match.get(key) for key in ("parsed", "has_parsed", "parse_status") if key in match}
    warnings = []
    statuses = {"single_match": single_status, "recent_list": recent_status}
    flat = {f"single.{key}": value for key, value in single_status.items()}
    flat.update({f"recent.{key}": value for key, value in recent_status.items()})
    claims_parsed = any(value is True or str(value).lower() in {"parsed", "complete", "completed"} for value in flat.values())
    claims_unparsed = any(value is False or str(value).lower() in {"waiting", "requested", "unavailable"} for value in flat.values())
    if claims_parsed and not complete:
        warnings.append("Status claims parsed, but one or more strict fields are missing or empty.")
    if claims_unparsed and complete:
        warnings.append("Status claims unparsed/incomplete, but all strict fields are present.")
    if recent_status and single_status and recent_status != single_status:
        warnings.append("Recent-list status and single-match cache status are inconsistent.")
    return {
        "actual_tier": tier,
        "strict_complete": complete,
        "field_presence": presence,
        "missing_for_full_review": [field for field, present in presence.items() if not present],
        "reported_status": statuses,
        "warnings": warnings,
    }


def coverage_template(match: dict[str, Any], user_account_id: Any) -> dict[str, Any]:
    user = next((p for p in match.get("players") or [] if str(p.get("account_id")) == str(user_account_id)), None)
    user_deaths = user.get("deaths") if isinstance(user, dict) else None
    return {
        "draft_status": "NOT_ALLOWED",
        "lanes": {"required": 3, "completed": 0},
        "support_lane_pressure": {"required": 4, "completed": 0},
        "cores": {"required": 6, "completed": 0},
        "supports": {"required": 4, "completed": 0},
        "key_skills": {
            "required_each_side": [2, 4],
            "radiant_selected": 0,
            "radiant_completed": 0,
            "dire_selected": 0,
            "dire_completed": 0,
        },
        "decisive_fights": {"required_range": [3, 5], "selected": 0, "completed": 0},
        "user_deaths": {"required": user_deaths, "completed": 0},
        "resource_categories": {
            "required": ["damage_targets", "buildings", "roshan", "buybacks"],
            "completed": [],
        },
        "equipment_validation": "PENDING",
        "evidence_labels": "PENDING",
        "rule": "Do not draft a complete review until every mandatory template is filled or explicitly marked unavailable with a reason.",
    }


def require_fields(record: dict[str, Any], fields: tuple[str, ...], prefix: str, missing: list[str]) -> None:
    for field in fields:
        if not substantive(record.get(field)):
            missing.append(f"{prefix}.{field} is incomplete")


def validate_equipment_analysis(ledger: dict[str, Any]) -> list[str]:
    equipment = ledger.get("equipment_analysis_template")
    if not isinstance(equipment, dict):
        return ["equipment_analysis_template is missing"]
    missing: list[str] = []

    required_players = set(equipment.get("required_player_indices") or [])
    audits = equipment.get("player_item_audits") or []
    audit_map: dict[Any, dict[str, Any]] = {}
    for audit in audits:
        if not isinstance(audit, dict):
            missing.append("player_item_audits contains a non-object entry")
            continue
        index = audit.get("player_index")
        if index in audit_map:
            missing.append(f"player_item_audits contains duplicate player_index={index}")
        audit_map[index] = audit
    for index in sorted(required_players):
        audit = audit_map.get(index)
        if not audit:
            missing.append(f"player_item_audits missing player_index={index}")
            continue
        require_fields(
            audit,
            ("role", "build_conclusion", "best_item_decision", "biggest_item_issue", "resource_fit", "evidence_level"),
            f"player_item_audits[{index}]",
            missing,
        )
        if audit.get("role") not in {"core", "support", "核心", "辅助"}:
            missing.append(f"player_item_audits[{index}].role must identify core or support")
        if not evidence_labeled(audit.get("evidence_level")):
            missing.append(f"player_item_audits[{index}].evidence_level lacks a fact/inference/unknown label")
        key_items = audit.get("key_items")
        if not isinstance(key_items, list) or not key_items:
            missing.append(f"player_item_audits[{index}].key_items is empty")
            continue
        for item_index, item in enumerate(key_items):
            if not isinstance(item, dict):
                missing.append(f"player_item_audits[{index}].key_items[{item_index}] is not an object")
                continue
            require_fields(
                item,
                (
                    "item",
                    "purchase_time",
                    "capability_or_tradeoff",
                    "targeting",
                    "first_relevant_fight",
                    "use_evidence",
                    "fight_outcome",
                    "map_conversion",
                    "window_judgment",
                    "evidence_level",
                ),
                f"player_item_audits[{index}].key_items[{item_index}]",
                missing,
            )
            if not evidence_labeled(item.get("evidence_level")):
                missing.append(
                    f"player_item_audits[{index}].key_items[{item_index}].evidence_level lacks a fact/inference/unknown label"
                )

    required_bkb = set(equipment.get("required_bkb_player_indices") or [])
    bkb_audits = equipment.get("bkb_player_audits") or []
    bkb_map = {audit.get("player_index"): audit for audit in bkb_audits if isinstance(audit, dict)}
    for index in sorted(required_bkb):
        audit = bkb_map.get(index)
        if not audit:
            missing.append(f"bkb_player_audits missing player_index={index}")
            continue
        require_fields(
            audit,
            ("purchase_time", "high_value_window", "low_value_or_uncovered_window", "conclusion", "evidence_level"),
            f"bkb_player_audits[{index}]",
            missing,
        )
        if not evidence_labeled(audit.get("evidence_level")):
            missing.append(f"bkb_player_audits[{index}].evidence_level lacks a fact/inference/unknown label")

    expected_aegis = ledger.get("roshan_aegis_lifecycles") or []
    aegis_audits = equipment.get("aegis_lifecycle_audits") or []
    aegis_map = {
        audit.get("roshan_kill_time"): audit for audit in aegis_audits if isinstance(audit, dict)
    }
    for fact in expected_aegis:
        time = fact.get("roshan_kill_time")
        audit = aegis_map.get(time)
        if not audit:
            missing.append(f"aegis_lifecycle_audits missing roshan_kill_time={time}")
            continue
        for factual_field in (
            "roshan_kill_side",
            "aegis_event_type",
            "aegis_holder_side",
            "ownership_relation",
        ):
            if audit.get(factual_field) != fact.get(factual_field):
                missing.append(
                    f"aegis_lifecycle_audits[{time}].{factual_field} does not match extracted facts"
                )
        require_fields(
            audit,
            (
                "first_relevant_fight",
                "first_life_result",
                "death_type_boundary",
                "second_life_result",
                "map_conversion",
                "evidence_level",
            ),
            f"aegis_lifecycle_audits[{time}]",
            missing,
        )
        if not evidence_labeled(audit.get("evidence_level")):
            missing.append(f"aegis_lifecycle_audits[{time}].evidence_level lacks a fact/inference/unknown label")

    if equipment.get("user_index") is not None:
        user_path = equipment.get("user_build_path") or {}
        require_fields(
            user_path,
            (
                "first_fight_ready_item",
                "enemy_problem_answered",
                "highest_risk_item",
                "item_gap_consequence",
                "alternative_order",
                "next_game_rule",
                "evidence_level",
            ),
            "user_build_path",
            missing,
        )
        if not evidence_labeled(user_path.get("evidence_level")):
            missing.append("user_build_path.evidence_level lacks a fact/inference/unknown label")
    require_fields(
        equipment,
        ("high_risk_items_buyback_conflict", "high_risk_items_buyback_evidence_level"),
        "equipment_analysis_template",
        missing,
    )
    if not evidence_labeled(equipment.get("high_risk_items_buyback_evidence_level")):
        missing.append("high_risk_items_buyback_evidence_level lacks a fact/inference/unknown label")
    return missing


def validate_coverage(ledger: dict[str, Any]) -> list[str]:
    coverage = ledger.get("analysis_coverage_template")
    if not isinstance(coverage, dict):
        return ["analysis_coverage_template is missing"]
    missing = []
    for key in ("lanes", "support_lane_pressure", "cores", "supports", "user_deaths"):
        item = coverage.get(key) or {}
        required = item.get("required")
        completed = item.get("completed")
        if required is None or completed != required:
            missing.append(f"{key}: completed={completed}, required={required}")

    skills = coverage.get("key_skills") or {}
    low, high = (skills.get("required_each_side") or [2, 4])[:2]
    for side in ("radiant", "dire"):
        selected = skills.get(f"{side}_selected")
        completed = skills.get(f"{side}_completed")
        if not isinstance(selected, int) or not low <= selected <= high or completed != selected:
            missing.append(f"key_skills.{side}: selected={selected}, completed={completed}, required={low}-{high}")

    fights = coverage.get("decisive_fights") or {}
    fight_low, fight_high = (fights.get("required_range") or [3, 5])[:2]
    selected = fights.get("selected")
    completed = fights.get("completed")
    if not isinstance(selected, int) or not fight_low <= selected <= fight_high or completed != selected:
        missing.append(f"decisive_fights: selected={selected}, completed={completed}, required={fight_low}-{fight_high}")

    resources = coverage.get("resource_categories") or {}
    required_resources = set(resources.get("required") or [])
    completed_resources = set(resources.get("completed") or [])
    absent_resources = sorted(required_resources - completed_resources)
    if absent_resources:
        missing.append("resource_categories: " + ", ".join(absent_resources))
    if coverage.get("evidence_labels") != "COMPLETE":
        missing.append("evidence_labels is not COMPLETE")
    equipment_missing = validate_equipment_analysis(ledger)
    if equipment_missing:
        missing.extend(equipment_missing)
    if coverage.get("equipment_validation") != "COMPLETE":
        missing.append("equipment_validation is not COMPLETE")
    if coverage.get("draft_status") != "REVIEW_COMPLETE":
        missing.append("draft_status is not REVIEW_COMPLETE")
    return missing


def build_ledger(match: dict[str, Any], recent_raw: Any, user_account_id: Any) -> dict[str, Any]:
    players = match.get("players") or []
    recent_status = find_recent_status(recent_raw, match.get("match_id")) if recent_raw is not None else {}
    aegis_facts = roshan_aegis_lifecycles(match, players)
    return {
        "match": {
            "match_id": match.get("match_id"),
            "start_time": match.get("start_time"),
            "duration": match.get("duration"),
            "radiant_win": match.get("radiant_win"),
            "patch": match.get("patch"),
            "version": match.get("version"),
            "radiant_score": match.get("radiant_score"),
            "dire_score": match.get("dire_score"),
        },
        "parse_audit": parse_audit(match, recent_status),
        "players": [player_fact(player, index) for index, player in enumerate(players)],
        "death_timeline": death_timeline(players),
        "advantage_swings": advantage_swings(match),
        "objectives": match.get("objectives") or [],
        "roshan_aegis_lifecycles": aegis_facts,
        "teamfights": teamfight_facts(match, players),
        "equipment_analysis_template": equipment_analysis_template(match, user_account_id, aegis_facts),
        "analysis_coverage_template": coverage_template(match, user_account_id),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("match_json", type=Path, nargs="?")
    parser.add_argument("--recent-json", type=Path, help="Optional recent-match list for status conflict checks")
    parser.add_argument("--user-account-id", help="Used to set the required user-death count")
    parser.add_argument("--output", type=Path, help="Write the ledger to a file instead of stdout")
    parser.add_argument("--check-ledger", type=Path, help="Validate a populated ledger's mandatory coverage and exit")
    args = parser.parse_args()

    try:
        if args.check_ledger:
            ledger = load_json(args.check_ledger)
            missing = validate_coverage(ledger)
            print(json.dumps({"passed": not missing, "missing": missing}, ensure_ascii=False, indent=2))
            return 0 if not missing else 3
        if args.match_json is None:
            parser.error("match_json is required unless --check-ledger is used")
        match = unwrap_match(load_json(args.match_json))
        recent_raw = load_json(args.recent_json) if args.recent_json else None
        ledger = build_ledger(match, recent_raw, args.user_account_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"fact-ledger error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(ledger, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

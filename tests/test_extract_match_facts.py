import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "extract_match_facts.py"
SPEC = importlib.util.spec_from_file_location("extract_match_facts", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def synthetic_match():
    players = []
    for index in range(10):
        player_slot = index if index < 5 else index + 123
        players.append(
            {
                "account_id": 1000 + index,
                "player_slot": player_slot,
                "hero_id": index + 1,
                "deaths": 0,
                "purchase_log": [{"time": 100, "key": "black_king_bar"}] if index == 0 else [],
            }
        )
    return {
        "match_id": 1,
        "version": 22,
        "players": players,
        "teamfights": [{"start": 100, "end": 120, "players": [{} for _ in players]}],
        "objectives": [
            {"time": 200, "type": "CHAT_MESSAGE_ROSHAN_KILL", "team": 2},
            {
                "time": 202,
                "type": "CHAT_MESSAGE_AEGIS_STOLEN",
                "slot": 6,
                "player_slot": 129,
            },
        ],
        "radiant_gold_adv": [0, 1],
        "radiant_xp_adv": [0, 1],
    }


def complete_legacy_coverage(ledger):
    coverage = ledger["analysis_coverage_template"]
    coverage["lanes"]["completed"] = 3
    coverage["support_lane_pressure"]["completed"] = 4
    coverage["cores"]["completed"] = 6
    coverage["supports"]["completed"] = 4
    coverage["key_skills"].update(
        {
            "radiant_selected": 2,
            "radiant_completed": 2,
            "dire_selected": 2,
            "dire_completed": 2,
        }
    )
    coverage["decisive_fights"].update({"selected": 3, "completed": 3})
    coverage["user_deaths"]["completed"] = 0
    coverage["resource_categories"]["completed"] = list(coverage["resource_categories"]["required"])
    coverage["evidence_labels"] = "COMPLETE"
    coverage["equipment_validation"] = "COMPLETE"
    coverage["draft_status"] = "REVIEW_COMPLETE"


def complete_equipment_analysis(ledger):
    equipment = ledger["equipment_analysis_template"]
    for audit in equipment["player_item_audits"]:
        index = audit["player_index"]
        audit.update(
            {
                "role": "core" if index in {0, 1, 2, 5, 6, 7} else "support",
                "key_items": [
                    {
                        "item": "example_item",
                        "purchase_time": 100,
                        "capability_or_tradeoff": "获得关键能力",
                        "targeting": "针对敌方问题",
                        "first_relevant_fight": "第1波团战",
                        "use_evidence": "窗口内有使用记录",
                        "fight_outcome": "产生击杀结果",
                        "map_conversion": "无直接转化：随后撤退",
                        "window_judgment": "装备窗口已兑现",
                        "evidence_level": "数据明确显示",
                    }
                ],
                "build_conclusion": "路线服务本局职责",
                "best_item_decision": "及时补足关键能力",
                "biggest_item_issue": "不适用：没有明确问题",
                "resource_fit": "资源与职责匹配",
                "evidence_level": "数据明确显示",
            }
        )
    for audit in equipment["bkb_player_audits"]:
        audit.update(
            {
                "purchase_time": 100,
                "high_value_window": "第1波有使用并获得击杀",
                "low_value_or_uncovered_window": "无法确认：没有第二个团战窗口",
                "conclusion": "BKB窗口产生作用",
                "evidence_level": "数据明确显示；冷却无法确认",
            }
        )
    for audit in equipment["aegis_lifecycle_audits"]:
        audit.update(
            {
                "first_relevant_fight": "第1波相关战斗",
                "first_life_result": "无法确认：缺少录像",
                "death_type_boundary": "无法确认盾命或实死",
                "second_life_result": "无法确认：缺少录像",
                "map_conversion": "无直接转化：测试数据",
                "evidence_level": "数据明确显示归属；后续无法确认",
            }
        )
    equipment["user_build_path"].update(
        {
            "first_fight_ready_item": "关键参战装",
            "enemy_problem_answered": "解决敌方控制",
            "highest_risk_item": "不适用：没有高风险装备",
            "item_gap_consequence": "真空期没有接团",
            "alternative_order": "不适用：原顺序合理",
            "next_game_rule": "看到控制阵容先补魔免",
            "evidence_level": "高概率推断",
        }
    )
    equipment["high_risk_items_buyback_conflict"] = "不适用：没有高风险装备"
    equipment["high_risk_items_buyback_evidence_level"] = "数据明确显示"


class ExtractMatchFactsTests(unittest.TestCase):
    def test_roshan_kill_and_stolen_aegis_are_distinct(self):
        match = synthetic_match()
        facts = MODULE.roshan_aegis_lifecycles(match, match["players"])
        self.assertEqual(facts[0]["roshan_kill_side"], "radiant")
        self.assertEqual(facts[0]["aegis_holder_side"], "dire")
        self.assertEqual(facts[0]["ownership_relation"], "stolen")

    def test_legacy_counts_cannot_bypass_equipment_gate(self):
        ledger = MODULE.build_ledger(synthetic_match(), None, 1006)
        complete_legacy_coverage(ledger)
        missing = MODULE.validate_coverage(ledger)
        self.assertTrue(any("key_items is empty" in item for item in missing))

    def test_structured_equipment_analysis_can_pass(self):
        ledger = MODULE.build_ledger(synthetic_match(), None, 1006)
        complete_legacy_coverage(ledger)
        complete_equipment_analysis(ledger)
        self.assertEqual(MODULE.validate_coverage(ledger), [])


if __name__ == "__main__":
    unittest.main()

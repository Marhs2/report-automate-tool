import unittest

from weekly_deck import (
    merge_last_week_next,
    next_sections_of,
    pick_previous_weekly,
    same_work,
)


class SameWorkTests(unittest.TestCase):
    def test_exact_and_contained_sentences_match(self):
        self.assertTrue(same_work("WPAS DB 백업", "WPAS DB 백업"))
        self.assertTrue(
            same_work(
                "제품 소개 페이지 콘텐츠 포맷 정의",
                "제품 소개 페이지 콘텐츠 포맷 정의 (6/1~6/12)",
            )
        )

    def test_unrelated_work_does_not_match(self):
        self.assertFalse(same_work("홈페이지 시안 검토", "TYM 태그 펌웨어 업그레이드"))


class PickPreviousTests(unittest.TestCase):
    def test_picks_the_closest_earlier_week(self):
        last = {"next": [{"title": "MES", "items": ["배치 변경"]}]}
        older = {"next": [{"title": "MES", "items": ["오래된 항목"]}]}
        picked = pick_previous_weekly(
            [
                (["2026-05-25", "2026-05-29"], last),
                (["2026-05-18", "2026-05-22"], older),
            ],
            ["2026-06-01", "2026-06-05"],
        )
        self.assertEqual(picked["next"][0]["items"], ["배치 변경"])

    def test_ignores_the_current_week(self):
        picked = pick_previous_weekly(
            [(["2026-06-01", "2026-06-05"], {"next": []})],
            ["2026-06-01", "2026-06-05"],
        )
        self.assertIsNone(picked)


class MergeLastWeekTests(unittest.TestCase):
    def test_carries_unmentioned_last_next_into_this_week(self):
        report, carried = merge_last_week_next(
            {
                "projects": [
                    {
                        "projectName": "TYM",
                        "completedTasks": ["계절기종 실적 테스트"],
                        "inProgressTasks": [],
                        "issues": [],
                        "nextWeekPlans": ["태그 펌웨어 업그레이드"],
                    }
                ]
            },
            [
                {
                    "title": "TYM",
                    "items": [
                        "SRM DB Link 에서 배치로 변경 검토",
                        "태그 펌웨어 업그레이드",
                    ],
                }
            ],
        )
        plans = report["projects"][0]["nextWeekPlans"]
        self.assertEqual(carried, 1)
        self.assertIn("SRM DB Link 에서 배치로 변경 검토", plans)
        self.assertEqual(plans.count("태그 펌웨어 업그레이드"), 1)

    def test_does_not_carry_work_already_completed(self):
        report, carried = merge_last_week_next(
            {
                "projects": [
                    {
                        "projectName": "대한전선 IoT",
                        "completedTasks": [
                            "문자 발송 기준정보 관리 프로그램 발송 이력 확인 추가 개발 및 배포 완료"
                        ],
                        "inProgressTasks": [],
                        "issues": [],
                        "nextWeekPlans": [],
                    }
                ]
            },
            [
                {
                    "title": "대한전선 IoT",
                    "items": ["문자 발송 기준정보 관리 프로그램- 추가 요청 사항 검토 및 개발 : 부서 관리 및 문자 발송 이력 확인"],
                }
            ],
        )
        self.assertEqual(carried, 0)
        self.assertEqual(report["projects"][0]["nextWeekPlans"], [])

    def test_adds_a_project_that_only_existed_last_week(self):
        report, carried = merge_last_week_next(
            {"projects": []},
            [{"title": "RealTrek", "items": ["WPAS 기존 DB 백업"]}],
        )
        self.assertEqual(carried, 1)
        self.assertEqual(report["projects"][0]["projectName"], "RealTrek")
        self.assertEqual(
            report["projects"][0]["nextWeekPlans"],
            ["WPAS 기존 DB 백업"],
        )

    def test_next_sections_read_deck_or_legacy(self):
        deck = next_sections_of(
            {
                "schema": "weekly-deck-v1",
                "next": [{"title": "홈페이지", "items": ["시안 확정"]}],
            }
        )
        legacy = next_sections_of(
            {
                "projects": [
                    {
                        "projectName": "홈페이지",
                        "nextWeekPlans": ["시안 확정"],
                    }
                ]
            }
        )
        self.assertEqual(deck[0]["items"], ["시안 확정"])
        self.assertEqual(legacy[0]["items"], ["시안 확정"])


if __name__ == "__main__":
    unittest.main()

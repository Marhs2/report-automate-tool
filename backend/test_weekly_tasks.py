import unittest

from main import (
    _weekly_tasks_match,
    build_weekly_confirm_questions,
    drop_empty_projects,
    promote_weekly_tasks,
)


class WeeklyTasksMatchTests(unittest.TestCase):
    def test_and_and_submit_do_not_merge_payroll_with_military_docs(self):
        self.assertFalse(
            _weekly_tasks_match(
                "5월 급여대장 작성 및 세무사 제출",
                "병역업체지정 가점사항 제출 및 등록 : 고용보험 명부 외 15 작성 및 제출",
            )
        )

    def test_same_bank_different_visits_do_not_match(self):
        self.assertFalse(
            _weekly_tasks_match(
                "우리은행 매경미디어 지점 방문, 통장 개설 및 보증서 관련 서류 제출",
                "우리은행 주거래 지점 담당자 당사 방문 : 대출연장, 기술신용보증기금 개시 등 업무 협의",
            )
        )

    def test_preview_modal_still_matches_shorter_progress(self):
        self.assertTrue(
            _weekly_tasks_match(
                "원문 미리보기 모달 개발 완료",
                "카드 클릭 시 원문 미리보기 구현",
            )
        )


class PromoteWeeklyTests(unittest.TestCase):
    def test_keeps_payroll_and_woori_next_plans(self):
        report = promote_weekly_tasks(
            {
                "projects": [
                    {
                        "projectName": "경영지원",
                        "completedTasks": [
                            "병역업체지정 가점사항 제출 및 등록 : 우수기업활용인증서 외 15 작성 및 제출"
                        ],
                        "inProgressTasks": [
                            "우리은행 주거래 지점 담당자 당사 방문 : 대출연장 협의",
                            "이노비즈 인증 실사 대응 준비 서류 작성 및 취합 : 직무발명보상지침 등 17종",
                            "서울디지텍고 면접 합격자 공유 및 진행 절차 확인",
                        ],
                        "issues": [],
                        "nextWeekPlans": [
                            "5월 급여대장 작성 및 세무사 제출",
                            "우리은행 매경미디어 지점 방문, 통장 개설 및 보증서 관련 서류 제출",
                            "이노비즈 인증 실사 대응 서류 준비",
                            "서울디지텍고 합격자 3자협약 진행 일정 협의",
                            "대중소협업플랫폼 24년, 25년 미흡 대응",
                        ],
                    }
                ]
            }
        )
        plans = report["projects"][0]["nextWeekPlans"]
        self.assertIn("5월 급여대장 작성 및 세무사 제출", plans)
        self.assertIn(
            "우리은행 매경미디어 지점 방문, 통장 개설 및 보증서 관련 서류 제출",
            plans,
        )
        self.assertIn("서울디지텍고 합격자 3자협약 진행 일정 협의", plans)
        self.assertNotIn("이노비즈 인증 실사 대응 서류 준비", plans)

    def test_drops_exact_duplicate_next_in_progress(self):
        report = promote_weekly_tasks(
            {
                "projects": [
                    {
                        "projectName": "국책과제",
                        "completedTasks": [],
                        "inProgressTasks": ["대중소협업플랫폼 24년, 25년 미흡 대응"],
                        "issues": [],
                        "nextWeekPlans": ["대중소협업플랫폼 24년, 25년 미흡 대응"],
                    }
                ]
            }
        )
        self.assertEqual(report["projects"][0]["nextWeekPlans"], [])


class AliasAndConfirmTests(unittest.TestCase):
    def test_travel_rule_merges_into_admin(self):
        report = drop_empty_projects(
            {
                "projects": [
                    {
                        "projectName": "경영지원",
                        "completedTasks": ["서울디지텍고 면접 합격자 공유"],
                        "inProgressTasks": [],
                        "issues": [],
                        "nextPlans": [],
                    },
                    {
                        "projectName": "여비규정 개정",
                        "completedTasks": [],
                        "inProgressTasks": ["국내여비 규정 중 숙박비 초과 문구 변경"],
                        "issues": [],
                        "nextPlans": ["개정 예정일자 : 2026.06.01"],
                    },
                ]
            }
        )
        names = [p["projectName"] for p in report["projects"]]
        self.assertEqual(names, ["경영지원"])
        admin = report["projects"][0]
        self.assertIn("국내여비 규정 중 숙박비 초과 문구 변경", admin["inProgressTasks"])
        self.assertIn("개정 예정일자 : 2026.06.01", admin["nextPlans"])

    def test_confirm_does_not_ask_about_unselected_weekdays(self):
        questions = build_weekly_confirm_questions(
            {
                "projects": [
                    {
                        "projectName": "국책과제",
                        "completedTasks": ["정산 완료"],
                        "inProgressTasks": [],
                        "issues": [],
                        "nextWeekPlans": ["감사 대응"],
                    }
                ]
            },
            [],
            ["2026-05-11", "2026-05-14", "2026-05-15"],
        )
        texts = [q["text"] for q in questions]
        self.assertFalse(any("빠져 있습니다" in text for text in texts))


if __name__ == "__main__":
    unittest.main()

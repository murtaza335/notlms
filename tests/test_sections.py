import unittest

from notlms.sections import detect_section, detect_sections, is_for_section, parse_section


class DetectSectionTest(unittest.TestCase):
    def test_real_world_names(self):
        cases = {
            "Lab-05-[Submission Link]-BSCS-14C": "C",
            "Lab 6 Submission_sec_C": "C",
            "Lab 6 Submission_sec_B": "B",
            "Lab - 06 - [Submission Link] - BSCS-14B": "B",
            "Lab 5 Submission Section B": "B",
            "Assignment 1 BSCS 14-D": "D",
            "Lab-07-[Submission Link] - BSCS14A": "A",
            "Lab 6 Submission Section A": "A",
            "Lab 7 Submissionn": None,
            "Quiz 2": None,
            "Second Assignment": None,
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(detect_section(name), expected)

    def test_filtering(self):
        self.assertTrue(is_for_section("Lab 6 Submission Section A", "A"))
        self.assertTrue(is_for_section("Lab 7 Submissionn", "A"))
        self.assertFalse(is_for_section("Lab 6 Submission_sec_B", "A"))
        self.assertTrue(is_for_section("Lab 6 Submission_sec_B", ""))


class MoreRulesTest(unittest.TestCase):
    def test_extra_tag_formats(self):
        cases = {
            "Quiz 3 (Sec B)": {"B"},
            "Lab 4 (C)": {"C"},
            "Lab 4 [D]": {"D"},
            "Assignment Section A and B": {"A", "B"},
            "Assignment Sec A, B": {"A", "B"},
            "Lab 2 Sections A/C": {"A", "C"},
            "Lab 9 BEE-13 D": {"D"},
            "Lab 9 BESE12B": {"B"},
            "Lab 07 A": set(),
            "Assignment 2 is due": set(),
            "Quiz 1 - Second Attempt": set(),
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(detect_sections(name), expected)

    def test_multi_section_tag_matches_either(self):
        self.assertTrue(is_for_section("Assignment Section A and B", "B"))
        self.assertFalse(is_for_section("Assignment Section A and B", "C"))
        self.assertFalse(is_for_section("Quiz 3 (Sec B)", "A"))

    def test_parse_section(self):
        self.assertEqual(parse_section("b"), "B")
        self.assertEqual(parse_section(" Section C "), "C")
        self.assertEqual(parse_section("BSCS-14D"), "D")
        for bad in ("", "AB", "14", "Section A and B"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_section(bad)


if __name__ == "__main__":
    unittest.main()

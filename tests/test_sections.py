import unittest

from notlms.sections import detect_section, is_for_section


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


if __name__ == "__main__":
    unittest.main()

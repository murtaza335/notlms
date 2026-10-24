import unittest

from notlms.moodle import _flatten


class FlattenTest(unittest.TestCase):
    def test_lists_and_nested(self):
        self.assertEqual(
            _flatten({"courseids": [5, 7], "options": {"a": True}, "skip": None, "n": 3}),
            {"courseids[0]": 5, "courseids[1]": 7, "options[a]": 1, "n": 3},
        )


if __name__ == "__main__":
    unittest.main()

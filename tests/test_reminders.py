import tempfile
import unittest
from pathlib import Path

from lms_notifier.reminders import NEW, OVERDUE, ReminderState, current_stage, due_reminders
from lms_notifier.tasks import Task

HOURS = [72, 24, 6, 1]
NOW = 1_800_000_000


def make_task(hours_left: float, cmid: int = 1) -> Task:
    return Task(
        cmid=cmid,
        name="Lab 1",
        course="CS-101",
        module="assign",
        due=int(NOW + hours_left * 3600),
        cutoff=0,
        url="https://lms.example/mod/assign/view.php?id=1",
    )


class CurrentStageTest(unittest.TestCase):
    def test_stages(self):
        self.assertEqual(current_stage(make_task(100), NOW, HOURS), NEW)
        self.assertEqual(current_stage(make_task(72), NOW, HOURS), "72")
        self.assertEqual(current_stage(make_task(30), NOW, HOURS), "72")
        self.assertEqual(current_stage(make_task(23.9), NOW, HOURS), "24")
        self.assertEqual(current_stage(make_task(0.5), NOW, HOURS), "1")
        self.assertEqual(current_stage(make_task(-1), NOW, HOURS), OVERDUE)


class DueRemindersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_each_stage_fires_once(self):
        task = make_task(20)
        state = ReminderState(self.path)
        [reminder] = due_reminders([task], state, NOW, HOURS)
        self.assertEqual(reminder.stage, "24")
        state.mark_sent(task, reminder.stage)
        state.save(NOW)

        reloaded = ReminderState(self.path)
        self.assertEqual(due_reminders([task], reloaded, NOW + 60, HOURS), [])
        # Crossing the 6h threshold triggers a new reminder.
        [later] = due_reminders([task], reloaded, NOW + 15 * 3600, HOURS)
        self.assertEqual(later.stage, "6")

    def test_old_entries_are_pruned(self):
        task = make_task(-24 * 40)
        state = ReminderState(self.path)
        state.mark_sent(task, OVERDUE)
        state.save(NOW)
        self.assertFalse(ReminderState(self.path).was_sent(task, OVERDUE))


if __name__ == "__main__":
    unittest.main()

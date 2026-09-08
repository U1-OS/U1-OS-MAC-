import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from utils import u1_autopilot as autopilot


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026,9,8,0,0,tzinfo=timezone.utc)
        self.store = {'u1_autopilot_config':{'enabled':True,'briefing':False,'reminders':True,'health':False}}
        self.rows = []
        self.patches = [patch.object(autopilot,'read_value',side_effect=lambda key,default:copy.deepcopy(self.store.get(key,default))),
                        patch.object(autopilot,'save_value',side_effect=lambda key,value:self.store.update({key:copy.deepcopy(value)})),
                        patch.object(autopilot.workspace,'preferences',return_value={'timezone':'UTC'}),
                        patch.object(autopilot.workspace,'records',side_effect=lambda:self.rows)]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()

    def event(self,hours):
        self.rows = [{'id':'event-one','kind':'event','title':'Important meeting','payload':{'start':(self.now+timedelta(hours=hours)).isoformat()}}]

    def test_lead_times(self):
        for hours,label in [(70,'3 days'),(23,'1 day'),(7,'8 hours'),(.1,'15 minutes')]:
            with self.subTest(hours=hours):
                self.store.pop('u1_autopilot_activity',None)
                self.store.pop('u1_event_reminder_marks',None)
                self.event(hours)
                result=autopilot.tick(self.now)
                self.assertEqual(len(result['activity']),1)
                self.assertIn(label,result['activity'][0]['title'])

    def test_deduplicated_between_polls(self):
        self.event(7)
        autopilot.tick(self.now)
        self.assertEqual(len(autopilot.tick(self.now+timedelta(minutes=1))['activity']),1)

    def test_marks_survive_activity_retention(self):
        self.event(7)
        autopilot.tick(self.now)
        self.store['u1_autopilot_activity']=[]
        self.assertEqual(autopilot.tick(self.now+timedelta(minutes=1))['activity'],[])

    def test_new_stage_emits_new_reminder(self):
        self.event(25)
        autopilot.tick(self.now)
        result=autopilot.tick(self.now+timedelta(hours=2))
        self.assertEqual(len(result['activity']),2)
        self.assertIn('1 day',result['activity'][0]['title'])

    def test_reschedule_has_independent_key(self):
        self.event(7)
        autopilot.tick(self.now)
        self.event(6)
        self.assertEqual(len(autopilot.tick(self.now)['activity']),2)

    def test_disabled_and_outside_window(self):
        self.event(80)
        self.assertEqual(autopilot.tick(self.now)['activity'],[])
        self.event(7)
        self.store['u1_autopilot_config']['enabled']=False
        self.assertEqual(autopilot.tick(self.now)['activity'],[])


if __name__ == '__main__':unittest.main()

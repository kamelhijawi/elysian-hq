import datetime as dt
import pathlib
import tempfile
import unittest
from zoneinfo import ZoneInfo
from orbit_workspace import snapshot

class OrbitTests(unittest.TestCase):
    def test_registered_departments_and_available_sources_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder)
            (root/'marketing/do').mkdir(parents=True)
            (root/'marketing/do/publisher.md').write_text('# Publisher')
            (root/'marketing/live/handoffs').mkdir(parents=True)
            (root/'marketing/live/handoffs/sales.md').write_text('# Handoff 2026-10-07\nTest')
            manifest={'centre':{'id':'hq','name':'HQ','folder':'hq'},'departments':[{'id':'marketing','name':'Marketing','folder':'marketing'},{'id':'sales','name':'Sales','folder':'sales'}], 'functions':[{'from':'marketing','to':'sales','name':'Campaign support','what':'Support'}, {'from':'marketing','to':'paused','name':'Not active','what':''}], 'paused':[{'id':'paused'}]}
            jobs={'publisher':{'dept':'marketing','recipe':'do/publisher.md','label':'Drafts','what':'Create drafts'}}
            data=snapshot(root,manifest,{}, {'marketing':[('Missing','live/missing.md'),('Handoff','live/handoffs/sales.md')]},jobs,{'publisher':{'state':'run','message':'Running'}},{},dt.datetime(2026,10,7,tzinfo=ZoneInfo('Asia/Dubai')))
            self.assertEqual([d['id'] for d in data['departments']],['hq','marketing','sales'])
            self.assertEqual(len(data['functions']),1)
            self.assertTrue(data['functions'][0]['available'])
            self.assertEqual(data['functions'][0]['date'],'2026-10-07')
            marketing=data['departments'][1]
            self.assertEqual(marketing['roles'][0]['job'],'publisher')
            self.assertEqual(marketing['jobs'][0]['state'],'run')
            self.assertEqual(len(marketing['resources']),1)
            self.assertFalse(marketing['has_report'])
            self.assertIsNone(marketing['next'])

    def test_missing_handoff_is_not_presented_as_available(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest={'centre':{'id':'hq','name':'HQ','folder':'hq'},'departments':[{'id':'a','name':'A','folder':'a'},{'id':'b','name':'B','folder':'b'}],'functions':[{'from':'a','to':'b','name':'Input','what':'Test'}]}
            data=snapshot(pathlib.Path(folder),manifest,{}, {},{}, {},{})
            self.assertFalse(data['functions'][0]['available'])
            self.assertEqual(data['functions'][0]['date'],'')
            self.assertEqual(data['departments'][1]['roles'],[])

if __name__=='__main__':unittest.main()

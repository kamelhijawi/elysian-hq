import datetime as dt
import pathlib
import tempfile
import unittest
from marketing_workspace import DUBAI, next_schedule, rows, snapshot

class WorkspaceTests(unittest.TestCase):
    def test_pipe_formats_and_prose(self):
        values=rows('Header\n| date | name | state |\n|---|---|---|\n| 2026-10-06 | One | OPEN |\n2026-10-06 | Two | DONE\nNot a date | Three | OPEN', ['date','name','state'])
        self.assertEqual([v['name'] for v in values],['One','Two'])

    def test_schedule_is_dubai_and_rolls_forward(self):
        now=dt.datetime(2026,10,6,21,0,tzinfo=DUBAI)
        schedule=[{'days':[3],'hour':7,'minute':0,'label':'Production'}]
        value=next_schedule(schedule,now)
        self.assertEqual(value['at'],'2026-10-07T07:00:00+04:00')
        self.assertIsNone(next_schedule([],now))

    def test_latest_order_wins_and_only_open_orders_are_overdue(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);live=root/'marketing-brain/live';live.mkdir(parents=True)
            (live/'production.md').write_text('2026-10-01 | V-1 | First | video | LinkedIn | 2026-10-02 | << fill: owner >> | OPEN | note\n2026-10-03 | V-1 | First | video | LinkedIn | 2026-10-02 | << fill: owner >> | DROPPED 2026-10-03 | expired\n2026-10-03 | B-1 | Second | buy | LinkedIn | 2026-10-05 | << fill: owner >> | OPEN | note\n2026-10-03 | — | paid layer | buy | Meta | — | none | OPEN | parked\n2026-10-03 | V-2 | Third | video | LinkedIn | << fill: due >> | Kamel | OPEN | note')
            result=snapshot(root,{}, {}, [], {},dt.datetime(2026,10,6,tzinfo=DUBAI))
            self.assertEqual(len(result['production']),3)
            self.assertEqual(result['counts']['open'],2)
            self.assertEqual(result['counts']['overdue'],1)
            self.assertEqual(result['counts']['unassigned'],1)
            self.assertFalse(result['sources']['ideas.md'])
            self.assertEqual(result['report']['status'],'No report')

    def test_post_body_is_from_post_section_and_bad_ids_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);posts=root/'marketing-brain/live/posts';posts.mkdir(parents=True)
            (posts/'P-1.md').write_text('# Draft\n## Post\nHello <world>\n## Notes\nInternal note')
            result=snapshot(root,{}, {}, [{'id':'P-1','status':'READY'},{'id':'../other','status':'READY'}],{})
            self.assertEqual(result['posts'][0]['body'],'Hello <world>')
            self.assertEqual(result['counts']['ready'],1)
            self.assertEqual(len(result['posts']),1)

if __name__=='__main__':unittest.main()

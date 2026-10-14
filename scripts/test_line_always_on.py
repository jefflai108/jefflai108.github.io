"""Schema-2 publication gates and deterministic pages; synthetic fixtures stay in tests."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('always_on', HERE/'render-line-always-on.py')
always_on = importlib.util.module_from_spec(spec)
spec.loader.exec_module(always_on)


def verdict(**changes):
    value={'warranted':True,'timing':4,'useful':4,'tone':5,'not_annoying':4,'grounded':True,'private':True,
           'decision_progress':None,'reason':'只提對話裡的事情。','grounding_issues':['none']}
    return dict(value,**changes)


def fixture():
    episodes=[{'id':'PV01','scope':'private','feature':'P1','polarity':'positive','title':'週六爬山',
               'tests':'出發前關心一次。','timezone':'Asia/Taipei','turns':[{'at':'2026-10-14T19:00:00+08:00','from':'user','text':'週六去爬山 <script>'}],
               'expect':{'proactive':{'min':1,'max':1,'windows':[]},'horizon':'2026-10-20T00:00:00+08:00'}}]
    rate={'hits':2,'total':2,'rate':1.0}
    arms={arm:{'recall':dict(rate),'negative_silence':{'hits':0,'total':0,'rate':None},
               'judge':{'timing':4,'useful':4,'tone':5,'not_annoying':4,'decision_progress':None,'appropriate':dict(rate)},
               'foreground':{'first_reply_ms':{'p50':5200,'p90':9300,'n':2}},'unmeasured':{'runs':0}} for arm in always_on.ARMS}
    controls={'judgments':2,'as_expected':2,'items':[{'id':'C01','judged':[{'pass':i,'as_expected':True,'verdict':verdict()} for i in (1,2)]}]}
    judge={'passes':2,'missing_judgments':0,'packet_count':2,'control_count':1,'model':'test-only-model','calibration_only':False,
           'rubric_sha256':'e'*64,'judge_sha256':'f'*64,'packets_sha256':'0'*64,'consistency':{'warranted':1.0}}
    runs=[{'episode_id':'PV01','arm':arm,'repeat':repeat,'replies':[{'at':'2026-10-14T19:00:06+08:00','text':'收到！'}],
           'proactive':[{'at':'2026-10-16T19:00:00+08:00','text':'裝備整理好了沒～','role':'unsolicited','lane':'proactive','verdict':verdict()}] if arm=='engine' else [],
           'turns':[],'checks':{'count_ok':True,'window_hit':True}} for arm in always_on.ARMS for repeat in range(2)]
    return {'schema_version':2,'complete':True,'replay_complete':True,'judging_complete':True,'publication_ready':True,'incomplete_episodes':[],
            'refs':{'existing':'a'*40,'engine':'b'*40},'models':{'foreground':'test-only-model','judge':{'model':'test-only-judge'}},
            'metadata':{'smoke':False,'executor':True,'repeats':2,'episode_count':1,'slot_count':4,
                        'host_notices':{arm:{'count':1,'sha256':'c'*64} for arm in always_on.ARMS},
                        'degraded_untagged':{arm:0 for arm in always_on.ARMS},'judge':deepcopy(judge),'judge_foreground':deepcopy(judge)},
            'episodes':episodes,'runs':runs,'summary':arms,'comparison':{'clusters':1,'recall_difference':0,'recall_difference_ci95':[-1,1]},
            'gates':{arm:{'decisions':{'suppressed':1},'by_gate':{'suppressed':{'quiet_hours':1}}} for arm in always_on.ARMS},
            'foreground_judge':{arm:{'judged':2,**{key:dict(rate) for key in ('answered','no_rejection','honest','grounded','alternatives')}} for arm in always_on.ARMS},
            'judge_controls':deepcopy(controls),'foreground_controls':deepcopy(controls),'slot_status':{arm+':measured':2 for arm in always_on.ARMS}}


class RenderTest(unittest.TestCase):
    def test_projects_actual_schema_and_escapes_case_text(self):
        projected=always_on.project(fixture(),generated_at='2026-10-14')
        self.assertIn('metadata',projected)
        self.assertNotIn('design',projected)
        page=always_on.render(projected)
        self.assertIn('&lt;script&gt;',page)
        self.assertNotIn('爬山 <script>',page)
        self.assertIn('麻吉 · 自主關心',page)
        self.assertIn('data-explorer',page)

    def test_composite_is_recomputed_and_privacy_cannot_be_offset_by_warmth(self):
        data=fixture()
        for run in data['runs']:
            for message in run['proactive']:message['verdict']=verdict(private=False,tone=5)
        projected=always_on.project(data,generated_at='2026-10-14')
        self.assertEqual(projected['summary']['engine']['judge']['appropriate'],{'hits':0,'total':2,'rate':0})
        self.assertEqual(projected['summary']['existing']['judge']['appropriate']['total'],0)

    def test_complete_flags_do_not_override_missing_evidence(self):
        mutations=[lambda d:d.update(publication_ready=False),lambda d:d.update(replay_complete=False),
                   lambda d:d['metadata'].update(smoke=True),lambda d:d['metadata'].update(executor=False),
                   lambda d:d['runs'].pop(),lambda d:d['runs'].append(deepcopy(d['runs'][0])),
                   lambda d:d['slot_status'].update({'engine:pending':1}),
                   lambda d:d['metadata']['host_notices']['engine'].update(count=0),
                   lambda d:d['metadata']['degraded_untagged'].update(engine=1),
                   lambda d:d['summary']['engine']['unmeasured'].update(runs=1),
                   lambda d:d['metadata']['judge'].update(missing_judgments=1),
                   lambda d:d['metadata']['judge_foreground'].update(passes=1),
                   lambda d:d['metadata']['judge'].update(calibration_only=True),
                   lambda d:d['foreground_controls']['items'][0]['judged'][0].update(as_expected=False),
                   lambda d:d['judge_controls']['items'][0]['judged'].pop(),
                   lambda d:d.update(foreground_judge=None),
                   lambda d:next(r for r in d['runs'] if r['proactive'])['proactive'][0].update(verdict=None)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                data=fixture();mutate(data)
                with self.assertRaises(ValueError):always_on.project(data,generated_at='2026-10-14')

    def test_private_fields_and_nonfinite_values_are_rejected(self):
        for key,value in [('credentials','secret'),('path','/Users/private/study'),('count',float('nan'))]:
            data=fixture();data['metadata'][key]=value
            with self.assertRaises(ValueError):always_on.project(data,generated_at='2026-10-14')

    def test_pending_page_contains_no_fixture_performance(self):
        page=always_on.render({'status':'pending'})
        self.assertIn('尚未有可發布',page)
        self.assertIn('等待完整量測',page)
        self.assertNotIn('100.0%',page)
        self.assertNotIn('test-only',page)

    def test_published_protocol_digest_covers_its_immutable_cases(self):
        import hashlib
        cases=json.loads((always_on.PUBLIC/always_on.CASES_NAME).read_text())
        protocol=json.loads((always_on.PUBLIC/cases['protocol_file']).read_text())
        canonical=json.dumps(protocol,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(),cases['protocol_sha256'])
        self.assertEqual(protocol['cases']['episodes'],cases['episodes'])
        self.assertNotIn('protocol_file',protocol['cases'])

    def test_method_has_blinding_controls_and_explicit_development_limits(self):
        source={'episodes':fixture()['episodes']}
        cases=always_on.public_cases(source,'a'*40,'b'*64)
        page=always_on.render_method(cases)
        for text in ('教學示意','不是人類偏好證據','第 1 次','holdout','沒有量測出的麻吉回答','data-clock'):
            self.assertIn(text,page)
        self.assertNotIn('test-only',page)

    def test_new_tabs_share_the_layout_asset(self):
        for page in (always_on.render({'status':'pending'}),always_on.render_method(always_on.public_cases({'episodes':fixture()['episodes']},'a'*40,'b'*64))):
            self.assertIn('report-layout.css',page)
            self.assertIn('benchmark-page',page)
            self.assertNotIn('max-width:1450px',page)

    def test_committed_pages_reproduce(self):
        public=always_on.PUBLIC
        data=json.loads((public/always_on.JSON_NAME).read_text())
        cases=json.loads((public/always_on.CASES_NAME).read_text())
        index=json.loads((public/always_on.ITERATIONS_NAME).read_text())
        self.assertEqual(always_on.render(data,index['iterations']),(public/always_on.PAGE_NAME).read_text())
        self.assertEqual(always_on.render_method(cases,has_results=data.get('publication_ready') is True),(public/always_on.METHOD_NAME).read_text())


if __name__=='__main__':unittest.main()

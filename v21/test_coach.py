import base64, copy, datetime as dt, json, shutil, subprocess, tempfile, unittest
from pathlib import Path
import coach

class CoachTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.c=coach.catalog()
    def setUp(self):
        self.ws=Path(tempfile.mkdtemp(prefix='ps1-v21-qa-'));self.s=coach.empty(self.c)
    def tearDown(self):
        for p in self.ws.rglob('*'):
            p.chmod(0o755 if p.is_dir() else 0o644)
        shutil.rmtree(self.ws)
    def stage(self,minutes,success=False,error=False,image=False):
        c,ws,s=self.c,self.ws,self.s
        r=coach.start(c,ws,s); a=s['active'];w=Path(r['path']);original=w.read_bytes()
        w.write_text(w.read_text()+'\n\n**Fixture de test synthétique.**\n')
        if image:
            (w.parent/'images').mkdir(exist_ok=True)
            (w.parent/'images/fixture.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jT4sAAAAASUVORK5CYII='))
            w.write_text(w.read_text()+'\n![Fixture](images/fixture.png)\n')
        first=coach.first(c,ws,s);saved=Path(s['active']['first_path']);first_sha=coach.sha(saved)
        self.assertEqual(coach.first(c,ws,s),first)
        w.write_text(w.read_text()+'\n\nAutocorrection synthétique.\n')
        f=coach.finish(c,ws,s,minutes);self.assertEqual(coach.finish(c,ws,s,minutes),f);self.assertEqual(coach.sha(saved),first_sha)
        if image:self.assertTrue((saved.parent/'images/fixture.png').is_file())
        self.assertEqual(coach.start(c,ws,s)['phase'],'review')
        d=coach.read(f['review_template']);hp,h=coach.adapt._handoff(ws,d['handoff_id'])
        def evidence(role):
            m=h['snapshots'][role];path=m['document'];sha=next(x['sha256'] for x in m['files'] if x['path']==path)
            return dict(snapshot=role,path=path,sha256=sha,medium='text',certainty='confirmed',visually_reviewed=False,locator_fr='Fixture synthétique de test; pas une évaluation personnelle.')
        if success:
            for o in d['observations']:
                o.update(outcome='correct',confidence=80,assistance='none',criteria_passed=list(range(len(o['rubric_fr']))),point_ids=list(o['eligible_points']),novel=True,method_choice=True,explanation_verified=True,error_type='none',observation_fr='Réussite synthétique pour le test de l’algorithme.',evidence=[evidence('first')])
            d.update(exit_criteria_verified=list(range(len(c['nodes'][a['lesson_id']]['exit_criteria_fr']))),correction_reviewed=True,anki_reviewed=True)
        if error:
            o=next(o for o in d['observations'] if o['task_id']=='D00-E04')
            o.update(outcome='incorrect',confidence=95,assistance='none',point_ids=list(o['eligible_points']),error_type='concept',error_tags=['variance_linearity'],corrected_status='self_corrected',observation_fr='Erreur synthétique sur la variance; corrigée après consultation.',evidence=[evidence(k) for k in ('first','corrected','reference')])
            d['pilot_metrics']=dict(consignes_min=5,tentative_min=45,correction_min=10,friction_fr='Test isolé.')
            bad=copy.deepcopy(d);bad['observations'][3]['evidence'][0]['sha256']='0'*64
            with self.assertRaises(ValueError):coach.review(c,ws,s,bad)
            self.assertEqual(len(s['history']),0)
        result=coach.review(c,ws,s,d)
        self.assertIsNone(s['active']);self.assertEqual(coach.sha(saved),first_sha)
        return result
    def test_coverage(self):
        c=self.c;gaps=set(coach.read(c['root']/'database/derived/p0_closure.json')['point_ids_not_individually_resolved'])
        self.assertEqual(len(gaps),33);self.assertEqual({p['point_id'] for p in c['probes'].values()},gaps)
        self.assertEqual(sum(n['minutes'] for n in c['nodes'].values()),1200)
        self.assertEqual(len(c['card_ids']),71)
        for p in c['probes'].values():
            for f in 'AB':
                w=coach.render_probe(p,f,'work');r=coach.render_probe(p,f,'correction')
                self.assertNotIn(p['forms'][f]['correction_md'],w);self.assertIn(p['forms'][f]['correction_md'],r)
                self.assertEqual(c['links'][p['id']+'-'+f],{p['point_id']:[0]})
        self.assertEqual(c['p0']-set(p for a in c['links'].values() for p in a),set())
    def test_initial_budget_no_probe(self):
        b=coach.budget(self.c,self.s);self.assertEqual(b['planned_core_remaining'],1200);self.assertEqual(b['available_extra'],0)
        with self.assertRaises(ValueError):coach.open_probe(self.c,self.ws,self.s,'P17','A')
    def test_full_handoff_and_next(self):
        self.stage(60,error=True,image=True)
        p=coach.read(self.ws/'plan.json');self.assertEqual(p['budget']['spent'],60);self.assertEqual(p['next_stage']['id'],'L01');self.assertTrue(p['priority_errors'])
        self.assertTrue(list((self.ws/'reviews').glob('*.json')))
        r=coach.start(self.c,self.ws,self.s);self.assertEqual(r['activity_id'],'L01');self.assertTrue(Path(r['path']).is_file())
        self.assertTrue((Path(r['path']).parent/'generation.json').is_file())
    def test_earned_minutes_probe(self):
        self.stage(60);r=self.stage(12,success=True);self.assertTrue(r['release_verified'])
        self.assertEqual(r['budget']['available_extra'],self.c['nodes']['L01']['minutes']-12)
        offer=next(x for x in r['optional_probes'] if x['id']=='P17')
        p=coach.open_probe(self.c,self.ws,self.s,'P17','A');self.assertEqual(p['minutes'],offer['minutes'])
        coach.first(self.c,self.ws,self.s);f=coach.finish(self.c,self.ws,self.s,offer['minutes'])
        self.assertEqual(coach.budget(self.c,self.s)['probe_minutes_used'],offer['minutes'])
        r=coach.review(self.c,self.ws,self.s,coach.read(f['review_template']))
        self.assertEqual(r['budget']['available_extra'],self.c['nodes']['L01']['minutes']-12-offer['minutes'])
        self.assertFalse(any(x['id']=='P17' for x in r['optional_probes']))
    def test_transfer_policy(self):
        c=self.c;s=self.s;p=c['probes']['P17']['point_id'];t=dt.datetime(2026,11,24,tzinfo=dt.timezone.utc)
        def event(id,when,kind='probe',obs=True,**kw):
            o=dict(task_id=id,point_ids=[p],outcome='correct',assistance='none',novel=True,method_choice=True,changed_context=True,confidence=80,error_type='none',explanation_verified=True);o.update(kw)
            return dict(kind=kind,first_at=when.isoformat(),observations=[o] if obs else [])
        s['history']=[event('P17-A',t),event('P17-B',t+dt.timedelta(days=2))];self.assertEqual(coach.results_by_point(c,s)[p]['level'],'autonome')
        s['history'].insert(1,event('L02',t+dt.timedelta(hours=1),'stage',False));self.assertEqual(coach.results_by_point(c,s)[p]['level'],'transfert')
        s['history'][-1]['first_at']=(t+dt.timedelta(hours=2)).isoformat();self.assertEqual(coach.results_by_point(c,s)[p]['level'],'autonome');self.assertTrue(coach.results_by_point(c,s)[p]['within_session_transfer'])
        s['history'].append(event('P17-B',t+dt.timedelta(hours=3),outcome='incorrect'));self.assertEqual(coach.results_by_point(c,s)[p]['level'],'a_revoir')
        s['history'].append(event('P17-B',t+dt.timedelta(hours=4),assistance='correction'));self.assertEqual(coach.results_by_point(c,s)[p]['level'],'compris')
    def test_graph_export(self):
        self.stage(60)
        r=subprocess.run(['node','--input-type=module','-e', '''import fs from 'node:fs';import {validateState} from './app/state.js';const c=JSON.parse(fs.readFileSync('data/curriculum.json'));const d=JSON.parse(fs.readFileSync(process.argv[1]));validateState(d,c);if(Object.keys(d.competencies).length)throw Error('Unexpected credit');console.log('PASS');''',str(self.ws/'graph_progress.json')],cwd=self.c['root'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr);self.assertIn('PASS',r.stdout)
    def test_conservative_budget(self):
        self.stage(40);self.stage(10);self.assertEqual(coach.budget(self.c,self.s)['available_extra'],0)
    def test_high_confidence_concept_priority(self):
        self.assertGreater(coach.severity(dict(outcome='incorrect',error_type='concept',confidence=95)),coach.severity(dict(outcome='incorrect',error_type='calculation',confidence=20)))

if __name__=='__main__':unittest.main(verbosity=2)

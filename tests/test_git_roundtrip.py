#!/usr/bin/env python3
"""A real local bare Git remote; synthetic work only, never publish fixtures."""
import base64, json, shutil, subprocess, tempfile, hashlib, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jT4sAAAAASUVORK5CYII=')
def command(cwd,*args):
    return subprocess.run(args,cwd=cwd,check=True,capture_output=True,text=True).stdout

def coach(root,*args):
    return json.loads(command(root,'python3','v21/coach.py',*args))

def identity(p):
    command(p,'git','config','user.email','ps1-test@example.invalid');command(p,'git','config','user.name','PS1 test fixture')

def publish(p,msg):
    command(p,'git','add','progress/');command(p,'git','commit','-m',msg);command(p,'git','push')

class GitRoundtrip(unittest.TestCase):
    def test_clone_attempt_review_pull_resume(self):
        with tempfile.TemporaryDirectory(prefix='ps1-public-qa-') as td:
            t=Path(td); seed=t/'seed'; remote=t/'remote.git';student=t/'élève workspace';reviewer=t/'tuteur clone'
            shutil.copytree(ROOT,seed,ignore=shutil.ignore_patterns('.git','__pycache__','progress'))
            (seed/'progress').mkdir();(seed/'progress/.gitkeep').touch()
            command(t,'git','init','--bare','-b','main',str(remote));command(seed,'git','init','-b','main');identity(seed)
            command(seed,'git','add','.');command(seed,'git','commit','-m','fixture baseline');command(seed,'git','remote','add','origin',str(remote));command(seed,'git','push','-u','origin','main')
            command(t,'git','clone',str(remote),str(student));identity(student)
            start=coach(student,'start');self.assertEqual(start['activity_id'],'D00');work=Path(start['path']);self.assertTrue(work.is_relative_to(student/'progress'))
            (work.parent/'images').mkdir();(work.parent/'images/fixture.png').write_bytes(PNG)
            work.write_text(work.read_text()+'\n\nRéponse synthétique.\n\n![Fixture](images/fixture.png)\n')
            first=coach(student,'first');saved=Path(first['first'])/work.name;h=hashlib.sha256(saved.read_bytes()).hexdigest()
            work.write_text(work.read_text()+'\n\nAutocorrection synthétique.\n');end=coach(student,'finish','60')
            (student/'progress/.Rhistory').write_text('NOT FOR PUBLICATION')
            publish(student,'D00 synthetic attempt');self.assertNotIn('.Rhistory',command(student,'git','ls-files','progress/'))
            command(t,'git','clone',str(remote),str(reviewer));identity(reviewer)
            s=coach(reviewer,'start');self.assertEqual(s['phase'],'review');self.assertTrue(Path(s['path']).is_relative_to(reviewer))
            self.assertEqual(hashlib.sha256((reviewer/'progress/first/D00'/work.name).read_bytes()).hexdigest(),h)
            self.assertEqual((reviewer/'progress/first/D00/images/fixture.png').read_bytes(),PNG)
            d=json.loads(Path(s['review_template']).read_text());d['reviewer']='human'
            review_path=t/'review_fixture.json';review_path.write_text(json.dumps(d))
            result=coach(reviewer,'review',str(review_path));self.assertEqual(result['next_stage']['id'],'L01');self.assertEqual(result['budget']['spent'],60)
            publish(reviewer,'D00 synthetic review');command(student,'git','pull','--ff-only')
            start2=coach(student,'start');self.assertEqual(start2['activity_id'],'L01');self.assertTrue(Path(start2['path']).parent.joinpath('data/mesures.csv').is_file())
            state=json.loads((student/'progress/coach_state.json').read_text());self.assertFalse(Path(state['active']['work_path']).is_absolute());self.assertFalse(Path(state['history'][0]['work_path']).is_absolute());self.assertEqual(state['project'],'ps1-public-20h')
            self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(),h)
            print('PASS actual local clone, image capture, commit/push, second clone, review, push, pull and next lesson')

if __name__=='__main__':unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Local, explicit review workflow; no automatic grading or background agent."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, re, shutil, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import adapt
from snapshot_attempt import snapshot
VERSION='2.1.1'
PROJECT_ID='ps1-public-20h'

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.ps1-',dir=p.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")
def parse_time(v): return dt.datetime.fromisoformat(v)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
    if not ok: raise ValueError(msg)

def catalog(root=ROOT):
    root=Path(root).resolve();_,nodes,lessons,exercises,blocks=adapt._catalog(root)
    tasks={eid:dict(e,lesson_id=lid) for eid,(lid,e) in exercises.items()}
    for lid,m in lessons.items():
        for v in m.get('variants',[]): tasks[v['id']]=dict(v,lesson_id=lid)
    probes={r['id']:r for r in read(root/'v21/probes.json')['records']}
    links={}
    for r in read(root/'database/derived/diagnostic_overlays.json')['records']:
        for a in r['assessment_refs']:
            if a['exercise_id'] in tasks:
                links.setdefault(a['exercise_id'],{})[r['point_id']]=a['rubric_indices']
    for p in probes.values():
        for form in 'AB':
            tid=p['id']+'-'+form
            tasks[tid]={'id':tid,'lesson_id':p['primary_lesson_id'],'rubric_fr':[p['forms'][form].get('rubric_fr',p['rubric_fr'])], 'minutes':p['attempt_minutes'],'point_probe':True}
            links[tid]={p['point_id']:[0]}
    points={r['point_id']:r for r in read(root/'database/derived/readiness_audit.json')['records']}
    for p in probes.values():
        points[p['point_id']]=dict(points[p['point_id']],primary_lesson_id=p['primary_lesson_id'])
    p0=set(read(root/'database/derived/p0_closure.json')['point_ids'])
    card_ids={r['id'] for r in read(root/'anki/deck/manifest.json')['notes']}
    return dict(root=root,nodes=nodes,lessons=lessons,tasks=tasks,links=links,probes=probes,points=points,p0=p0,card_ids=card_ids)

def empty(c): return dict(version=VERSION,project=PROJECT_ID,active=None,history=[],created_at=now())
def load(c,ws):
    f=ws/'coach_state.json';s=read(f) if f.is_file() else empty(c)
    require(s.get('version')==VERSION and s.get('project')==PROJECT_ID,'Session incompatible : utiliser le dossier du projet d’origine.')
    require(isinstance(s.get('history'),list),'Historique invalide.')
    return relocate(c,ws,s,decode=True)

def relocate(c,ws,state,decode=False):
    """Encode only designated file paths, preserving learner text verbatim."""
    import copy
    value=copy.deepcopy(state)
    workspace=Path(ws).resolve()
    for record in ([value['active']] if value.get('active') else [])+value.get('history',[]):
        for key in ('work_path','correction_path','first_path'):
            if key not in record: continue
            raw=Path(record[key])
            if decode:
                require(not raw.is_absolute() and '..' not in raw.parts,'Chemin de session non portable.')
                path=(workspace/raw).resolve()
                require(path.is_relative_to(workspace),'Chemin hors session.')
                record[key]=str(path)
            else:
                path=raw.resolve()
                require(path.is_relative_to(workspace),'Chemin hors session.')
                record[key]=path.relative_to(workspace).as_posix()
    return value

def results_by_point(c,s):
    levels={}; history={};stage_count=0
    for activity_index,h in enumerate(s['history']):
        if h['kind']=='stage':stage_count+=1
        for o in h['observations']:
            for p in o['point_ids']:
                events=history.setdefault(p,[])
                independent=o['outcome']=='correct' and o['assistance']=='none'
                events.append(dict(task_id=o['task_id'],stage_count=stage_count,activity_index=activity_index,at=h['first_at'],independent=independent,novel=o['novel'],method_choice=o['method_choice'],changed_context=o['changed_context'],outcome=o['outcome'],confidence=o['confidence'],error_type=o['error_type'],explanation_verified=o.get('explanation_verified',False)))
    for p,events in history.items():
        level='non_evalue';independent=[];session_transfer=False
        for e in events:
            if e['outcome'] in ('incorrect','partial'):
                level='a_revoir';independent=[];session_transfer=False;continue
            if e['outcome']!='correct':continue
            if not e['independent']:
                if e['explanation_verified'] and level in ('non_evalue','a_revoir'):level='compris'
                continue
            if level not in ('autonome','transfert'):level='application'
            if e['novel'] and e['method_choice'] and level!='transfert':level='autonome'
            if e['novel'] and e['method_choice'] and e['changed_context']:
                for before in independent:
                    if before['task_id']==e['task_id'] or not any(h['kind']=='stage' for h in s['history'][before['activity_index']+1:e['activity_index']]):continue
                    # Two distinct tasks separated by another reviewed core activity.
                    session_transfer=True
                    if parse_time(e['at'])-parse_time(before['at'])>=dt.timedelta(hours=24):level='transfert'
            independent.append(e)
        levels[p]=dict(level=level,within_session_transfer=session_transfer,observations=len(events),last_task=events[-1]['task_id'])
    return levels

def budget(c,s):
    finished={h['activity_id']:h for h in s['history'] if h['kind']=='stage'}
    pending=s['active'] if s['active'] and s['active']['phase']=='review' else None
    spent=sum(h['minutes'] for h in s['history'])+(pending['minutes'] if pending else 0)
    # Completed protected stages never donate minutes; only evidenced, complete lessons do.
    savings=sum(max(0,c['nodes'][lid]['minutes']-h['minutes']) for lid,h in finished.items() if c['nodes'][lid]['kind']=='lesson' and h['release_verified'])
    used_probes=sum(h['minutes'] for h in s['history'] if h['kind']=='probe')+(pending['minutes'] if pending and pending['kind']=='probe' else 0)
    future=sum(n['minutes'] for lid,n in c['nodes'].items() if lid not in finished and not (pending and pending['kind']=='stage' and lid==pending['activity_id']))
    available=max(0,min(savings-used_probes,1200-spent-future))
    return dict(total=1200,spent=spent,remaining=max(0,1200-spent),planned_core_remaining=future,verified_savings=savings,probe_minutes_used=used_probes,available_extra=available,shortfall=max(0,spent+future-1200),overrun=max(0,spent-1200))

def severity(o):
    if o['outcome'] not in ('incorrect','partial'):return 0
    # Priority, not a predicted mark. A high-confidence conceptual error is costly.
    base={'concept':5,'hypothesis':5,'method':4,'object':5,'r':3,'writing':2,'calculation':1,'unknown':3}.get(o['error_type'],0)
    return 10*base+(o['confidence'] or 0)/10+(5 if o['outcome']=='incorrect' else 0)

def recommendations(c,s):
    done={h['activity_id'] for h in s['history'] if h['kind']=='stage'};levels=results_by_point(c,s);b=budget(c,s)
    nxt=next((n for n in sorted(c['nodes'].values(),key=lambda x:x['order']) if n['id'] not in done),None)
    mode='parcours_complet';known=0;target=[]
    if nxt and nxt['kind']=='lesson':
        target=[p for p in c['p0'] if c['points'][p]['primary_lesson_id']==nxt['id']]
        known=sum(levels.get(p,{}).get('level') in ('application','autonome','transfert') for p in target)
        if target and known/len(target)>=.6 and not any(levels.get(p,{}).get('level')=='a_revoir' for p in target):mode='controle_avant_cours'
    # Recent unresolved errors before less useful optional recall. Do not rate unknown points as failed.
    latest={o['task_id']:o for h in s['history'] for o in h['observations']}
    errors=sorted([o for o in latest.values() if severity(o)>0],key=lambda o:(-severity(o),o['task_id']))
    seen={h['activity_id']:h for h in s['history'] if h['kind']=='probe'}
    offers=[]
    for p in c['probes'].values():
        if p['primary_lesson_id'] not in done:continue
        a=p['id']+'-A'; bb=p['id']+'-B';form=None
        if a not in seen:form='A'
        elif bb not in seen:
            # Need intervening work, not immediate repetition of the same question.
            i=next(i for i,h in enumerate(s['history']) if h['activity_id']==a)
            if any(h['kind']=='stage' for h in s['history'][i+1:]):form='B'
        if form is None:continue
        cost=p['attempt_minutes']+p['correction_minutes'];lv=levels.get(p['point_id'],{}).get('level','non_evalue')
        if lv=='transfert':continue
        if cost<=b['available_extra']:
            offers.append(dict(id=p['id'],form=form,point_id=p['point_id'],lesson_id=p['primary_lesson_id'],objective_fr=p['objective_fr'],minutes=cost,priority=0 if lv=='a_revoir' else (1 if form=='B' else 2)))
    offers.sort(key=lambda x:(x['priority'],x['minutes'],x['id']))
    # Exact existing cards only. No new notes or mutation of the learner collection.
    a4={};cards={};block_index={x['id']:x for m in c['lessons'].values() for x in m.get('blocks',[])}
    point_specs={p['id']:p for p in read(c['root']/'database/knowledge/knowledge_points.json')['records']}
    recurrent={}
    def related_blocks(o):
        t=c['tasks'][o['task_id']];ids=set(t.get('block_ids',[]));source=set()
        for pid in o['point_ids']:source.update(point_specs[pid]['required_block_ids'])
        if t.get('point_probe'):source.update(c['probes'][o['task_id'].split('-')[0]]['source_block_ids'])
        ids.update(bid for bid,block in block_index.items() if source & set(block.get('source_block_ids',[])))
        return ids & set(block_index)
    for h in s['history']:
        for o in h['observations']:
            if severity(o)>0:
                for bid in related_blocks(o):recurrent.setdefault(bid,set()).add(h['activity_id'])
    for o in errors:
        for bid in related_blocks(o):
            if bid in c['card_ids']:cards[bid]=max(cards.get(bid,0),severity(o))
            if block_index[bid]['retention'] in ('reference','reconstruct') or len(recurrent.get(bid,set()))>=2:
                a4[bid]=max(a4.get(bid,0),severity(o))
    # Explicit candidate selection for slow retrieval, based on reviewer observations.
    for h in s['history']:
        for entry in h.get('a4',[]):a4[entry['block_id']]=max(a4.get(entry['block_id'],0),entry['priority'])
    block_index={x['id']:x for m in c['lessons'].values() for x in m.get('blocks',[])}
    shortlist=[]
    for bid,priority in sorted(a4.items(),key=lambda x:(-x[1],x[0])):
        if bid in block_index and len(shortlist)<8:
            block=block_index[bid];shortlist.append(dict(block_id=bid,title_fr=block['title_fr'],source_path=f'lessons/{bid.split(chr(45))[0]}/{bid.split(chr(45))[0]}_Travail.Rmd',retention=block['retention'],priority=priority,action_fr='Sélectionner seulement si une consultation réduit une erreur ou un temps de reconstruction; garder les hypothèses.'))
    return dict(version=VERSION,active=s['active'],budget=b,next_stage=None if nxt is None else dict(id=nxt['id'],title_fr=nxt['title_fr'],minutes=nxt['minutes'],mode=mode,independent_point_evidence=known,point_count=len(target)),point_levels=levels,priority_errors=[dict(task_id=o['task_id'],score=severity(o),observation_fr=o['observation_fr']) for o in errors[:12]],optional_probes=offers,anki_priority=[dict(block_id=bid,subdeck='PS1::Parcours 20 h::'+bid.split('-')[0]) for bid in sorted(cards,key=lambda bid:(-cards[bid],bid))[:8]],a4_shortlist=shortlist,policy_fr='Les 20 h incluent le diagnostic. Les sondes utilisent uniquement du temps libéré par des leçons vérifiées. Pas de validation automatique ni de saut des problèmes de synthèse.')

def save(c,ws,s):
    plan=recommendations(c,s)
    write(ws/'coach_state.json',relocate(c,ws,s));write(ws/'plan.json',relocate(c,ws,plan))
    # A readable plan in RStudio; contains no exercise solutions.
    b=plan['budget'];n=plan['next_stage'];counts={x:sum(v['level']==x for v in plan['point_levels'].values()) for x in ('compris','application','autonome','transfert','a_revoir')}
    lines=['---','title: "PS1 · Tableau personnel"','lang: fr','output: html_notebook','---','',f"**Temps déclaré : {b['spent']} / 1 200 min.** Restant : {b['remaining']} min; marge disponible : {b['available_extra']} min.",'Points observés : '+', '.join(f'{k} : {v}' for k,v in counts.items())+'.', f"Points P0 sans observation : {len(c['p0']-set(plan['point_levels']))} / {len(c['p0'])}."]
    if b['shortfall']:lines.append(f"**Attention :** {b['shortfall']} min de déficit par rapport aux activités restantes. Ne pas ajouter de sondes; revoir la répartition avec le tuteur.")
    if n:lines+=['',f"**Prochaine activité :** {n['id']} · {n['title_fr']} ({n['minutes']} min).",'Mode : '+('contrôle avant lecture du cours, puis retour ciblé si nécessaire.' if n['mode']=='controle_avant_cours' else 'parcours normal.')]
    lines+=['','## Erreurs à reprendre']+[f"- {o['task_id']} : {o['observation_fr']}" for o in plan['priority_errors']]
    lines+=['','## Sondes facultatives (aucun corrigé ici)']+[f"- {p['id']}-{p['form']} · {p['objective_fr']} ({p['minutes']} min)" for p in plan['optional_probes'][:5]]
    lines+=['','## Anki : priorité aux cartes dues, puis aux cartes ciblées']+[f"- {p['block_id']} · {p['subdeck']}" for p in plan['anki_priority']]
    lines+=['','## A4 : candidats à sélectionner, pas à recopier tous']+[f"- [{p['block_id']}]({os.path.relpath(c['root']/p['source_path'],ws)}#{p['block_id']}) · {p['title_fr']} ({p['retention']}). {p['action_fr']}" for p in plan['a4_shortlist']]
    lines+=['','Le graphe v2 conserve son propre suivi; importer `graph_progress.json` dans une vue vierge pour reporter les activités relues (les minutes des sondes sont rattachées à leur leçon). Exporter d’abord tout suivi manuel à conserver. Aucune compétence globale n’est déduite des points.']
    (ws/'Tableau.Rmd').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Compatible with the existing graph. No fabricated competency evidence.
    curriculum=read(c['root']/'data/curriculum.json');lessons={h['activity_id']:{'status':'worked','minutes_spent':h['minutes'],'updated_at':h['reviewed_at']} for h in s['history'] if h['kind']=='stage'}
    for h in s['history']:
        if h['kind']=='probe' and h['lesson_id'] in lessons:
            lessons[h['lesson_id']]['minutes_spent']+=h['minutes']
            lessons[h['lesson_id']]['updated_at']=h['reviewed_at']
    write(ws/'graph_progress.json',dict(schema_version='1.0.0',curriculum_id=curriculum['curriculum_id'],curriculum_version=curriculum['version'],is_demo=False,updated_at=now(),lessons=lessons,competencies={}))
    return plan

def materialize_stage(c,ws,s,lid):
    src=c['root']/'lessons'/lid
    previous=next((h for h in reversed(s['history']) if h['kind']=='stage'),None)
    if previous and (c['nodes'][lid]['kind']=='lesson' or lid=='F01'):
        prep=adapt.prepare_next(c['root'],ws,lid,[Path(previous['work_path'])]);dest=Path(prep['path'])
    else:
        dest=ws/'activities'/lid
        require(not dest.exists(),'Dossier de travail déjà présent; ne pas écraser.')
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(src,dest)
        for p in dest.glob('*.Rmd'):
            p.write_text(adapt._rewrite_document_links(p.read_text(encoding='utf-8'),src,dest,c['root']),encoding='utf-8')
    w=dest/(lid+'_Travail.Rmd');r=dest/(lid+'_Corrige.Rmd');require(w.is_file() and r.is_file(),'Paire Rmd absente.')
    ids=[e['id'] for e in c['lessons'][lid].get('exercises',[])]
    if (dest/'generation.json').is_file():
        g=read(dest/'generation.json');ids+=list(dict.fromkeys(t['variant_id'] for t in g.get('tasks',[])))
    return dict(activity_id=lid,lesson_id=lid,kind='stage',phase='work',work_path=str(w),correction_path=str(r),task_ids=ids,started_at=now(),correction_sha=sha(r))

def render_probe(p,form,role):
    tid=p['id']+'-'+form;lid=p['primary_lesson_id'];d=p['forms'][form];body=d['prompt_md'] if role=='work' else d['correction_md']+'\n\n**Critère :** '+d.get('rubric_fr',p['rubric_fr'])
    # No method cue, solution, topic title or rubric in the work file.
    header=f'''---\ntitle: "Contrôle ciblé {tid}"\nlang: fr\noutput: html_notebook\neditor_options:\n  chunk_output_type: inline\nps1:\n  lesson_id: {lid}\n  document_role: {role}\n  minutes: {p['attempt_minutes']+p['correction_minutes']}\n---\n\n'''
    if role=='work' and p['id'] in {'P05','P16','P17','P18','P19','P20','P21','P22'}:
        body+='\n\n```{r reponse}\n# Votre code\n```\n'
    if role=='work':body+=f'\n\n**Tentative ({p["attempt_minutes"]} min) :**\n\n\n**Confiance avant correction :** … / 100. **Aide :** …\n\n'
    return header+f'## {tid}\n\n'+body+'\n'

def materialize_probe(c,ws,pid,form):
    p=c['probes'][pid];tid=pid+'-'+form;dest=ws/'activities'/tid;require(not dest.exists(),'Ce contrôle existe déjà.')
    dest.mkdir(parents=True);w=dest/(tid+'_Travail.Rmd');r=dest/(tid+'_Corrige.Rmd')
    w.write_text(render_probe(p,form,'work'),encoding='utf-8');r.write_text(render_probe(p,form,'correction'),encoding='utf-8')
    return dict(activity_id=tid,lesson_id=p['primary_lesson_id'],kind='probe',phase='work',work_path=str(w),correction_path=str(r),task_ids=[tid],started_at=now(),correction_sha=sha(r),reserved_minutes=p['attempt_minutes']+p['correction_minutes'])

def start(c,ws,s):
    if s['active']:
        a=s['active'];return dict(status='RESUME',path=a['work_path'],phase=a['phase'],activity_id=a['activity_id'],correction_path=a['correction_path'] if a['phase']=='correction' else None,handoff=str(ws/'handoffs'/a['handoff_id']) if a['phase']=='review' else None,review_template=str(ws/'review_queue'/(a['handoff_id']+'.json')) if a['phase']=='review' else None)
    plan=recommendations(c,s);n=plan['next_stage'];require(n is not None,'Toutes les activités principales ont été parcourues.')
    require(plan['budget']['remaining']>0,'Budget de 20 heures atteint.')
    # Never silently squeeze the exam or syntheses into an impossible budget.
    require(plan['budget']['remaining']>=n['minutes'],'Temps insuffisant pour cette activité. Revoir le plan sans dépasser les 20 h.')
    a=materialize_stage(c,ws,s,n['id']);s['active']=a;save(c,ws,s)
    return dict(status='READY',path=a['work_path'],activity_id=a['activity_id'],minutes=n['minutes'],mode=n['mode'])

def open_probe(c,ws,s,pid,form):
    require(s['active'] is None,'Terminer et faire relire le travail actif avant une sonde.')
    offers=recommendations(c,s)['optional_probes'];require(any(x['id']==pid and x['form']==form for x in offers),'Sonde indisponible : temps, prérequis ou espacement insuffisant.')
    a=materialize_probe(c,ws,pid,form);s['active']=a;save(c,ws,s);return dict(status='READY',path=a['work_path'],minutes=a['reserved_minutes'],activity_id=a['activity_id'])

def first(c,ws,s):
    a=s['active'];require(a is not None and a['phase'] in ('work','correction'),'Aucune première tentative active à figer.')
    if a['phase']=='correction':
        adapt._verify_files(Path(a['first_path']).parent,a['first_manifest']['files']);require(sha(a['correction_path'])==a['correction_sha'],'Corrigé modifié.')
        return dict(status='FIRST_SAVED',path=a['correction_path'],first=str(Path(a['first_path']).parent),activity_id=a['activity_id'])
    require(sha(a['correction_path'])==a['correction_sha'],'Corrigé de référence modifié.')
    dest=ws/'first'/a['activity_id'];m=snapshot(Path(a['work_path']),dest);adapt._seal(dest)
    a.update(phase='correction',first_path=str(dest/m['document']),first_manifest=m,first_at=now());save(c,ws,s)
    return dict(status='FIRST_SAVED',path=a['correction_path'],first=str(dest),activity_id=a['activity_id'])

def template(c,a,h,minutes):
    obs=[]
    for tid in a['task_ids']:
        t=c['tasks'][tid];obs.append(dict(task_id=tid,outcome='unassessed',confidence=None,assistance='unknown',criteria_passed=[],point_ids=[],novel=False,method_choice=False,changed_context=False,explanation_verified=False,error_type='unknown',error_tags=[],corrected_status='not_evaluated',observation_fr='',evidence=[],rubric_fr=t['rubric_fr'],eligible_points=c['links'].get(tid,{})))
    return dict(version=VERSION,activity_id=a['activity_id'],handoff_id=h['handoff_id'],reviewer='assistant',minutes=minutes,observations=obs,exit_criteria_verified=[],correction_reviewed=False,anki_reviewed=False,a4=[],adaptive_review=None,pilot_metrics=None,notes_fr='Ne renseigner que les critères effectivement relus; consulter les pièces figées. Aucune preuve par défaut.')

def finish(c,ws,s,minutes):
    a=s['active'];require(a is not None and a['phase'] in ('correction','review'),'Figer la première tentative avant l’autocorrection.')
    if a['phase']=='review':
        require(minutes==a['minutes'],'Durée déjà enregistrée; ne pas créer une nouvelle tentative.')
        hp,_=adapt._handoff(ws,a['handoff_id']);return dict(status='AWAITING_REVIEW',activity_id=a['activity_id'],handoff=str(hp),review_template=str(ws/'review_queue'/(a['handoff_id']+'.json')),minutes=minutes)
    require(type(minutes) is int and 1<=minutes<=1200,'Indiquer les minutes réellement travaillées, Anki compris.')
    adapt._verify_files(Path(a['first_path']).parent,a['first_manifest']['files']);require(sha(a['correction_path'])==a['correction_sha'],'Corrigé modifié.')
    hid='attempt-'+a['activity_id'].lower();h=adapt.capture_handoff(c['root'],ws,hid,a['lesson_id'],a['first_path'],a['work_path'],a['correction_path']);a.update(phase='review',handoff_id=hid,minutes=minutes)
    p=ws/'review_queue'/(hid+'.json');write(p,template(c,a,h,minutes));save(c,ws,s)
    return dict(status='AWAITING_REVIEW',activity_id=a['activity_id'],handoff=h['path'],review_template=str(p),minutes=minutes)

def review(c,ws,s,d):
    a=s['active'];require(a and a['phase']=='review','Aucune tentative en attente de revue.')
    require(d['version']==VERSION and d['activity_id']==a['activity_id'] and d['handoff_id']==a['handoff_id'] and d['reviewer'] in ('human','assistant') and type(d['minutes']) is int and d['minutes']==a['minutes'],'Revue incompatible avec la tentative figée.')
    hp,h=adapt._handoff(ws,a['handoff_id']);ids=set(a['task_ids']);seen=set();obs=[]
    for o in d['observations']:
        tid=o['task_id'];require(tid in ids and tid not in seen,'Exercice inconnu ou répété.');seen.add(tid)
        t=c['tasks'][tid];r=o['outcome'];require(r in ('correct','partial','incorrect','unanswered','unassessed'),'Résultat invalide.')
        require(o['confidence'] is None or type(o['confidence']) is int and 0<=o['confidence']<=100,'Confiance invalide.')
        require(o['assistance'] in ('none','course','hint','correction','unknown'),'Aide invalide.')
        require(all(type(o[k]) is bool for k in ('novel','method_choice','changed_context','explanation_verified')),'Indices d’autonomie invalides.')
        require(o['error_type'] in ('concept','hypothesis','object','method','r','writing','calculation','unknown','none'),'Type d’erreur invalide.')
        criteria=o['criteria_passed'];require(isinstance(criteria,list) and all(type(i) is int and 0<=i<len(t['rubric_fr']) for i in criteria) and len(set(criteria))==len(criteria),'Indices de critères invalides.')
        point_ids=o['point_ids'];links=c['links'].get(tid,{});require(isinstance(point_ids,list) and len(set(point_ids))==len(point_ids) and set(point_ids)<=set(links),'Lien point/exercice non vérifié.')
        if r=='unassessed':require(not criteria and not point_ids and not o['evidence'],'Un point non évalué ne reçoit aucune preuve.')
        elif r=='unanswered':require(not criteria and not point_ids,'Une réponse absente n’attribue aucun point.')
        else:
            require(bool(o['observation_fr'].strip()) and o['evidence'],'Constat et preuve explicites requis.')
            roles=set()
            for ev in o['evidence']:
                role=ev['snapshot'];require(role in h['snapshots'],'Pièce inconnue.')
                require(adapt._validate_evidence(hp/'snapshots'/role,h['snapshots'][role],ev),'Preuve incertaine : laisser non évalué.');roles.add(role)
            require('first' in roles,'La preuve doit citer la première tentative, pas seulement le corrigé.')
        tags=o.get('error_tags',[]);require(isinstance(tags,list) and len(set(tags))==len(tags) and set(tags)<=set(t.get('error_tags',[])),'Étiquette d’erreur non reliée à cet exercice.')
        require(o.get('corrected_status') in ('not_evaluated','still_present','self_corrected'),'État d’autocorrection invalide.')
        if r=='correct':
            require(set(criteria)==set(range(len(t['rubric_fr']))),'Un exercice déclaré correct doit satisfaire tous ses critères.')
            require(all(set(links[p])<=set(criteria) for p in point_ids),'Critère précis de point manquant.')
        if o['changed_context']:require(o['novel'] and o['method_choice'],'Le transfert exige un contexte nouveau et un choix autonome.')
        if t.get('point_probe') and tid.endswith('-B') and r=='correct' and point_ids:
            prev=next((h for h in s['history'] if h['activity_id']==tid[:-1]+'A'),None)
            require(prev and any(x['outcome']=='correct' and x['assistance']=='none' and set(point_ids)<=set(x['point_ids']) for x in prev['observations']), 'La forme B seule ne valide pas toute la portée du point; consigner la réponse sans attribuer ce point.')
        obs.append({k:o[k] for k in ['task_id','outcome','confidence','assistance','criteria_passed','point_ids','novel','method_choice','changed_context','explanation_verified','error_type','error_tags','corrected_status','observation_fr','evidence']})
    require(seen==ids,'Chaque exercice doit être classé; non évalué est autorisé.')
    exit_checks=d['exit_criteria_verified'];node=c['nodes'][a['lesson_id']];require(isinstance(exit_checks,list) and len(set(exit_checks))==len(exit_checks) and all(type(i) is int and 0<=i<len(node['exit_criteria_fr']) for i in exit_checks),'Critère de sortie inconnu.')
    metrics=d.get('pilot_metrics')
    if metrics is not None:
        require(a['activity_id']=='D00' and isinstance(metrics,dict) and set(metrics)<= {'consignes_min','tentative_min','correction_min','friction_fr'} and all(type(v) is int and v>=0 for k,v in metrics.items() if k!='friction_fr') and isinstance(metrics.get('friction_fr',''),str),'Mesures pilote invalides.')
        require(sum(v for k,v in metrics.items() if k!='friction_fr')<=a['minutes'],'Durées pilote incohérentes.')
    a4=d.get('a4',[]);valid_blocks={b['id'] for m in c['lessons'].values() for b in m.get('blocks',[])}
    for x in a4:
        require(x['block_id'] in valid_blocks and type(x['priority']) is int and 0<=x['priority']<=100 and isinstance(x['reason_fr'],str) and x['reason_fr'].strip(),'Candidat A4 invalide.')
    # Only successful independent complete lesson work can release time.
    require(type(d.get('correction_reviewed')) is bool and type(d.get('anki_reviewed')) is bool,'Confirmer explicitement correction et rappel/Anki.')
    release=(a['kind']=='stage' and node['kind']=='lesson' and bool(obs) and d['correction_reviewed'] and d['anki_reviewed'] and all(o['outcome']=='correct' and o['assistance']=='none' and o['novel'] for o in obs) and any(o['method_choice'] for o in obs) and set(exit_checks)==set(range(len(node['exit_criteria_fr']))))
    # The original, evidence-checked adaptive scheduler remains the sole allocator of its review slots.
    # Generate its review only from confirmed, explicitly tagged findings with all three actual pieces.
    if a['kind']=='stage' and d.get('adaptive_review') is None:
        findings=[]
        for i,o in enumerate(sorted(obs,key=severity,reverse=True)):
            if o['outcome'] not in ('partial','incorrect') or not o['error_tags'] or '-E' not in o['task_id']:continue
            if {e['snapshot'] for e in o['evidence']}!={'first','corrected','reference'}:continue
            findings.append(dict(finding_id=f'finding-{i+1}',exercise_id=o['task_id'],error_tags=o['error_tags'],status='confirmed',corrected_status=o['corrected_status'],observation_fr=o['observation_fr'],evidence=o['evidence']))
        if findings:
            d['adaptive_review']=dict(schema_version='2.0.0',review_id='review-'+a['activity_id'].lower(),handoff_id=a['handoff_id'],reviewer=d['reviewer'],resume_after_lesson_id=a['lesson_id'],introduced_lesson_ids=sorted({h['lesson_id'] for h in s['history'] if h['kind']=='stage'}|{a['lesson_id']}),findings=findings)
    if d.get('adaptive_review') is not None:
        require(a['kind']=='stage','Une sonde utilise sa forme B, pas la banque héritée.')
        r=d['adaptive_review'];require(r['handoff_id']==a['handoff_id'],'Revue adaptative liée à une autre tentative.')
        rank={o['task_id']:severity(o) for o in obs};r=dict(r,findings=sorted(r['findings'],key=lambda f:-rank.get(f['exercise_id'],0)))
        adapt.submit_review(c['root'],ws,r)
    entry={k:a[k] for k in ('activity_id','lesson_id','kind','work_path','first_at','handoff_id','minutes')};entry.update(reviewed_at=now(),reviewer=d['reviewer'],observations=obs,exit_criteria_verified=exit_checks,release_verified=release,a4=a4,correction_reviewed=d['correction_reviewed'],anki_reviewed=d['anki_reviewed'],pilot_metrics=d.get('pilot_metrics'))
    write(ws/'reviewed'/(a['handoff_id']+'.json'),entry);s['history'].append(entry);s['active']=None;plan=save(c,ws,s)
    return dict(status='REVIEW_RECORDED',release_verified=release,budget=plan['budget'],next_stage=plan['next_stage'],optional_probes=plan['optional_probes'][:5],tableau=str(ws/'Tableau.Rmd'))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,default=ROOT/'progress');sub=p.add_subparsers(dest='cmd',required=True)
    for k in ('start','first','status'):sub.add_parser(k)
    f=sub.add_parser('finish');f.add_argument('minutes',type=int)
    r=sub.add_parser('review');r.add_argument('file',type=Path)
    q=sub.add_parser('probe');q.add_argument('id');q.add_argument('form',choices=['A','B'])
    args=p.parse_args();ws=args.workspace.resolve();c=catalog();require(ws==(ROOT/'progress').resolve() or (ws!=ROOT and not ROOT.is_relative_to(ws) and not ws.is_relative_to(ROOT)), 'Utiliser progress/ ou une session de test hors du projet.')
    ws.mkdir(parents=True,exist_ok=True);lock=ws/'.coach-lock'
    try:
        lock.mkdir()
    except FileExistsError: p.exit(2,'Une opération est déjà en cours.\n')
    try:
        s=load(c,ws)
        if args.cmd=='start':out=start(c,ws,s)
        elif args.cmd=='first':out=first(c,ws,s)
        elif args.cmd=='finish':out=finish(c,ws,s,args.minutes)
        elif args.cmd=='review':out=review(c,ws,s,read(args.file))
        elif args.cmd=='probe':out=open_probe(c,ws,s,args.id,args.form)
        else:out=save(c,ws,s)
        print(json.dumps(out,ensure_ascii=False,indent=2))
    except (ValueError,KeyError,TypeError,OSError) as e:p.exit(2,'Opération refusée : '+str(e)+'\n')
    finally:lock.rmdir()
if __name__=='__main__':main()

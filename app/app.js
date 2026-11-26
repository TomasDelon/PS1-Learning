import {emptyState,validateState,demonstrated,syntheticState,prerequisitesOf} from './state.js';

const $=id=>document.getElementById(id);
const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const statusLabels={unassessed:'Non évaluée',in_progress:'En cours',worked:'Parcourue',review_due:'À revoir',practising:'En apprentissage',demonstrated:'Démontrée'};
let curriculum,metadata,sourceManifest,realState,state,selected='D00',demoMode=false,storageKey,renderSerial=0,lastMermaid='',studyMode='work';
const message=(text,error=false)=>{$('message').textContent=text;$('message').style.color=error?'#9b3f2d':'#426f60';};
const nodeById=id=>curriculum.nodes.find(n=>n.id===id);
const skillMeta=id=>metadata.records.find(c=>c.id===id);
const lessonStatus=id=>state.lessons[id]?.status||'unassessed';
const skillStatus=id=>state.competencies[id]?.status||'unassessed';
const safeLabel=text=>String(text).replace(/["\[\]{}<>`\\\n\r]/g,' ').replace(/&/g,'et');

function save(next) {
  if(demoMode)throw new Error('La démonstration ne modifie pas votre suivi.');
  next.updated_at=new Date(Math.max(Date.now(),Date.parse(next.updated_at)||0)).toISOString();
  const checked=validateState(next,curriculum);
  localStorage.setItem(storageKey,JSON.stringify(checked));
  realState=checked;state=realState;
  message('Suivi enregistré dans ce navigateur. Exportez une copie JSON pour le conserver ailleurs.');
  refresh();
}

function download(text,name,type='application/json') {
  const url=URL.createObjectURL(new Blob([text],{type}));const a=make('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function refreshStats() {
  const worked=curriculum.nodes.filter(n=>lessonStatus(n.id)==='worked').length;
  const ids=[...new Set(curriculum.nodes.flatMap(n=>n.competency_ids))];
  const mastered=ids.filter(id=>skillStatus(id)==='demonstrated').length;
  const minutes=Object.values(state.lessons).reduce((s,x)=>s+x.minutes_spent,0);
  $('lesson-count').textContent=`${worked} / ${curriculum.nodes.length}`;$('lesson-progress').max=curriculum.nodes.length;$('lesson-progress').value=worked;
  $('skill-count').textContent=`${mastered} / ${ids.length}`;$('skill-progress').max=ids.length;$('skill-progress').value=mastered;
  $('time-count').textContent=`${minutes} min`;
  const remaining=curriculum.budget_minutes-minutes;
  $('remaining-time').textContent=remaining>=0?`${remaining} min`:`Dépassement de ${-remaining} min`;
  const reviewLessons=curriculum.nodes.filter(n=>lessonStatus(n.id)==='review_due').length;
  const reviewSkills=ids.filter(id=>skillStatus(id)==='review_due').length;
  $('review-count').textContent=reviewLessons||reviewSkills?`${reviewLessons} étape(s), ${reviewSkills} compétence(s)`:'Aucun signalement';
  refreshNavigation();
  const notice=$('state-notice');notice.classList.toggle('demo',demoMode);
  notice.textContent=demoMode?'DÉMONSTRATION SYNTHÉTIQUE. Ces données ne décrivent pas votre apprentissage. Votre suivi reste inchangé.':state.updated_at?'Suivi saisi dans ce navigateur. Les critères indiquent une preuve déclarée, pas une correction automatique de vos réponses.':'Aucune évaluation enregistrée. Les étapes et les compétences sont non évaluées.';
  $('demo').textContent=demoMode?'Quitter la démonstration':'Voir une démonstration';
  $('reset').disabled=demoMode;$('import-state').disabled=demoMode;
  document.querySelectorAll('.module-card').forEach(button=>{const nodes=curriculum.nodes.filter(n=>n.module_id===button.dataset.moduleId);button.querySelector('small').textContent=`${nodes.filter(n=>lessonStatus(n.id)==='worked').length} / ${nodes.length} étapes · ${nodes.reduce((sum,n)=>sum+n.minutes,0)} min`;button.classList.toggle('active',$('module-filter').value===button.dataset.moduleId);});
}

function refreshNavigation(){
  const current=nodeById(selected);if(!current)return;
  $('current-step').textContent=`${current.id} · ${current.minutes} min`;
  const order=[...curriculum.nodes].sort((a,b)=>a.order-b.order);
  const next=order.find(n=>n.order>current.order&&lessonStatus(n.id)!=='worked');
  const button=$('next-step');button.disabled=!next;
  button.textContent=next?`${next.id} · ${next.minutes} min`:'Fin du parcours';
  button.onclick=next?()=>choose(next.id):null;
}

function visibleNodes() {
  let nodes=curriculum.nodes;const module=$('module-filter').value;
  if(module!=='all')nodes=nodes.filter(n=>n.module_id===module);
  if($('focus-prerequisites').checked){const set=prerequisitesOf(selected,curriculum);set.add(selected);nodes=curriculum.nodes.filter(n=>set.has(n.id));}
  if($('edge-filter').value==='encompassing'){const related=new Set((curriculum.encompassing_references||[]).flatMap(r=>[r.category_lesson_id,r.member_lesson_id]));nodes=nodes.filter(n=>related.has(n.id));}
  return nodes;
}

async function renderGraph() {
  const serial=++renderSerial;
  $('graph').dataset.rendered='loading';
  const nodes=visibleNodes(),ids=new Set(nodes.map(n=>n.id)),type=$('edge-filter').value;
  const categories=[...new Map((curriculum.encompassing_references||[]).map(r=>[`${r.category_lesson_id}:${r.member_lesson_id}`,{from:r.category_lesson_id,to:r.member_lesson_id}])).values()].filter(e=>e.from!==e.to);
  const edges=(type==='encompassing'?categories:curriculum.edges.filter(e=>e.type===type)).filter(e=>ids.has(e.from)&&ids.has(e.to));
  $('graph-heading').textContent=type==='encompassing'?'Catégorie et familles comprises':type==='sequence'?'Ordre de travail':'Carte des prérequis';
  $('relation-help').textContent=type==='encompassing'?'Le choix général d’un test en L11 comprend des familles étudiées en L11-L13. La flèche pointillée va de la catégorie vers ses familles; elle n’impose pas de prérequis. Ces cinq références de thèmes sont une interprétation éditoriale du graphe hérité.':type==='sequence'?'Les flèches suivent les 23 activités dans l’ordre proposé. Cet ordre ne prouve pas qu’une compétence est acquise.':'Une flèche de prérequis indique ce qui aide à travailler l’étape suivante. Un prérequis parcouru reste distinct d’une compétence démontrée.';
  const lines=['flowchart TD'];
  for(const n of nodes){const title=n.title_fr.length>42?n.title_fr.slice(0,40)+'…':n.title_fr;lines.push(`  ${n.id}["${safeLabel(n.id+' · '+title)}"]`);}
  for(const e of edges)lines.push(type==='encompassing'?`  ${e.from} -. comprend .-> ${e.to}`:`  ${e.from} --> ${e.to}`);
  lines.push('  classDef unassessed fill:#f2f5f8,stroke:#a7b7c5,color:#294354','  classDef in_progress fill:#d9eafb,stroke:#6c9ac7,color:#244665','  classDef worked fill:#d9eee6,stroke:#6aab95,color:#265448','  classDef review_due fill:#ffead0,stroke:#d3a266,color:#76502a');
  for(const n of nodes)lines.push(`  class ${n.id} ${lessonStatus(n.id)}`);
  lastMermaid=lines.join('\n');
  if(!nodes.length){$('graph').replaceChildren(make('p','Aucune étape dans cette vue.','empty'));return;}
  try{
    const result=await window.mermaid.render(`ps1graph${serial}`,lastMermaid);
    if(serial!==renderSerial)return;
    $('graph').innerHTML=result.svg;
    const svg=$('graph').querySelector('svg');
    if(svg){const width=parseFloat(svg.getAttribute('viewBox')?.split(' ')[2]||700);svg.dataset.baseWidth=String(width);applyZoom();}
    $('graph').querySelectorAll('g.node').forEach(g=>{
      const id=nodes.find(n=>(g.id.startsWith(`flowchart-${n.id}-`)||g.id.includes(`-flowchart-${n.id}-`)))?.id;if(!id)return;
      g.setAttribute('tabindex','0');g.setAttribute('role','button');g.setAttribute('aria-label',`${id}. ${nodeById(id).title_fr}. ${statusLabels[lessonStatus(id)]}`);
      g.dataset.lessonId=id;g.classList.toggle('selected',id===selected);
      g.addEventListener('click',()=>choose(id));g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(id);}});
    });
    $('graph').dataset.rendered='true';
  }catch(error){if(serial===renderSerial){$('graph').replaceChildren(make('p',`Le graphe n’a pas pu être rendu : ${error.message}`,'error'));$('graph').dataset.rendered='false';}}
}

function applyZoom(){const svg=$('graph').querySelector('svg');if(svg){const base=Number(svg.dataset.baseWidth);svg.style.width=`${base*Number($('zoom').value)/100}px`;svg.style.height='auto';}}
function list(title,items,parent){if(!items?.length)return;parent.append(make('h3',title));const ul=make('ul');for(const item of items)ul.append(make('li',item));parent.append(ul);}
function checkbox(label,name,form){const l=make('label',undefined,'check'),input=make('input');input.type='checkbox';input.name=name;l.append(input,make('span',label));form.append(l);return input;}

function renderDetails() {
  const n=nodeById(selected),box=$('details');box.replaceChildren();if(!n)return;
  box.append(make('div',`${n.id} · ${n.minutes} MIN`,'kicker'),make('h2',n.title_fr));
  const pills=make('div',undefined,'pills');pills.append(make('span',statusLabels[lessonStatus(n.id)],'pill'),make('span',n.lesson_status==='protocol_available'?'Protocole disponible':'Deux Rmd disponibles','pill'));box.append(pills);
  box.append(make('p',n.id==='S01'?'180 min réservées à votre essai. Les fichiers contiennent uniquement le protocole et son audit; aucune épreuve ni réponse n’est chargée.':`${n.block_count||0} repères de cours · ${n.exercise_count||0} exercices · ${n.variant_count||0} variantes de rappel ou de transfert. Correction et rappel compris dans le budget.`,'milestone'));
  const moduleNodes=curriculum.nodes.filter(x=>x.module_id===n.module_id),done=moduleNodes.filter(x=>lessonStatus(x.id)==='worked').length;
  box.append(make('p',`Module : ${done} / ${moduleNodes.length} étapes parcourues`,'module-progress'));
  if(n.depends_on.length){box.append(make('h3','Prérequis'));const p=make('div',undefined,'pills');for(const id of n.depends_on){const b=make('button',`${id} · ${statusLabels[lessonStatus(id)]}`,'link-button');b.onclick=()=>choose(id);p.append(b);}box.append(p);const missing=n.depends_on.filter(id=>lessonStatus(id)!=='worked');if(missing.length)box.append(make('p','Prérequis sans étape déclarée parcourue. Cette indication ne remplace pas un diagnostic.','precheck'));}
  list('À savoir faire',n.objectives_fr,box);list('Critères de sortie',n.exit_criteria_fr,box);
  const form=make('form',undefined,'state-form');form.id='lesson-state-form';const fields=make('div',undefined,'state-fields');
  const label=make('label','État de cette étape'),select=make('select');select.name='status';for(const val of ['unassessed','in_progress','worked','review_due']){const o=make('option',statusLabels[val]);o.value=val;select.append(o);}select.value=lessonStatus(n.id);label.append(select);
  const timeLabel=make('label','Minutes utilisées'),time=make('input');time.type='number';time.min='0';time.max='1200';time.step='1';time.required=true;time.name='minutes';time.value=state.lessons[n.id]?.minutes_spent||0;timeLabel.append(time);fields.append(label,timeLabel);form.append(fields);
  const submit=make('button','Enregistrer l’étape');submit.type='submit';submit.disabled=demoMode;form.append(submit,make('small',' Le statut « Parcourue » ne valide aucune compétence.'));
  form.onsubmit=e=>{e.preventDefault();try{const next=structuredClone(realState);next.lessons[n.id]={status:select.value,minutes_spent:Number(time.value),updated_at:new Date().toISOString()};save(next);}catch(err){message(err.message,true);}};box.append(form);
  if(n.work_path){box.append(make('h3','Documents RStudio'));const files=make('div',undefined,'lesson-files');
    const modeLabel=make('label','Mode de travail'),mode=make('select');mode.id='study-mode';for(const [value,label] of [['work','Cours et exercices'],['review','Rappel et transfert']]){const option=make('option',label);option.value=value;mode.append(option);}mode.value=studyMode;modeLabel.append(mode);files.append(modeLabel);
    const modeNote=make('p',undefined,'milestone');modeNote.id='mode-guidance';
    const describeMode=()=>{studyMode=mode.value;modeNote.textContent=n.id==='S01'?'Le protocole seul est disponible. Une épreuve réelle ne commence que sur votre décision.':studyMode==='review'?'Choisir une variante non consultée selon une erreur observée. Elle remplace un créneau de rappel ou de F01; elle ne s’ajoute pas au budget.':'Ouvrir le Rmd de travail dans RStudio, sélectionner Visual et exécuter les chunks au fil de la tentative. Conserver les premières réponses.';};mode.onchange=describeMode;describeMode();files.append(modeNote);
    const work=make('a',n.id==='S01'?'Télécharger le protocole Rmd':'Télécharger le Rmd de travail','button');work.id='work-link';work.href='../'+n.work_path;work.download='';files.append(work);
    if(n.correction_path){const checkLabel=make('label',undefined,'attempt-check'),check=make('input');check.type='checkbox';check.id='attempted-check';checkLabel.append(check,make('span',n.id==='S01'?'Je souhaite consulter l’audit du protocole.':'J’ai conservé ma première tentative et souhaite consulter le corrigé.'));files.append(checkLabel);const correction=make('a',n.id==='S01'?'Télécharger l’audit du protocole':'Télécharger le corrigé séparé','button');correction.id='correction-link';correction.download='';correction.setAttribute('aria-disabled','true');correction.tabIndex=-1;correction.style.opacity='.45';check.onchange=()=>{if(check.checked){correction.href='../'+n.correction_path;correction.removeAttribute('aria-disabled');correction.tabIndex=0;correction.style.opacity='1';}else{correction.removeAttribute('href');correction.setAttribute('aria-disabled','true');correction.tabIndex=-1;correction.style.opacity='.45';}};files.append(correction);}box.append(files);
  } else box.append(make('p','Le fichier de cette étape sera produit à partir des modèles. Aucun corrigé n’est chargé ici.','milestone'));
  const firstPractice=(n.first_practice_competency_ids||[]).filter(id=>!n.competency_ids.includes(id));
  if(firstPractice.length){box.append(make('h3','Premières applications'));const ul=make('ul',undefined,'practice-list');for(const id of firstPractice){const li=make('li',skillMeta(id)?.label_fr||id);const owner=curriculum.nodes.find(x=>x.competency_ids.includes(id));if(owner){const b=make('button',`Vérification complète : ${owner.id}`,'link-button');b.onclick=()=>choose(owner.id);li.append(make('br'),b);}ul.append(li);}box.append(ul,make('p','Une première application guidée ne valide pas toute la compétence.','milestone'));}
  if(n.competency_ids.length){box.append(make('h3',`Compétences à vérifier ici · ${n.competency_ids.length}`),make('p','Les preuves sont déclarées après correction de votre travail. Les critères ne jugent pas automatiquement vos mathématiques.','milestone'));for(const id of n.competency_ids)box.append(competencyControl(id));}
  if(n.source_refs?.length){box.append(make('h3','Sources de cette étape'));const ul=make('ul',undefined,'source-list');for(const s of n.source_refs){const li=make('li');const source=sourceManifest.sources.find(x=>x.source_id===s.source_id);if(source?.package_path){const a=make('a',s.source_id);a.href='../'+source.package_path;a.target='_blank';a.rel='noopener';li.append(a);}else li.append(make('span',s.source_id));li.append(document.createTextNode(` · ${s.locator}${s.purpose?' · '+s.purpose:''}`));ul.append(li);}box.append(ul);}
}

function competencyControl(id) {
  const c=skillMeta(id),record=state.competencies[id]||{status:'unassessed',evidence:[]};
  const details=make('details',undefined,'competency');details.dataset.competencyId=id;
  details.append(make('summary',c?.label_fr||id),make('div',statusLabels[record.status],'skill-status'),make('code',id));
  const checks=c?.rubric?.observable_checks_fr||[];if(checks.length){const ul=make('ul');for(const t of checks)ul.append(make('li',t));details.append(ul);}
  if(record.evidence.length){const ul=make('ul',undefined,'evidence-list');for(const e of record.evidence)ul.append(make('li',`${e.exercise_ref} · ${e.date.slice(0,16).replace('T',' ')} · ${e.independent&&e.correct?'réussite autonome':'travail à reprendre'}${e.changed_context?' · transfert':''}${e.delayed_mixed?' · rappel différé':''}`));details.append(ul);}
  const form=make('form',undefined,'evidence-form');const refLabel=make('label','Référence de votre exercice'),ref=make('input');ref.name='exercise_ref';ref.required=true;ref.maxLength=200;ref.placeholder='Ex. L04-E03, tentative 1';refLabel.append(ref);form.append(refLabel);
  const independent=checkbox('Résolu sans aide ni correction consultée','independent',form),correct=checkbox('Calcul et justification corrects après vérification','correct',form),changed=checkbox('Application dans un contexte différent','changed_context',form),delayed=checkbox('Rappel différé, mélangé à d’autres notions','delayed_mixed',form);
  const noteLabel=make('label','Observation ou erreur à retravailler'),note=make('textarea');note.name='note';note.maxLength=1000;noteLabel.append(note);form.append(noteLabel);
  const submit=make('button','Ajouter cette preuve');submit.type='submit';submit.disabled=demoMode;form.append(submit);form.onsubmit=e=>{e.preventDefault();try{const next=structuredClone(realState);const previous=next.competencies[id]?.evidence||[];const evidence=[...previous,{id:crypto.randomUUID(),date:new Date().toISOString(),exercise_ref:ref.value.trim(),independent:independent.checked,correct:correct.checked,changed_context:changed.checked,delayed_mixed:delayed.checked,note:note.value.trim()}];const status=!correct.checked?'review_due':demonstrated(evidence)?'demonstrated':'practising';next.competencies[id]={status,evidence};save(next);}catch(err){message(err.message,true);}};details.append(form);
  if(record.evidence.length){const review=make('button','Marquer à revoir','quiet');review.disabled=demoMode;review.onclick=()=>{try{const next=structuredClone(realState);next.competencies[id].status='review_due';save(next);}catch(err){message(err.message,true);}};details.append(review);}
  details.append(make('small','Le statut « Démontrée » exige au moins deux exercices distincts réussis sans aide, dont un transfert et un rappel différé après une première preuve.'));return details;
}

function choose(id){if(!nodeById(id))return;selected=id;$('lesson-select').value=id;refreshNavigation();renderDetails();if($('focus-prerequisites').checked)renderGraph();else $('graph').querySelectorAll('g.node').forEach(g=>g.classList.toggle('selected',g.dataset.lessonId===id));}
function refresh(){refreshStats();renderDetails();renderGraph();}

async function start() {
  const [c,m,sm]=await Promise.all([fetch('../data/curriculum.json'),fetch('../data/reference_catalog.json'),fetch('../data/source_manifest.json')]);if(!c.ok||!m.ok||!sm.ok)throw new Error('Fichiers du parcours indisponibles. Démarrez tools/serve.py depuis le dossier extrait.');curriculum=await c.json();metadata=await m.json();metadata.records=metadata.competencies;sourceManifest=await sm.json();
  if(!Array.isArray(curriculum.nodes)||!Array.isArray(curriculum.edges)||curriculum.nodes.length===0)throw new Error('Parcours invalide.');
  storageKey=`ps1.progress.${curriculum.curriculum_id}.${curriculum.version}`;realState=emptyState(curriculum);
  const stored=localStorage.getItem(storageKey);if(stored){try{realState=validateState(JSON.parse(stored),curriculum);}catch(e){message(`Le suivi local existant n’a pas été chargé ni effacé : ${e.message}`,true);}}
  state=realState;selected=curriculum.nodes.slice().sort((a,b)=>a.order-b.order)[0].id;
  const modules=curriculum.modules||[...new Set(curriculum.nodes.map(n=>n.module_id))].map(id=>({id,title_fr:id}));for(const mod of modules){const o=make('option',mod.title_fr);o.value=mod.id;$('module-filter').append(o);const b=make('button',undefined,'module-card');b.dataset.moduleId=mod.id;b.append(make('strong',mod.title_fr),make('small',''));b.onclick=()=>{$('module-filter').value=mod.id;$('focus-prerequisites').checked=false;choose(curriculum.nodes.filter(n=>n.module_id===mod.id).sort((a,b)=>a.order-b.order)[0].id);refreshStats();renderGraph();};$('module-overview').append(b);}
  for(const n of [...curriculum.nodes].sort((a,b)=>a.order-b.order)){const o=make('option',`${n.id} · ${n.title_fr}`);o.value=n.id;$('lesson-select').append(o);}
  $('lesson-select').value=selected;$('lesson-select').onchange=e=>choose(e.target.value);
  $('module-filter').onchange=()=>{refreshStats();renderGraph();};$('edge-filter').onchange=()=>{const category=$('edge-filter').value==='encompassing';$('focus-prerequisites').disabled=category;if(category)$('focus-prerequisites').checked=false;renderGraph();};$('focus-prerequisites').onchange=renderGraph;$('zoom').oninput=applyZoom;
  $('download-mermaid').onclick=()=>download(lastMermaid+'\n','PS1_parcours.mmd','text/plain');
  $('export-state').onclick=()=>download(JSON.stringify(state,null,2)+'\n',demoMode?'PS1_suivi_DEMO.json':'PS1_suivi.json');
  $('import-state').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{if(f.size>1000000)throw new Error('Fichier trop volumineux, limite 1 Mo.');const next=validateState(JSON.parse(await f.text()),curriculum);if(!confirm('Remplacer le suivi de ce navigateur par ce fichier ? Exportez votre suivi actuel si nécessaire.'))return;save(next);}catch(err){message(`Import refusé : ${err.message}`,true);}finally{e.target.value='';}};
  $('demo').onclick=()=>{demoMode=!demoMode;state=demoMode?syntheticState(curriculum):realState;message('');refresh();};
  $('reset').onclick=()=>{if(confirm('Effacer uniquement le suivi PS1 de ce navigateur ? Les fichiers et vos exports restent inchangés.')){localStorage.removeItem(storageKey);realState=emptyState(curriculum);state=realState;message('Suivi local effacé.');refresh();}};
  if(!window.mermaid)throw new Error('Le moteur Mermaid local est absent. Conservez le dossier app/vendor.');
  window.mermaid.initialize({startOnLoad:false,securityLevel:'strict',htmlLabels:false,theme:'base',fontFamily:'system-ui, sans-serif',flowchart:{htmlLabels:false,curve:'basis',useMaxWidth:false,nodeSpacing:30,rankSpacing:42},themeVariables:{primaryColor:'#f2f5f8',lineColor:'#a0b4c4',fontSize:'13px'}});
  refresh();document.body.dataset.ready='true';
}

start().catch(e=>{$('state-notice').textContent=e.message;$('state-notice').classList.add('error');message('Ouvrez http://127.0.0.1:8765/app/ après avoir lancé python3 tools/serve.py.',true);document.body.dataset.ready='error';});

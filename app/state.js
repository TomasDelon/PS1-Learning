export const LESSON_STATUS = Object.freeze(['unassessed','in_progress','worked','review_due']);
export const SKILL_STATUS = Object.freeze(['unassessed','practising','demonstrated','review_due']);
const plain = value => value !== null && typeof value === 'object' && !Array.isArray(value) && Object.getPrototypeOf(value) === Object.prototype;
const fail = message => { throw new Error(message); };
const bounded = (value, max, name) => typeof value === 'string' && value.length <= max ? value : fail(`${name} invalide.`);
export const CLOCK_SKEW_MS = 60_000;
// Calendar-valid ISO timestamps, explicit timezone, at most millisecond precision.
function timestamp(value) {
  if (typeof value !== 'string') return NaN;
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?(Z|([+-])(\d{2}):(\d{2}))$/.exec(value);
  if (!match) return NaN;
  const [, ys, ms, ds, hs, mins, ss, , zone, , ohs, oms] = match;
  const [year, month, day, hour, minute, second] = [ys, ms, ds, hs, mins, ss].map(Number);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > days[month - 1] || hour > 23 || minute > 59 || second > 59) return NaN;
  if (zone !== 'Z') {
    const offsetHours = Number(ohs), offsetMinutes = Number(oms);
    if (offsetHours > 14 || offsetMinutes > 59 || (offsetHours === 14 && offsetMinutes !== 0)) return NaN;
  }
  return Date.parse(value);
}
const only = (value, allowed, name) => { for (const key of Object.keys(value)) if (!allowed.includes(key)) fail(`Champ inconnu dans ${name} : ${key}.`); };

export function emptyState(curriculum, isDemo = false) {
  return {schema_version:'1.0.0', curriculum_id:curriculum.curriculum_id, curriculum_version:curriculum.version, is_demo:isDemo, updated_at:null, lessons:{}, competencies:{}};
}

export function demonstrated(evidence) {
  const lastFailure = Math.max(-Infinity, ...evidence.filter(e => !e.correct).map(e => Date.parse(e.date)));
  const successful = evidence.filter(e => e.independent && e.correct && Date.parse(e.date) > lastFailure);
  const distinct = new Set(successful.map(e => e.exercise_ref.trim()));
  return distinct.size >= 2 && successful.some(e => e.changed_context) && successful.some(e => e.delayed_mixed && successful.some(first => first.id !== e.id && Date.parse(first.date) < Date.parse(e.date)));
}

export function validateState(candidate, curriculum, {allowDemo = false, now = Date.now()} = {}) {
  if (!Number.isFinite(now)) fail('Horloge de validation invalide.');
  if (!plain(candidate)) fail('Le fichier doit contenir un objet JSON.');
  only(candidate, ['schema_version','curriculum_id','curriculum_version','is_demo','updated_at','lessons','competencies'], 'le suivi');
  if (candidate.schema_version !== '1.0.0') fail('Version de suivi incompatible.');
  if (candidate.curriculum_id !== curriculum.curriculum_id || candidate.curriculum_version !== curriculum.version) fail('Ce suivi appartient à une autre version du parcours.');
  if (typeof candidate.is_demo !== 'boolean' || (candidate.is_demo && !allowDemo)) fail('Un exemple synthétique ne peut pas remplacer votre suivi.');
  const updated = candidate.updated_at === null ? null : timestamp(candidate.updated_at);
  if (updated !== null && !Number.isFinite(updated)) fail('Date de mise à jour invalide.');
  if (updated !== null && updated > now + CLOCK_SKEW_MS) fail('Date de mise à jour future.');
  const nestedTime = (value, label) => {
    const parsed = timestamp(value);
    if (!Number.isFinite(parsed)) fail(`Date ${label} invalide.`);
    if (parsed > now + CLOCK_SKEW_MS) fail(`Date ${label} future.`);
    if (updated === null || parsed > updated) fail(`Date ${label} postérieure à la mise à jour du suivi.`);
  };
  if (!plain(candidate.lessons) || !plain(candidate.competencies)) fail('Les étapes et compétences doivent être des objets.');
  const nodeIds = new Set(curriculum.nodes.map(n => n.id));
  const skillIds = new Set(curriculum.nodes.flatMap(n => n.competency_ids));
  for (const [id, value] of Object.entries(candidate.lessons)) {
    if (!nodeIds.has(id)) fail(`Étape inconnue : ${id}.`);
    if (!plain(value)) fail(`État invalide : ${id}.`);
    only(value, ['status','minutes_spent','updated_at'], id);
    if (!LESSON_STATUS.includes(value.status)) fail(`Statut d’étape invalide : ${id}.`);
    if (!Number.isInteger(value.minutes_spent) || value.minutes_spent < 0 || value.minutes_spent > 1200) fail(`Temps invalide : ${id}.`);
    nestedTime(value.updated_at, `de l’étape ${id}`);
  }
  if (Object.values(candidate.lessons).reduce((n,x) => n+x.minutes_spent,0) > 10000) fail('Temps total incohérent.');
  let totalEvidence = 0;
  for (const [id, value] of Object.entries(candidate.competencies)) {
    if (!skillIds.has(id)) fail(`Compétence inconnue : ${id}.`);
    if (!plain(value)) fail(`État de compétence invalide : ${id}.`);
    only(value, ['status','evidence'], id);
    if (!SKILL_STATUS.includes(value.status)) fail(`Statut de compétence invalide : ${id}.`);
    if (!Array.isArray(value.evidence) || value.evidence.length > 200) fail(`Preuves invalides : ${id}.`);
    totalEvidence += value.evidence.length;
    const seen = new Set();
    for (const item of value.evidence) {
      if (!plain(item)) fail(`Preuve invalide : ${id}.`);
      only(item, ['id','date','exercise_ref','independent','correct','changed_context','delayed_mixed','note'], 'la preuve');
      bounded(item.id, 100, 'Identifiant de preuve');
      bounded(item.exercise_ref, 200, 'Référence d’exercice');
      bounded(item.note, 1000, 'Commentaire');
      if (!item.id || !item.exercise_ref.trim() || seen.has(item.id)) fail('Référence vide ou identifiant de preuve dupliqué.');
      seen.add(item.id);
      nestedTime(item.date, 'de preuve');
      for (const name of ['independent','correct','changed_context','delayed_mixed']) if (typeof item[name] !== 'boolean') fail(`Champ ${name} invalide.`);
    }
    if (value.status === 'demonstrated' && !demonstrated(value.evidence)) fail(`Preuves insuffisantes pour déclarer la compétence démontrée : ${id}.`);
    if (value.status === 'unassessed' && value.evidence.length) fail(`État non évalué incohérent avec des preuves : ${id}.`);
  }
  if (totalEvidence > 2000) fail('Le suivi contient trop de preuves.');
  return JSON.parse(JSON.stringify(candidate));
}

export function prerequisitesOf(id, curriculum) {
  const byId = new Map(curriculum.nodes.map(n => [n.id,n]));
  const result = new Set();
  const visit = current => { for (const dep of byId.get(current)?.depends_on || []) if (!result.has(dep)) { result.add(dep); visit(dep); } };
  visit(id); result.delete(id); return result;
}

export function syntheticState(curriculum, {now = Date.now()} = {}) {
  if (!Number.isFinite(now)) fail('Horloge de démonstration invalide.');
  const state = emptyState(curriculum,true);
  const stamp = new Date(now).toISOString();
  const firstStamp = new Date(now - 26 * 60 * 60 * 1000).toISOString();
  const recallStamp = new Date(now - 60 * 1000).toISOString();
  state.updated_at=stamp;
  for (const id of ['D00','L01','L02']) if (curriculum.nodes.some(n=>n.id===id)) state.lessons[id]={status:'worked',minutes_spent:15,updated_at:stamp};
  if (curriculum.nodes.some(n=>n.id==='L04')) state.lessons.L04={status:'review_due',minutes_spent:20,updated_at:stamp};
  const skill=curriculum.nodes.find(n=>n.id==='L04')?.competency_ids?.[0] || curriculum.nodes.flatMap(n=>n.competency_ids)[0];
  if (skill) state.competencies[skill]={status:'demonstrated',evidence:[{id:'DEMO-1',date:firstStamp,exercise_ref:'EXEMPLE SYNTHÉTIQUE A',independent:true,correct:true,changed_context:false,delayed_mixed:false,note:'Donnée de démonstration, aucune réponse réelle.'},{id:'DEMO-2',date:recallStamp,exercise_ref:'EXEMPLE SYNTHÉTIQUE B',independent:true,correct:true,changed_context:true,delayed_mixed:true,note:'Donnée de démonstration, aucune réponse réelle.'}]};
  return validateState(state,curriculum,{allowDemo:true,now});
}

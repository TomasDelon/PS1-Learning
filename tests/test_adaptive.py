"""Disposable fixtures only: no project learner/session directories are used."""
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ps1_adapt", PROJECT/"tools/adapt.py")
adapt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapt)
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jT4sAAAAASUVORK5CYII=")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def rmd(lid, role):
    bid = lid+"-B01"
    eid = lid+"-E01"
    block_ids = '["'+bid+'"]' if role == "work" else "[]"
    text = ("---\ntitle: "+lid+"\noutput: html_notebook\nps1:\n"
            "  template_version: '1.0.0'\n  lesson_id: "+lid+"\n  document_role: "+role+"\n"
            "  content_status: authored_complete\n  minutes: 20\n"
            "  exercise_ids: [\""+eid+"\"]\n  block_ids: "+block_ids+"\n"
            "  learner_state: not_created\n---\n\n")
    if role == "work":
        text += "## 1/6 · Cours\n\n### Bloc {#"+bid+"}\n\n> **THM ["+bid+"] · Variance**\n>\n> Une variable de carré intégrable a une variance finie.\n\n"
        text += "## 2/6 · Comprendre\n\n## 3/6 · Résoudre\n\n### Exercice {#"+eid+"}\n\nJustifier la variance d'une transformation.\n\n"
        text += "## 4/6 · R\n\n## 5/6 · Corriger\n\nConserver la première tentative.\n\n"
        text += "## 6/6 · Rappel\n\nSix minutes de correction et rappel, déjà incluses.\n\n## Références\n\nSource synthétique du test.\n"
    else:
        text += "### Correction {#"+eid+"}\n\n<!-- ps1:solution id="+eid+" -->\n\nLa translation ne change pas la variance.\n"
    return text


class AdaptiveTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="ps1-adaptive-fixture-"))
        self.root = self.temp/"package"
        self.ws = self.temp/"session"
        nodes = []
        for i in range(1, 6):
            lid = f"L{i:02d}"
            nodes.append(dict(id=lid, kind="lesson", order=i, minutes=20,
                              depends_on=[] if i==1 else [f"L{i-1:02d}"],
                              time_breakdown=dict(cours=3, exercices=11, self_correction_review=6)))
            folder = self.root/"lessons"/lid
            folder.mkdir(parents=True)
            (folder/(lid+"_Travail.Rmd")).write_text(rmd(lid,"work"))
            (folder/(lid+"_Corrige.Rmd")).write_text(rmd(lid,"correction"))
            (folder/"data").mkdir()
            (folder/"data/fixture.csv").write_text("x\n2\n4\n")
            meta = dict(lesson_id=lid, minutes=20,
                review_allocation=dict(correction_minutes=2,anki_minutes=1),
                blocks=[dict(id=lid+"-B01"),dict(id=lid+"-B02")],
                exercises=[dict(id=lid+"-E01",block_ids=[lid+"-B01",lid+"-B02"],
                                error_tags=["independence"],rubric_fr=["Justifier."])],
                variants=[
                  dict(id=lid+"-V01",family="variance_translation",for_exercise_ids=[lid+"-E01"],
                       error_tags=["independence"],block_ids=[lid+"-B01"],minutes=3,has_r=False,
                       prompt_md="Comparer la variance de X et celle de X+3, sous une hypothèse explicite.",
                       correction_md="La variance est inchangée pour X de carré intégrable.",
                       rubric_fr=["Nommer le carré intégrable.","Justifier la translation."],
                       transfer="Reconnaître une translation dans une unité différente."),
                  dict(id=lid+"-V02",family="shared_noise",for_exercise_ids=[lid+"-E01"],
                       error_tags=["method_choice"],block_ids=[lid+"-B02"],minutes=3,has_r=False,
                       prompt_md="Y=-X. Peut-on additionner les variances de X et Y pour calculer celle de leur somme ?",
                       correction_md="La somme est nulle. La covariance ne peut pas être omise.",
                       rubric_fr=["Identifier la dépendance.","Justifier la somme constante."],
                       transfer="Décider que l'addition sous indépendance n'est plus applicable.")])
            write_json(folder/"lesson.json",meta)
        write_json(self.root/"data/curriculum.json",dict(budget_minutes=100,nodes=nodes))
        self.first = self.temp/"answers/first/L01_Travail.Rmd"
        self.corrected = self.temp/"answers/corrected/L01_Travail.Rmd"
        for p, suffix in [(self.first,b"first"),(self.corrected,b"corrected")]:
            p.parent.mkdir(parents=True)
            p.write_text(rmd("L01","work")+"\n![Photo de test](images/reponse.png)\n")
            (p.parent/"images").mkdir()
            (p.parent/"images/reponse.png").write_bytes(PNG+suffix)
        self.reference = self.root/"lessons/L01/L01_Corrige.Rmd"

    def tearDown(self):
        for p in self.temp.rglob("*"):
            try:
                p.chmod(0o755 if p.is_dir() else 0o644)
            except FileNotFoundError:
                pass
        shutil.rmtree(self.temp)

    def capture(self):
        return adapt.capture_handoff(self.root,self.ws,"attempt-a","L01",self.first,self.corrected,self.reference)

    def review(self, image_uncertain=False, rid="review-a"):
        hp,h=adapt._handoff(self.ws,"attempt-a")
        evidence=[]
        for role in ["first","corrected","reference"]:
            m=h["snapshots"][role]
            path="images/reponse.png" if role=="first" and image_uncertain else m["document"]
            entry=next(x for x in m["files"] if x["path"]==path)
            evidence.append(dict(snapshot=role,path=path,sha256=entry["sha256"],
                                 medium="image" if role=="first" and image_uncertain else "text",
                                 certainty="uncertain" if role=="first" and image_uncertain else "confirmed",
                                 visually_reviewed=False,locator_fr="Exercice L01-E01, justification."))
        return dict(schema_version="2.0.0",review_id=rid,handoff_id="attempt-a",reviewer="human",
                    resume_after_lesson_id="L01",introduced_lesson_ids=["L01"],
                    findings=[dict(finding_id="finding-a",exercise_id="L01-E01",error_tags=["independence"],
                                   status="confirmed",corrected_status="self_corrected",
                                   observation_fr="L'autocorrection est présente; une vérification autonome reste requise.",
                                   evidence=evidence)])

    def test_capture_preserves_all_images_and_originals(self):
        before=self.first.read_bytes()
        result=self.capture()
        hp,h=adapt._handoff(self.ws,"attempt-a")
        self.assertEqual(result["images"],2)
        self.assertEqual((hp/"snapshots/first/images/reponse.png").read_bytes(),PNG+b"first")
        self.assertEqual((hp/"snapshots/corrected/images/reponse.png").read_bytes(),PNG+b"corrected")
        self.assertEqual(self.first.read_bytes(),before)
        self.assertEqual(h["status"],"AWAITING_REVIEW")
        self.assertFalse(h["automatic_image_grading"])

    def test_missing_image_rolls_back_whole_capture(self):
        (self.corrected.parent/"images/reponse.png").unlink()
        with self.assertRaises(ValueError):
            self.capture()
        self.assertFalse((self.ws/"handoffs/attempt-a").exists())
        self.assertEqual(list(self.ws.glob(".capture-*")),[])

    def test_unsafe_handoff_id_refused(self):
        for bad in ["../overwrite","/tmp/bad","bad/name","a b","A01",""]:
            with self.assertRaises(adapt.AdaptiveError):
                adapt.capture_handoff(self.root,self.ws,bad,"L01",self.first,self.corrected,self.reference)

    def test_canonical_directory_refused_as_workspace(self):
        with self.assertRaises(adapt.AdaptiveError):
            adapt.capture_handoff(self.root,self.root/"lessons/runtime","attempt-a","L01",self.first,self.corrected,self.reference)

    def test_duplicate_attempt_and_review_are_not_recreated(self):
        self.capture()
        with self.assertRaises(adapt.AdaptiveError):
            self.capture()
        with self.assertRaises(adapt.AdaptiveError):
            adapt.capture_handoff(self.root,self.ws,"another-id","L01",self.first,self.corrected,self.reference)
        r=self.review()
        adapt.submit_review(self.root,self.ws,r)
        result=adapt.submit_review(self.root,self.ws,r)
        self.assertEqual(result["status"],"ALREADY_RECORDED")
        self.assertEqual(len(list((self.ws/"reviews").glob("*.json"))),1)
        r2=copy.deepcopy(r);r2["findings"][0]["observation_fr"]="Autre contenu."
        with self.assertRaises(adapt.AdaptiveError):
            adapt.submit_review(self.root,self.ws,r2)

    def test_uncertain_image_stays_blocked(self):
        self.capture()
        result=adapt.submit_review(self.root,self.ws,self.review(True))
        self.assertEqual(result["plan"]["findings"][0]["status"],"NEEDS_CLARIFICATION")
        self.assertEqual(result["plan"]["tasks"],[])

    def test_image_not_visually_reviewed_cannot_be_confirmed(self):
        self.capture()
        r=self.review(True);r["findings"][0]["evidence"][0]["certainty"]="confirmed"
        result=adapt.submit_review(self.root,self.ws,r)
        self.assertEqual(result["plan"]["findings"][0]["status"],"NEEDS_CLARIFICATION")

    def test_bad_evidence_hash_or_unknown_exercise_refused(self):
        self.capture()
        r=self.review();r["findings"][0]["evidence"][0]["sha256"]="0"*64
        with self.assertRaises(adapt.AdaptiveError):
            adapt.submit_review(self.root,self.ws,r)
        r=self.review();r["findings"][0]["exercise_id"]="L99-E01"
        with self.assertRaises(adapt.AdaptiveError):
            adapt.submit_review(self.root,self.ws,r)
        self.assertFalse((self.ws/"reviews").exists())

    def test_tampered_snapshot_refused(self):
        self.capture()
        p=self.ws/"handoffs/attempt-a/snapshots/first/images/reponse.png"
        p.chmod(0o644);p.write_bytes(PNG+b"changed")
        with self.assertRaises(adapt.AdaptiveError):
            adapt.submit_review(self.root,self.ws,self.review())

    def test_pending_base_then_versioned_patch_preserves_budget_and_assets(self):
        self.capture()
        original=(self.root/"lessons/L02/L02_Travail.Rmd").read_bytes()
        base=adapt.prepare_next(self.root,self.ws,"L02",[self.first])
        self.assertEqual(base["status"],"BASE_READY_REVIEW_PENDING")
        base_bytes=Path(base["work"]).read_bytes()
        adapt.submit_review(self.root,self.ws,self.review())
        patched=adapt.prepare_next(self.root,self.ws,"L02",[self.first])
        self.assertEqual(patched["status"],"REVIEW_INSERTED")
        self.assertNotEqual(base["generation_id"],patched["generation_id"])
        self.assertEqual(Path(base["work"]).read_bytes(),base_bytes)
        self.assertEqual((self.root/"lessons/L02/L02_Travail.Rmd").read_bytes(),original)
        self.assertEqual(patched["allocation"],dict(total_lesson_minutes=20,original_review_minutes=6,
                         protected_current_review_minutes=3,replaceable_review_minutes=3,
                         inserted_review_minutes=3,remaining_review_minutes=3,
                         remaining_discretionary_minutes=0,added_minutes=0,
                         policy_source="explicit_current_correction_and_anki"))
        self.assertIn("{#L01-V01}",Path(patched["work"]).read_text())
        self.assertNotIn("La variance est inchangée",Path(patched["work"]).read_text())
        self.assertIn("La variance est inchangée",Path(patched["correction"]).read_text())
        self.assertTrue((Path(patched["path"])/"data/fixture.csv").is_file())
        self.assertEqual(Path(patched["work"]).read_text().split("---",2)[1],
                         original.decode().split("---",2)[1])
        again=adapt.prepare_next(self.root,self.ws,"L02",[self.first])
        self.assertEqual(again["status"],"ALREADY_PREPARED")

    def test_active_lesson_and_earlier_target_refused(self):
        active=self.root/"lessons/L02/L02_Travail.Rmd"
        for target in ["L01","L02"]:
            with self.assertRaises(adapt.AdaptiveError):
                adapt.prepare_next(self.root,self.ws,target,[active])
        with self.assertRaises(adapt.AdaptiveError):
            adapt.prepare_next(self.root,self.ws,"L03",[])

    def test_nonadjacent_transfer_and_self_correction_not_mastery(self):
        self.capture()
        p=adapt.submit_review(self.root,self.ws,self.review())["plan"]
        tasks={x["stage"]:x for x in p["tasks"]}
        self.assertEqual(tasks["repair"]["scheduled_lesson_id"],"L02")
        self.assertEqual(tasks["delayed_transfer"]["scheduled_lesson_id"],"L04")
        self.assertNotEqual(tasks["repair"]["variant_id"],tasks["delayed_transfer"]["variant_id"])
        self.assertEqual(p["findings"][0]["status"],"TRANSFER_PENDING")
        self.assertFalse(p["learner_mastery_changed"])

    def test_missing_prerequisite_is_not_assumed(self):
        m=json.loads((self.root/"lessons/L01/lesson.json").read_text())
        for variant in m["variants"]:
            variant["block_ids"].append("L03-B01")
        write_json(self.root/"lessons/L01/lesson.json",m)
        self.capture()
        p=adapt.submit_review(self.root,self.ws,self.review())["plan"]
        self.assertEqual(p["findings"][0]["status"],"PREREQUISITE_CONFIRMATION_REQUIRED")
        self.assertIn("L03",p["findings"][0]["missing_prerequisites"])

    def test_ready_repair_is_not_blocked_by_a_future_transfer_prerequisite(self):
        m=json.loads((self.root/"lessons/L01/lesson.json").read_text())
        m["variants"][0]["block_ids"].append("L03-B01")
        write_json(self.root/"lessons/L01/lesson.json",m)
        self.capture()
        plan=adapt.submit_review(self.root,self.ws,self.review())["plan"]
        self.assertEqual(plan["tasks"][0]["variant_id"],"L01-V02")
        self.assertEqual(plan["findings"][0]["status"],"TRANSFER_PREREQUISITE_CONFIRMATION_REQUIRED")

    def test_shared_blocks_do_not_create_unreviewed_targeted_links(self):
        p=self.root/"lessons/L01/lesson.json"
        meta=json.loads(p.read_text())
        for variant in meta["variants"]:
            variant["for_exercise_ids"]=[]
            variant["error_tags"]=["independence"]
        write_json(p,meta)
        self.capture()
        plan=adapt.submit_review(self.root,self.ws,self.review())["plan"]
        self.assertEqual(plan["findings"][0]["status"],"AUTHORED_VARIANT_REQUIRED")
        self.assertEqual(plan["tasks"],[])

    def test_no_review_capacity_never_adds_minutes(self):
        c=json.loads((self.root/"data/curriculum.json").read_text())
        for n in c["nodes"]:
            n["time_breakdown"]["self_correction_review"]=2
        write_json(self.root/"data/curriculum.json",c)
        self.capture()
        p=adapt.submit_review(self.root,self.ws,self.review())["plan"]
        self.assertEqual(p["findings"][0]["status"],"NO_SUITABLE_SLOT")
        self.assertEqual(p["review_minutes_reserved"],{})

    def test_late_review_moves_to_next_future_slot(self):
        self.capture()
        r=self.review();r["resume_after_lesson_id"]="L02"
        p=adapt.submit_review(self.root,self.ws,r)["plan"]
        by_stage={t["stage"]:t for t in p["tasks"]}
        self.assertEqual(by_stage["repair"]["scheduled_lesson_id"],"L03")
        self.assertEqual(by_stage["delayed_transfer"]["scheduled_lesson_id"],"L05")

    def test_failed_plan_does_not_commit_an_unusable_review(self):
        self.capture()
        path=self.root/"lessons/L01/lesson.json"
        m=json.loads(path.read_text())
        m["variants"][0]["block_ids"]=["L99-B01"]
        write_json(path,m)
        with self.assertRaises(adapt.AdaptiveError):
            adapt.submit_review(self.root,self.ws,self.review())
        self.assertEqual(list((self.ws/"reviews").glob("*.json")),[])

    def test_shared_variant_is_inserted_once_for_two_findings(self):
        self.capture()
        review=self.review()
        other=copy.deepcopy(review["findings"][0])
        other["finding_id"]="finding-b"
        other["error_tags"]=["independence","formal_language"]
        review["findings"].append(other)
        plan=adapt.submit_review(self.root,self.ws,review)["plan"]
        self.assertEqual(len(plan["findings"]),2)
        self.assertEqual(len(plan["tasks"]),2)
        self.assertEqual(plan["review_minutes_reserved"],{"L02":3,"L04":3})
        out=adapt.prepare_next(self.root,self.ws,"L02",[self.first])
        self.assertEqual(Path(out["work"]).read_text().count("{#L01-V01}"),1)

    def test_changed_authored_variant_creates_new_version(self):
        self.capture()
        adapt.submit_review(self.root,self.ws,self.review())
        first=adapt.prepare_next(self.root,self.ws,"L02",[self.first])
        saved=Path(first["work"]).read_bytes()
        path=self.root/"lessons/L01/lesson.json"
        m=json.loads(path.read_text())
        m["variants"][0]["prompt_md"] += " Donner une justification en français."
        write_json(path,m)
        second=adapt.prepare_next(self.root,self.ws,"L02",[self.first])
        self.assertNotEqual(first["generation_id"],second["generation_id"])
        self.assertEqual(Path(first["work"]).read_bytes(),saved)

    def test_end_of_course_never_fakes_a_later_slot(self):
        self.capture()
        review=self.review()
        review["resume_after_lesson_id"]="L04"
        plan=adapt.submit_review(self.root,self.ws,review)["plan"]
        self.assertEqual(plan["findings"][0]["status"],"NO_LATER_REVIEW_SLOT")
        transfer=next(t for t in plan["tasks"] if t["stage"]=="delayed_transfer")
        self.assertIsNone(transfer["scheduled_lesson_id"])

    def add_f01(self):
        curriculum=json.loads((self.root/"data/curriculum.json").read_text())
        curriculum["nodes"].append(dict(id="F01",kind="review",order=8,minutes=90,depends_on=["L05"]))
        write_json(self.root/"data/curriculum.json",curriculum)
        folder=self.root/"lessons/F01"
        folder.mkdir()
        exercises=[dict(id=f"F01-E{i:02d}",minutes=10,block_ids=[],rubric_fr=["Justifier."],error_tags=[])
                   for i in range(2,9)]
        write_json(folder/"lesson.json",dict(lesson_id="F01",minutes=90,blocks=[],variants=[],exercises=exercises,
                   adaptive_replacement_slots=dict(slot_minutes=10,slot_count=4,
                     proposal_exercise_ids=[f"F01-E{i:02d}" for i in range(2,9)],
                     default_exercise_ids=[f"F01-E{i:02d}" for i in range(2,6)])))
        for role,name in [("work","Travail"),("correction","Corrige")]:
            text=rmd("F01",role).replace("  minutes: 20","  minutes: 90")
            text += "\n## 3/6 · Quatre créneaux choisis, 40 min\n\n"
            for i in range(2,9):
                text += f"### Créneau {i-1} {{#F01-E{i:02d}}}\n\n"
                if role=="correction": text += f"<!-- ps1:solution id=F01-E{i:02d} -->\n\n"
                text += f"Problème initial {i}, 10 minutes.\n\n"
            text += "## 4/6 · Rappel mixte, 15 min\n\nRappel protégé de quinze minutes.\n"
            (folder/("F01_"+name+".Rmd")).write_text(text)

    def protect_all_ordinary_review(self):
        for p in (self.root/"lessons").glob("L*/lesson.json"):
            meta=json.loads(p.read_text())
            meta["review_allocation"]=dict(correction_minutes=4,anki_minutes=2)
            write_json(p,meta)

    def test_current_correction_and_anki_cannot_be_consumed(self):
        self.protect_all_ordinary_review()
        self.capture()
        plan=adapt.submit_review(self.root,self.ws,self.review())["plan"]
        self.assertEqual(plan["findings"][0]["status"],"NO_SUITABLE_SLOT")
        base=adapt.prepare_next(self.root,self.ws,"L02",[self.first])
        self.assertEqual(base["status"],"BASE_READY_REVIEW_PENDING")
        self.assertEqual(base["allocation"]["protected_current_review_minutes"],6)
        self.assertEqual(base["allocation"]["inserted_review_minutes"],0)

    def test_unknown_review_split_is_protected(self):
        for p in (self.root/"lessons").glob("L*/lesson.json"):
            meta=json.loads(p.read_text());del meta["review_allocation"];write_json(p,meta)
        self.capture()
        plan=adapt.submit_review(self.root,self.ws,self.review())["plan"]
        self.assertEqual(plan["findings"][0]["status"],"NO_SUITABLE_SLOT")

    def test_f01_replaces_whole_nonadjacent_slots_once(self):
        self.add_f01();self.protect_all_ordinary_review();self.capture()
        plan=adapt.submit_review(self.root,self.ws,self.review())["plan"]
        tasks={t["stage"]:t for t in plan["tasks"]}
        self.assertEqual(tasks["repair"]["scheduled_slot_index"],1)
        self.assertEqual(tasks["delayed_transfer"]["scheduled_slot_index"],3)
        self.assertEqual(tasks["delayed_transfer"]["spacing_kind"],"within_session_spacing")
        self.assertEqual(tasks["delayed_transfer"]["intervening_slot_index"],2)
        self.assertEqual(plan["review_minutes_reserved"],{"F01":20})
        original=(self.root/"lessons/F01/F01_Travail.Rmd").read_bytes()
        prepared=adapt.prepare_next(self.root,self.ws,"F01",[self.root/"lessons/L05/L05_Travail.Rmd"])
        work=Path(prepared["work"]).read_text()
        self.assertNotIn("Problème initial 2,",work)
        self.assertNotIn("Problème initial 4,",work)
        self.assertIn("Problème initial 3,",work)
        self.assertIn("Rappel protégé de quinze minutes.",work)
        self.assertEqual(prepared["allocation"]["inserted_review_minutes"],20)
        self.assertEqual(prepared["allocation"]["remaining_discretionary_minutes"],20)
        self.assertEqual(prepared["allocation"]["total_lesson_minutes"],90)
        self.assertEqual((self.root/"lessons/F01/F01_Travail.Rmd").read_bytes(),original)
        again=adapt.prepare_next(self.root,self.ws,"F01",[self.root/"lessons/L05/L05_Travail.Rmd"])
        self.assertEqual(again["status"],"ALREADY_PREPARED")
        self.assertEqual(adapt.build_plan(self.root,self.ws)["review_minutes_reserved"],{"F01":20})

    def test_f01_seven_minute_attempt_keeps_two_correction_and_one_recall(self):
        self.add_f01();self.protect_all_ordinary_review()
        path=self.root/"lessons/L01/lesson.json"
        meta=json.loads(path.read_text())
        for variant in meta["variants"]: variant["minutes"]=7
        write_json(path,meta)
        self.capture()
        plan=adapt.submit_review(self.root,self.ws,self.review())["plan"]
        for task in plan["tasks"]:
            self.assertEqual(task["slot_allocation"],dict(attempt_minutes=7,correction_minutes=2,recall_minutes=1))
        generated=adapt.prepare_next(self.root,self.ws,"F01",[self.root/"lessons/L05/L05_Travail.Rmd"])
        self.assertIn("7 min de tentative, 2 min de correction, 1 min de rappel",Path(generated["work"]).read_text())

    def test_f01_eight_minute_attempt_cannot_consume_correction_or_recall(self):
        self.add_f01();self.protect_all_ordinary_review()
        path=self.root/"lessons/L01/lesson.json"
        meta=json.loads(path.read_text())
        for variant in meta["variants"]: variant["minutes"]=8
        write_json(path,meta)
        self.capture()
        plan=adapt.submit_review(self.root,self.ws,self.review())["plan"]
        self.assertEqual(plan["findings"][0]["status"],"NO_SUITABLE_SLOT")
        self.assertEqual(plan["review_minutes_reserved"],{})

    def test_f01_transfer_requires_the_intervening_task_confirmation(self):
        self.add_f01();self.protect_all_ordinary_review();self.capture()
        adapt.submit_review(self.root,self.ws,self.review())
        generated=adapt.prepare_next(self.root,self.ws,"F01",[self.root/"lessons/L05/L05_Travail.Rmd"])
        _,g=adapt._verify_generation(self.ws,generated["generation_id"])
        task=next(t for t in g["tasks"] if t["stage"]=="delayed_transfer")
        attempt=Path(generated["work"])
        attempt.write_text(attempt.read_text()+"\nRéponse synthétique au transfert.\n")
        verification=self.verification(generated,task,attempt)
        result=adapt.verify_transfer(self.root,self.ws,verification,attempt)
        self.assertEqual(result["outcome"],"uncertain")
        verification=self.verification(generated,task,attempt,"check-b")
        verification["intervening_task_completed"]=True
        result=adapt.verify_transfer(self.root,self.ws,verification,attempt)
        self.assertEqual(result["outcome"],"pass")
        report=json.loads((Path(result["path"])/"verification.json").read_text())
        self.assertEqual(report["verification_scope"],"within_session_spacing")
        self.assertFalse(report["learner_mastery_changed"])

    def test_capture_prefers_the_actual_prepared_paired_correction(self):
        self.add_f01();self.protect_all_ordinary_review();self.capture()
        adapt.submit_review(self.root,self.ws,self.review())
        generated=adapt.prepare_next(self.root,self.ws,"F01",[self.root/"lessons/L05/L05_Travail.Rmd"])
        first=self.temp/"first_f01.Rmd"
        first.write_text(Path(generated["work"]).read_text()+"\nPremière trace synthétique.\n")
        adapt.capture_handoff(self.root,self.ws,"f01-paired-reference","F01",first,Path(generated["work"]))
        folder,h=adapt._handoff(self.ws,"f01-paired-reference")
        self.assertEqual(h["reference_origin"],"paired_correction")
        ref=folder/"snapshots/reference"/h["snapshots"]["reference"]["document"]
        self.assertEqual(ref.read_bytes(),Path(generated["correction"]).read_bytes())
        self.assertIn("{#L01-V01}",ref.read_text())

    def transfer_fixture(self):
        self.capture()
        adapt.submit_review(self.root,self.ws,self.review())
        adapt.prepare_next(self.root,self.ws,"L02",[self.first])
        generated=adapt.prepare_next(self.root,self.ws,"L04",[self.root/"lessons/L03/L03_Travail.Rmd"])
        _,g=adapt._verify_generation(self.ws,generated["generation_id"])
        task=next(t for t in g["tasks"] if t["stage"]=="delayed_transfer")
        attempt=self.temp/"transfer/L04_Travail.Rmd"
        attempt.parent.mkdir()
        attempt.write_text(Path(generated["work"]).read_text()+"\nRéponse de fixture uniquement.\n")
        return generated,task,attempt

    def verification(self,generated,task,attempt,vid="check-a"):
        evidence=dict(path=attempt.name,sha256=adapt._hash(attempt.read_bytes()),medium="text",
                      certainty="confirmed",visually_reviewed=False,locator_fr="Réponse à "+task["variant_id"])
        return dict(schema_version="2.0.0",verification_id=vid,generation_id=generated["generation_id"],
                    task_id=task["task_id"],reviewer="human",unaided=True,new_decision_observed=True,
                    outcome="pass",method_choice_fr="Le relecteur confirme une décision sur la dépendance.",
                    rubric_results=[dict(criterion_index=i,result="met",evidence=copy.deepcopy(evidence)) for i in [1,2]])

    def test_explicit_unaided_transfer_review_required(self):
        generated,task,attempt=self.transfer_fixture()
        v=self.verification(generated,task,attempt)
        v["unaided"]=False
        result=adapt.verify_transfer(self.root,self.ws,v,attempt)
        self.assertEqual(result["outcome"],"uncertain")
        self.assertNotEqual(adapt.build_plan(self.root,self.ws)["findings"][0]["status"],"TRANSFER_VERIFIED")
        v=self.verification(generated,task,attempt,"check-b")
        result=adapt.verify_transfer(self.root,self.ws,v,attempt)
        self.assertEqual(result["outcome"],"pass")
        self.assertEqual(adapt.build_plan(self.root,self.ws)["findings"][0]["status"],"TRANSFER_VERIFIED")
        self.assertFalse(result["learner_mastery_changed"])

    def test_transfer_uncertain_image_not_graded(self):
        generated,task,attempt=self.transfer_fixture()
        (attempt.parent/"images").mkdir()
        (attempt.parent/"images/papier.png").write_bytes(PNG)
        attempt.write_text(attempt.read_text()+"\n![Réponse](images/papier.png)\n")
        v=self.verification(generated,task,attempt)
        evidence=dict(path="images/papier.png",sha256=adapt._hash(PNG),medium="image",
                      certainty="confirmed",visually_reviewed=False,locator_fr="Photo non relue.")
        for r in v["rubric_results"]:
            r["evidence"]=copy.deepcopy(evidence)
        result=adapt.verify_transfer(self.root,self.ws,v,attempt)
        self.assertEqual(result["outcome"],"uncertain")

    def test_work_can_be_edited_in_the_prepared_version(self):
        generated,task,_=self.transfer_fixture()
        attempt=Path(generated["work"])
        attempt.write_text(attempt.read_text()+"\nRéponse saisie dans le fichier de travail préparé.\n")
        result=adapt.verify_transfer(self.root,self.ws,self.verification(generated,task,attempt),attempt)
        self.assertEqual(result["outcome"],"pass")
        self.assertIn("Réponse saisie",attempt.read_text())

    def test_latest_verification_uses_time_instead_of_identifier_sort(self):
        generated,task,attempt=self.transfer_fixture()
        v=self.verification(generated,task,attempt,"z-first")
        adapt.verify_transfer(self.root,self.ws,v,attempt)
        v=self.verification(generated,task,attempt,"a-second")
        v["outcome"]="retry"
        v["rubric_results"][0]["result"]="not_met"
        adapt.verify_transfer(self.root,self.ws,v,attempt)
        plan=adapt.build_plan(self.root,self.ws)
        self.assertEqual(plan["findings"][0]["status"],"TRANSFER_REVIEW_REQUIRED")

    def test_verification_uses_the_prepared_rubric_snapshot(self):
        generated,task,attempt=self.transfer_fixture()
        path=self.root/"lessons/L01/lesson.json"
        meta=json.loads(path.read_text())
        meta["variants"][1]["rubric_fr"].append("Critère ajouté après la préparation.")
        write_json(path,meta)
        result=adapt.verify_transfer(self.root,self.ws,self.verification(generated,task,attempt),attempt)
        self.assertEqual(result["outcome"],"pass")

    def test_duplicate_verification_compares_all_attempt_image_bytes(self):
        generated,task,attempt=self.transfer_fixture()
        (attempt.parent/"images").mkdir()
        photo=attempt.parent/"images/papier.png"
        photo.write_bytes(PNG)
        attempt.write_text(attempt.read_text()+"\n![Réponse complémentaire](images/papier.png)\n")
        verification=self.verification(generated,task,attempt)
        adapt.verify_transfer(self.root,self.ws,verification,attempt)
        again=adapt.verify_transfer(self.root,self.ws,verification,attempt)
        self.assertEqual(again["status"],"ALREADY_RECORDED")
        photo.write_bytes(PNG+b"changed")
        with self.assertRaises(adapt.AdaptiveError):
            adapt.verify_transfer(self.root,self.ws,verification,attempt)


class ActualCatalogueTest(unittest.TestCase):
    """Copies authored material into temp; all attempt/review records remain synthetic."""
    def setUp(self):
        self.temp=Path(tempfile.mkdtemp(prefix="ps1-adaptive-real-catalogue-"))
        self.root=self.temp/"package"
        self.ws=self.temp/"session"
        (self.root/"data").mkdir(parents=True)
        shutil.copy2(PROJECT/"data/curriculum.json",self.root/"data/curriculum.json")
        for lid in [f"L{i:02d}" for i in range(1,18)]+["F01"]:
            shutil.copytree(PROJECT/"lessons"/lid,self.root/"lessons"/lid)
        (self.root/"adaptive").mkdir()
        for name in ["additional_variants.json","approved_variant_links.json"]:
            shutil.copy2(PROJECT/"adaptive"/name,self.root/"adaptive"/name)

    def tearDown(self):
        for p in self.temp.rglob("*"):
            p.chmod(0o755 if p.is_dir() else 0o644)
        shutil.rmtree(self.temp)

    def synthetic_review(self,lid,eid):
        _,nodes,lessons,exercises,_=adapt._catalog(self.root)
        paths={}
        source=self.root/"lessons"/lid/(lid+"_Travail.Rmd")
        for role in ["first","corrected"]:
            path=self.temp/"synthetic_answers"/role/source.name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(source.read_text()+"\nFixture synthétique uniquement : "+role+".\n")
            paths[role]=path
        hid="fixture-"+lid.lower()
        adapt.capture_handoff(self.root,self.ws,hid,lid,paths["first"],paths["corrected"])
        hp,h=adapt._handoff(self.ws,hid)
        evidence=[]
        for role,manifest in h["snapshots"].items():
            doc=next(f for f in manifest["files"] if f["path"]==manifest["document"])
            evidence.append(dict(snapshot=role,path=doc["path"],sha256=doc["sha256"],medium="text",
                                 certainty="confirmed",visually_reviewed=False,
                                 locator_fr="Fixture temporaire de routage, sans réponse réelle."))
        ex=exercises[eid][1]
        review=dict(schema_version="2.0.0",review_id="review-"+lid.lower(),handoff_id=hid,reviewer="human",
            resume_after_lesson_id=lid,
            introduced_lesson_ids=[n["id"] for n in nodes.values() if n["kind"]=="lesson" and n["order"]<=nodes[lid]["order"]],
            findings=[dict(finding_id="synthetic-finding",exercise_id=eid,error_tags=ex["error_tags"],
                           status="confirmed",corrected_status="self_corrected",
                           observation_fr="Fausse réponse de fixture, uniquement pour vérifier le routage.",evidence=evidence)])
        return review,paths["first"]

    def test_actual_1200_minutes_and_explicit_direct_pairs(self):
        _,nodes,lessons,exercises,_=adapt._catalog(self.root)
        self.assertEqual(sum(n["minutes"] for n in nodes.values()),1200)
        free={lid:adapt._review_capacity(nodes[lid],meta)["replaceable"] for lid,meta in lessons.items()}
        self.assertEqual({lid:v for lid,v in free.items() if v and lid!="F01"},
                         {lid:5 for lid in ["L04","L06","L10","L12","L15","L17"]})
        self.assertEqual(nodes["F01"]["minutes"],90)
        self.assertEqual(free["F01"],40)
        main=[(eid,owner,ex) for eid,(owner,ex) in exercises.items() if nodes[owner]["kind"]=="lesson"]
        self.assertEqual(len(main),61)
        for eid,owner,ex in main:
            candidates=adapt._eligible(lessons[owner],ex,ex["error_tags"])
            self.assertGreaterEqual(len(candidates),2,eid)
            self.assertTrue(all(eid in v["for_exercise_ids"] for v in candidates))
        self.assertEqual({v["id"] for v in adapt._eligible(lessons["L15"],exercises["L15-E02"][1],exercises["L15-E02"][1]["error_tags"])},
                         {"L15-V92","L15-V93"})

    def test_actual_pending_base_then_checkpoint_pair_and_solution_isolation(self):
        review,active=self.synthetic_review("L01","L01-E02")
        base=adapt.prepare_next(self.root,self.ws,"L02",[active])
        self.assertEqual(base["allocation"]["inserted_review_minutes"],0)
        plan=adapt.submit_review(self.root,self.ws,review)["plan"]
        task={t["stage"]:t for t in plan["tasks"]}
        self.assertEqual(task["repair"]["scheduled_lesson_id"],"L04")
        self.assertEqual(task["delayed_transfer"]["scheduled_lesson_id"],"L06")
        source=self.root/"lessons/L04/L04_Travail.Rmd"
        before=source.read_bytes()
        result=adapt.prepare_next(self.root,self.ws,"L04",[self.root/"lessons/L03/L03_Travail.Rmd"])
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual(result["allocation"]["total_lesson_minutes"],45)
        self.assertEqual(result["allocation"]["protected_current_review_minutes"],4)
        self.assertEqual(result["allocation"]["inserted_review_minutes"],4)
        self.assertEqual(result["allocation"]["remaining_discretionary_minutes"],1)
        _,g=adapt._verify_generation(self.ws,result["generation_id"])
        variant=g["variant_snapshots"][task["repair"]["variant_id"]]
        work=Path(result["work"]).read_text();correction=Path(result["correction"]).read_text()
        self.assertIn(variant["prompt_md"],work)
        self.assertNotIn(variant["correction_md"],work)
        self.assertIn(variant["correction_md"],correction)
        self.assertEqual(work.split("---",2)[1],before.decode().split("---",2)[1])

    def test_actual_l17_f01_uses_two_of_four_slots_and_keeps_mixed_recall(self):
        review,active=self.synthetic_review("L17","L17-E01")
        plan=adapt.submit_review(self.root,self.ws,review)["plan"]
        transfer=next(t for t in plan["tasks"] if t["stage"]=="delayed_transfer")
        self.assertEqual(transfer["spacing_kind"],"within_session_spacing")
        self.assertEqual(plan["review_minutes_reserved"],{"F01":20})
        source=self.root/"lessons/F01/F01_Travail.Rmd"
        before=source.read_text()
        result=adapt.prepare_next(self.root,self.ws,"F01",[active])
        work=Path(result["work"]).read_text()
        self.assertEqual(result["allocation"]["total_lesson_minutes"],90)
        self.assertEqual(result["allocation"]["remaining_discretionary_minutes"],20)
        self.assertEqual(before[before.index("## 4/6"):],work[work.index("## 4/6"):])
        self.assertIn("Ce contrôle ne prouve pas une rétention à long terme.",work)
        self.assertFalse(adapt.build_plan(self.root,self.ws)["learner_mastery_changed"])


if __name__ == "__main__":
    unittest.main()

from api.deident import REDACTED, anonymous_snapshot, scrub_text, scrub_value


def test_explicit_identifiers_and_their_tokens_are_removed():
    s = scrub_text("Case for John Doe (MRN 44821). John presented with chest pain; Doe is 62.",
                   identifiers=["John Doe / 44821"])
    assert "John" not in s and "Doe" not in s and "44821" not in s
    assert "chest pain" in s and "62" in s


def test_emails_phones_ids_dates_are_redacted_but_clinical_numbers_survive():
    s = scrub_text("Contact jane.smith@example.org or +1 (415) 555-0134. NHS number 943 476 5919. "
                   "Seen 2024-03-05 and again on March 7, 2024; DOB 12/01/1961. "
                   "Creatinine 1.8 mg/dL, eGFR 28, potassium 5.9 mmol/L, metformin 1000 mg twice daily, "
                   "trial from 2019 with 3 weeks of symptoms.")
    assert "[email]" in s and "jane.smith" not in s
    assert "555-0134" not in s and "[phone]" in s
    assert "943 476 5919" not in s
    assert "2024-03-05" not in s and "March 7, 2024" not in s and "12/01/1961" not in s
    for keep in ("1.8 mg/dL", "eGFR 28", "5.9 mmol/L", "1000 mg", "2019", "3 weeks"):
        assert keep in s, keep


def test_labelled_name_lines_are_blanked():
    s = scrub_text("Patient name: Maria Alvarez\nAge: 54\nName — R. Chen\nPresenting: dyspnea")
    assert "Alvarez" not in s and "Chen" not in s
    assert "Age: 54" in s and "Presenting: dyspnea" in s
    assert REDACTED in s


def test_scrub_value_recurses_into_nested_json():
    v = scrub_value({"a": ["Call 415-555-0134", {"b": "ok@x.io"}], "n": 42}, [])
    assert v["n"] == 42 and "[phone]" in v["a"][0] and v["a"][1]["b"] == "[email]"


def test_anonymous_snapshot_drops_identity_and_scrubs_thread():
    row = {
        "id": "abc", "user_id": "u1", "user_name": "Dr Priya Nair", "user_email": "priya@clinic.org",
        "tenant_id": "demo", "patient_ref": "Ravi Kumar / 778812", "real_patient": True,
        "question": "Ravi Kumar, 58M, MRN 778812, eGFR 28 on metformin — continue?",
        "answer": "Reduce metformin at eGFR 28 [1]. Asked by Dr Priya Nair.",
        "attachments": [{"name": "labs.pdf"}], "visual_observation": "photo of Ravi",
        "thread": [{"question": "Ravi Kumar … continue?", "answer": "Reduce [1]", "attachments": [1],
                    "intake_transcript": "secret", "charts": [{"title": "eGFR for Ravi"}]}],
        "created_at": "2026-09-05T00:00:00",
    }
    snap = anonymous_snapshot(row)
    for k in ("id", "user_id", "user_name", "user_email", "tenant_id", "patient_ref", "real_patient",
              "attachments", "visual_observation", "created_at"):
        assert k not in snap, k
    assert "Ravi" not in snap["question"] and "778812" not in snap["question"] and "eGFR 28" in snap["question"]
    assert "Priya" not in snap["answer"] and "Nair" not in snap["answer"]
    t0 = snap["thread"][0]
    assert "attachments" not in t0 and "intake_transcript" not in t0
    assert "Ravi" not in t0["question"] and "Ravi" not in t0["charts"][0]["title"]

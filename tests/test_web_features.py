from __future__ import annotations

import unittest
from pathlib import Path

from backend.jd_parser import _parse_object
from backend.rag import (
    build_chunks,
    cgpa_value,
    execute_plan,
    heuristic_route,
    parse_json_object,
    validate_plan,
)
from resume_pipeline.interpreter_client import InterpretResult
from resume_pipeline.merge import apply_interpretations, normalize_grade
from resume_pipeline.provenance import _normalize, iter_evidence_fields, map_record
from resume_pipeline.schema import FieldValue, ProjectEntry, ResumeRecord


class RagTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = ResumeRecord(
            file="candidate.txt",
            method="text",
            parse_quality="Clean",
            full_name=FieldValue(raw_value="Ada Lovelace", confidence="high", evidence="Ada Lovelace"),
            cgpa=FieldValue(raw_value="8.8", normalized_value=8.8, confidence="high", evidence="CGPA 8.8"),
            skills=[
                FieldValue(raw_value="Python", confidence="high", evidence="Python"),
                FieldValue(raw_value="FastAPI", confidence="high", evidence="FastAPI"),
            ],
            projects=[
                ProjectEntry(title="API", one_liner="Built an API", confidence="high", evidence="Built an API")
            ],
        )

    def test_chunk_shape_and_hash(self) -> None:
        chunks = build_chunks("ada", self.record)
        self.assertEqual([chunk[0] for chunk in chunks], ["ada:profile", "ada:project_0"])
        self.assertEqual(chunks[0][2]["doc_id"], "ada")
        self.assertEqual(len(chunks[0][2]["content_hash"]), 64)

    def test_structured_filter_and_skill(self) -> None:
        pool = [
            {
                "doc_id": "ada",
                "name": "Ada",
                "cgpa": 8.8,
                "graduation_year": 2025,
                "college": "Example",
                "branch": "CS",
                "degree": "BE",
                "parse_quality": "Clean",
                "score": 90,
                "skills": ["Python", "FastAPI"],
            },
            {
                "doc_id": "bob",
                "name": "Bob",
                "cgpa": 7.0,
                "graduation_year": 2024,
                "college": "Example",
                "branch": "IT",
                "degree": "BE",
                "parse_quality": "Partial",
                "score": 50,
                "skills": ["Java"],
            },
        ]
        plan = validate_plan(
            {
                "filters": [{"field": "cgpa", "op": "gt", "value": 8}],
                "skills_any": ["Python"],
                "sort": {"field": "score", "direction": "desc"},
                "limit": 1,
            }
        )
        self.assertEqual([candidate["doc_id"] for candidate in execute_plan(pool, plan)], ["ada"])

    def test_route_and_json_parsing(self) -> None:
        self.assertEqual(
            heuristic_route("Among candidates who know Python, summarize project experience"),
            "hybrid",
        )
        self.assertEqual(parse_json_object('```json\n{"route":"structured"}\n```')["route"], "structured")

    def test_cgpa_filter_ignores_percentage_scale(self) -> None:
        percentage = FieldValue(raw_value="79%", normalized_value=79, scale="percentage", confidence="high")
        cgpa = FieldValue(raw_value="8.4", normalized_value=8.4, scale="cgpa_10", confidence="high")
        self.assertIsNone(cgpa_value(percentage))
        self.assertEqual(cgpa_value(cgpa), 8.4)


class ProvenanceTests(unittest.TestCase):
    def test_normalization_and_fields(self) -> None:
        self.assertEqual(_normalize("Speech &amp; NLP"), "speech nlp")
        record = ResumeRecord(
            file="candidate.pdf",
            method="docling",
            parse_quality="Clean",
            full_name=FieldValue(raw_value="Ada", confidence="high", evidence="Ada"),
        )
        fields = list(iter_evidence_fields(record))
        self.assertEqual(fields[0].field, "full_name")
        self.assertEqual(fields[0].group, "identity")

    def test_real_docling_mapping_when_artifact_exists(self) -> None:
        record_path = Path("extracted/res2.json")
        docling_path = Path("extracted/provenance/res2.docling.json")
        if not record_path.exists() or not docling_path.exists():
            self.skipTest("real provenance fixture is not available")
        record = ResumeRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
        matches = map_record(record, docling_path)
        self.assertGreaterEqual(len(matches), 20)
        self.assertGreaterEqual(sum(match.located for match in matches), 20)


class GradeNormalizationTests(unittest.TestCase):
    def test_supported_grade_scales(self) -> None:
        self.assertEqual(normalize_grade(8.4, "cgpa_10"), (8.4, "cgpa_10"))
        self.assertEqual(normalize_grade(79, "percentage"), (8.32, "percentage"))
        self.assertEqual(normalize_grade(3.6, "gpa_4"), (9.0, "gpa_4"))

    def test_ambiguous_grade_is_assumed_and_low_confidence(self) -> None:
        record = ResumeRecord(
            file="candidate.txt",
            method="text",
            parse_quality="Clean",
            cgpa=FieldValue(raw_value="8.4", confidence="high", evidence="8.4"),
        )
        apply_interpretations(
            {"candidate": record},
            [InterpretResult("candidate", "cgpa", 8.4, "unknown", False)],
        )
        self.assertEqual(record.cgpa.normalized_value, 8.4)
        self.assertEqual(record.cgpa.scale, "cgpa_10")
        self.assertEqual(record.cgpa.confidence, "low")
        self.assertIn("assumed source scale", record.cgpa.assumption)


class JobDescriptionParserTests(unittest.TestCase):
    def test_json_object_parses_fenced_model_output(self) -> None:
        parsed = _parse_object(
            '```json\n{"role":"Backend Developer","required_skills":["Python"]}\n```'
        )
        self.assertEqual(parsed["role"], "Backend Developer")


if __name__ == "__main__":
    unittest.main()

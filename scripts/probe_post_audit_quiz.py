"""Isolated-reader EvidenceQuiz validation for Probe v1.1."""

from __future__ import annotations

from typing import Any

from probe_post_audit_common import (
    MIN_QUIZ_CATEGORIES, QUIZ_CATEGORIES, _strings, _text,
)


def _validate_quiz(
    bundle: dict[str, Any], state: dict[str, Any], artifacts: dict[str, Any], errors: list[str]
) -> bool:
    quiz = bundle.get("reader_reconstruction")
    if not isinstance(quiz, dict):
        errors.append("reader_reconstruction must be an object")
        return True
    failed = False
    assessor = quiz.get("assessor")
    if not isinstance(assessor, dict):
        errors.append("reader_reconstruction.assessor must be an object")
        assessor = {}
        failed = True
    exact = {
        "role": "independent_isolated_reader",
        "independent_from_probe": True,
        "input_visibility": "final_package_only",
        "saw_truth_boundary": False,
        "saw_claude_audit": False,
        "saw_transform_record": False,
    }
    if not _text(assessor.get("assessor_id")):
        errors.append("reader_reconstruction.assessor.assessor_id must be non-empty")
        failed = True
    for key, expected in exact.items():
        if assessor.get(key) != expected:
            errors.append(f"reader_reconstruction.assessor.{key} must be {str(expected).lower() if isinstance(expected, bool) else expected}")
            failed = True

    categories = quiz.get("required_categories")
    if not _strings(categories, nonempty=True) or set(categories) - QUIZ_CATEGORIES:
        errors.append("reader_reconstruction.required_categories is invalid")
        categories = []
        failed = True
    lacking = MIN_QUIZ_CATEGORIES - set(categories)
    if lacking:
        errors.append(f"reader_reconstruction.required_categories lacks minimum categories: {sorted(lacking)}")
        failed = True
    quiz_claims = quiz.get("required_claim_ids")
    if not _strings(quiz_claims):
        errors.append("reader_reconstruction.required_claim_ids must be a unique string array")
        quiz_claims = []
        failed = True
    if set(quiz_claims) != state["represented"]:
        errors.append("reader_reconstruction.required_claim_ids must exactly match represented package claims")
        failed = True

    questions = quiz.get("questions")
    if not isinstance(questions, list) or not questions:
        errors.append("reader_reconstruction.questions must be a non-empty array")
        questions = []
        failed = True
    seen_questions: set[str] = set()
    covered_categories: set[str] = set()
    reconstructed: set[str] = set()
    output_text = artifacts.get("output_text", "")
    output_elements = artifacts.get("output_elements", {})
    for index, question in enumerate(questions):
        label = f"reader_reconstruction.questions[{index}]"
        local_error = False
        if not isinstance(question, dict) or not _text(question.get("question_id")):
            errors.append(f"{label}.question_id must be non-empty")
            failed = True
            continue
        question_id = question["question_id"]
        if question_id in seen_questions:
            errors.append(f"duplicate reconstruction question_id {question_id}")
            local_error = True
        seen_questions.add(question_id)
        category = question.get("category")
        if category not in QUIZ_CATEGORIES or category not in set(categories):
            errors.append(f"{label}.category is invalid or undeclared")
            local_error = True
        else:
            covered_categories.add(category)
        if question.get("required") is not True:
            errors.append(f"{label}.required must be true")
            local_error = True
        if not _text(question.get("prompt")) or not _text(question.get("answer_summary")) or not _text(question.get("note")):
            errors.append(f"{label} prompt, answer_summary, and note must be non-empty")
            local_error = True
        expected = question.get("expected_answerability")
        observed = question.get("observed_answerability")
        if expected not in {"answerable", "should_be_na"} or observed not in {"answered", "na"}:
            errors.append(f"{label} answerability state is invalid")
            local_error = True
        claim_ids = question.get("reconstructed_claim_ids")
        article_snippets = question.get("supporting_article_snippets")
        card_element_ids = question.get("supporting_card_element_ids")
        for field, value in (
            ("reconstructed_claim_ids", claim_ids),
            ("supporting_article_snippets", article_snippets),
            ("supporting_card_element_ids", card_element_ids),
        ):
            if not _strings(value):
                errors.append(f"{label}.{field} must be a unique string array")
                local_error = True
        claim_ids = claim_ids if isinstance(claim_ids, list) else []
        article_snippets = article_snippets if isinstance(article_snippets, list) else []
        card_element_ids = card_element_ids if isinstance(card_element_ids, list) else []
        unknown_claims = set(claim_ids) - state["represented"]
        if unknown_claims:
            errors.append(f"{label} reconstructs claims outside final package: {sorted(unknown_claims)}")
            local_error = True
        if expected == "answerable":
            if observed != "answered":
                errors.append(f"{label} was answerable but isolated reader returned NA")
                local_error = True
            if not claim_ids or not (article_snippets or card_element_ids):
                errors.append(f"{label} must cite final-package support and reconstruct at least one claim")
                local_error = True
            for snippet in article_snippets:
                if snippet not in output_text:
                    errors.append(f"{label} supporting article snippet is absent from output article: {snippet!r}")
                    local_error = True
            for element_id in card_element_ids:
                if element_id not in output_elements:
                    errors.append(f"{label} references missing output card element {element_id}")
                    local_error = True
        elif expected == "should_be_na":
            if observed != "na":
                errors.append(f"{label} should be NA but isolated reader produced an answer")
                local_error = True
            if claim_ids or article_snippets or card_element_ids:
                errors.append(f"{label} should-be-NA result must not claim package support")
                local_error = True
        expected_status = "fail" if local_error else "pass"
        if question.get("status") != expected_status:
            errors.append(f"{label}.status must be {expected_status} from verified question state")
            local_error = True
        if not local_error and expected == "answerable":
            reconstructed |= set(claim_ids)
        failed |= local_error

    missing_categories = set(categories) - covered_categories
    if missing_categories:
        errors.append(f"reader reconstruction lacks questions for categories: {sorted(missing_categories)}")
        failed = True
    missing_claims = set(quiz_claims) - reconstructed
    if missing_claims:
        errors.append(f"reader reconstruction failed to reconstruct required claims: {sorted(missing_claims)}")
        failed = True
    expected_status = "fail" if failed else "pass"
    if quiz.get("status") != expected_status:
        errors.append(f"reader_reconstruction.status must be {expected_status} from verified quiz state")
        failed = True
    if not _text(quiz.get("rationale")):
        errors.append("reader_reconstruction.rationale must be non-empty")
        failed = True
    if failed and state["guard"].get("reader_reconstruction_passed") == "pass":
        errors.append("semantic_guard.reader_reconstruction_passed cannot pass when reconstruction fails")
    return failed

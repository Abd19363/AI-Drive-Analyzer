import unittest

from app.services.query_intent_service import (
    classify_query_intent,
    is_document_structure_query,
    match_files_by_title,
)


class QueryIntentServiceTests(unittest.TestCase):
    def test_general_knowledge_query_is_answered_directly(self):
        self.assertEqual(classify_query_intent("What is photosynthesis?"), "direct_answer")

    def test_inflation_question_is_checked_against_drive_before_general_answer(self):
        self.assertEqual(
            classify_query_intent("How inflation effects the demand"),
            "fact",
        )

    def test_explicitly_general_topic_question_skips_document_analysis(self):
        self.assertEqual(
            classify_query_intent("In general, how does inflation affect demand?"),
            "direct_answer",
        )

    def test_definition_of_a_document_type_is_answered_directly(self):
        self.assertEqual(classify_query_intent("What is a contract?"), "direct_answer")

    def test_drive_document_query_requires_analysis(self):
        self.assertEqual(
            classify_query_intent("Summarize the project report"),
            "summary",
        )

    def test_question_about_document_contents_requires_analysis(self):
        self.assertEqual(
            classify_query_intent("What does this contract say?"),
            "fact",
        )

    def test_personal_business_question_requires_analysis(self):
        self.assertEqual(
            classify_query_intent("What is our total revenue?"),
            "calculation",
        )

    def test_selected_files_force_analysis_for_general_wording(self):
        self.assertEqual(
            classify_query_intent("What is photosynthesis?", has_selected_files=True),
            "fact",
        )

    def test_assistant_capabilities_are_answered_without_analysis(self):
        self.assertEqual(
            classify_query_intent("What file formats can you analyze?"),
            "capabilities",
        )

    def test_title_match_finds_short_topic_file_in_question(self):
        matching_files = match_files_by_title(
            "How inflation effects the demand",
            [{"id": "inflation-doc", "name": "inflation.pdf"}],
        )
        self.assertEqual([file_info["id"] for file_info in matching_files], ["inflation-doc"])

    def test_title_match_finds_one_relevant_word_from_multiword_title(self):
        matching_files = match_files_by_title(
            "What is inflation?",
            [{"id": "inflation-report", "name": "Annual Inflation Report.pdf"}],
        )
        self.assertEqual(
            [file_info["id"] for file_info in matching_files],
            ["inflation-report"],
        )

    def test_exact_filename_match_excludes_other_files_with_shared_tokens(self):
        matching_files = match_files_by_title(
            'How many sections are in "AI Developer Roadmap"?',
            [
                {"id": "roadmap", "name": "AI Developer Roadmap.pdf"},
                {"id": "notebook", "name": "AI_class.ipynb"},
                {"id": "dashboard", "name": "E-Commerce AI Dashboard.pdf"},
            ],
        )
        self.assertEqual([file_info["id"] for file_info in matching_files], ["roadmap"])

    def test_section_and_tab_inventory_queries_are_detected(self):
        self.assertTrue(
            is_document_structure_query(
                'How many sections are there in "AI Developer Roadmap"?'
            )
        )
        self.assertTrue(is_document_structure_query("List the names of the workbook tabs"))
        self.assertFalse(is_document_structure_query("Summarize this document"))

    def test_title_matched_general_wording_is_routed_to_document_analysis(self):
        self.assertEqual(
            classify_query_intent("What is inflation?", has_selected_files=True),
            "fact",
        )

    def test_title_match_does_not_select_unmentioned_document(self):
        matching_files = match_files_by_title(
            "What is inflation?",
            [{"id": "rates-doc", "name": "Interest rates.pdf"}],
        )
        self.assertEqual(matching_files, [])


if __name__ == "__main__":
    unittest.main()

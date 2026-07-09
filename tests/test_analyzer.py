import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import analyzer

class TestAnalyzer(unittest.TestCase):
    def test_split_into_sentences(self):
        text = "This is the first sentence. Here is another sentence! And a third sentence? This is the fourth one."
        sentences = analyzer.split_into_sentences(text)
        self.assertEqual(len(sentences), 4)
        self.assertEqual(sentences[0], "This is the first sentence.")
        self.assertEqual(sentences[1], "Here is another sentence!")

    def test_extract_keywords(self):
        query = "Python web scraping and automation"
        keywords = analyzer.extract_keywords(query)
        # "and" should be filtered out as stop word
        self.assertIn("python", keywords)
        self.assertIn("scraping", keywords)
        self.assertNotIn("and", keywords)

    def test_score_sentence(self):
        keywords = {"python", "scraping"}
        sentence_match = "Python is a language used for web scraping."
        sentence_no_match = "Java is a class-based, object-oriented language."
        
        score_high = analyzer.score_sentence(sentence_match, keywords, position_weight=1.5)
        score_zero = analyzer.score_sentence(sentence_no_match, keywords, position_weight=1.5)
        
        self.assertTrue(score_high > 0.0)
        self.assertEqual(score_zero, 0.0)

    def test_generate_local_summary(self):
        scraped_data = [
            {
                "url": "http://python.org",
                "title": "Python Language",
                "success": True,
                "paragraphs": [
                    "Python is a popular programming language. It is extensively used in web scraping and automation frameworks.",
                    "Many developers choose Python for data science and AI."
                ]
            }
        ]
        summary = analyzer.generate_local_summary(scraped_data, "Python scraping", "automation")
        self.assertIn("Executive Summary", summary)
        self.assertIn("Key Insights", summary)
        self.assertIn("Python Language", summary)
        self.assertIn("http://python.org", summary)

    @patch('requests.post')
    def test_generate_gemini_summary_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "# AI Synthesized Gemini Report"}]
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        report = analyzer.generate_gemini_summary([], "query", "topic", "fake-gemini-key")
        self.assertEqual(report, "# AI Synthesized Gemini Report")

    @patch('requests.post')
    def test_generate_openai_summary_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "# OpenAI Synthesized Report"}
                }
            ]
        }
        mock_post.return_value = mock_response
        
        report = analyzer.generate_openai_summary([], "query", "topic", "fake-openai-key")
        self.assertEqual(report, "# OpenAI Synthesized Report")

    @patch('requests.post')
    def test_generate_claude_summary_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"text": "# Claude Synthesized Report"}]
        }
        mock_post.return_value = mock_response
        
        report = analyzer.generate_claude_summary([], "query", "topic", "fake-claude-key")
        self.assertEqual(report, "# Claude Synthesized Report")

    @patch('config_manager.load_config')
    @patch('analyzer.generate_local_summary')
    @patch('analyzer.generate_gemini_summary')
    @patch('analyzer.generate_openai_summary')
    def test_synthesize_topics_routing(self, mock_openai, mock_gemini, mock_local, mock_load_config):
        mock_local.return_value = "Local summary"
        mock_gemini.return_value = "Gemini summary"
        mock_openai.return_value = "OpenAI summary"
        
        # Test routing to local
        mock_load_config.return_value = {"preferred_provider": "local"}
        res_local = analyzer.synthesize_topics([], "query", "topic")
        self.assertEqual(res_local, "Local summary")
        
        # Test routing to openai
        mock_load_config.return_value = {"preferred_provider": "openai", "openai_api_key": "key"}
        res_openai = analyzer.synthesize_topics([], "query", "topic")
        self.assertEqual(res_openai, "OpenAI summary")
        
        # Test fallback when provider key is missing
        mock_load_config.return_value = {"preferred_provider": "gemini", "openai_api_key": "key"}
        res_fallback = analyzer.synthesize_topics([], "query", "topic")
        self.assertEqual(res_fallback, "OpenAI summary")

    @patch('utils.safe_request')
    @patch('analyzer.generate_local_summary')
    def test_ai_summary_api_failures_and_exceptions(self, mock_local, mock_request):
        mock_local.return_value = "Rule-based Local Summary"
        
        # 1. Gemini HTTP 400 failure
        mock_resp_400 = MagicMock()
        mock_resp_400.status_code = 400
        mock_resp_400.text = "Invalid API Key"
        mock_request.return_value = mock_resp_400
        res = analyzer.generate_gemini_summary([], "query", "topic", "key")
        self.assertIn("Gemini API call failed", res)
        self.assertIn("Rule-based Local Summary", res)

        # 2. OpenAI Exception failure
        mock_request.side_effect = Exception("Connection Refused")
        res = analyzer.generate_openai_summary([], "query", "topic", "key")
        self.assertIn("OpenAI API call failed", res)
        self.assertIn("Rule-based Local Summary", res)

        # 3. Claude HTTP 500 failure
        mock_request.side_effect = None
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        mock_resp_500.text = "Internal Server Error"
        mock_request.return_value = mock_resp_500
        res = analyzer.generate_claude_summary([], "query", "topic", "key")
        self.assertIn("Anthropic Claude API call failed", res)
        self.assertIn("Rule-based Local Summary", res)

    @patch('utils.safe_request')
    def test_generate_gemini_grounding_search_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "# Grounded Report content"}]
                    },
                    "groundingMetadata": {
                        "webSearchQueries": ["AI agents design", "multi-agent frameworks"]
                    }
                }
            ]
        }
        mock_request.return_value = mock_resp
        
        res = analyzer.generate_gemini_grounding_search("AI agents", "frameworks", "key")
        self.assertTrue(res["success"])
        self.assertEqual(res["report"], "# Grounded Report content")
        self.assertEqual(res["queries"], ["AI agents design", "multi-agent frameworks"])
        self.assertIsNone(res["error"])

    @patch('utils.safe_request')
    def test_generate_gemini_grounding_search_failures(self, mock_request):
        # 1. HTTP 400
        mock_resp_400 = MagicMock()
        mock_resp_400.status_code = 400
        mock_resp_400.text = "Bad Request"
        mock_request.return_value = mock_resp_400
        res = analyzer.generate_gemini_grounding_search("AI agents", "frameworks", "key")
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "HTTP 400: Bad Request")

        # 2. Request Exception
        mock_request.side_effect = Exception("Read timeout")
        res = analyzer.generate_gemini_grounding_search("AI agents", "frameworks", "key")
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "Read timeout")

    def test_score_sentence_length_penalties(self):
        # 1. No words (symbols only)
        score_none = analyzer.score_sentence("!!!", {"test"}, 1.0)
        self.assertEqual(score_none, 0.0)

        # 2. Long sentence (> 40 words)
        long_sentence = " ".join(["python"] * 45)
        score_long = analyzer.score_sentence(long_sentence, {"python"}, 1.0)
        self.assertTrue(score_long > 0.0)

    def test_generate_local_summary_missing_insights_and_long_titles(self):
        # 1. Unsuccessful doc and doc with empty paragraphs
        scraped_data_skipped = [
            {"url": "http://skip1.com", "success": False, "title": "Skipped"},
            {"url": "http://skip2.com", "success": True, "title": "Empty", "paragraphs": []}
        ]
        summary_skipped = analyzer.generate_local_summary(scraped_data_skipped, "test", "topic")
        self.assertIn("No highly relevant sentences", summary_skipped)

        # 2. Long title truncation (> 50 chars)
        long_title = "A" * 60
        scraped_data_long_title = [
            {
                "url": "http://long.com",
                "success": True,
                "title": long_title,
                "paragraphs": ["This is a test paragraph matching the keyword python."]
            }
        ]
        summary_long = analyzer.generate_local_summary(scraped_data_long_title, "python", "topic")
        # Assert title is truncated to 47 chars + "..."
        expected_truncated = "A" * 47 + "..."
        self.assertIn(expected_truncated, summary_long)

        # 3. No matching sentences found (no keywords match)
        scraped_data_no_match = [
            {
                "url": "http://unrelated.com",
                "success": True,
                "title": "Unrelated",
                "paragraphs": ["Java is a programming language completely unrelated to the other one."]
            }
        ]
        summary_no_match = analyzer.generate_local_summary(scraped_data_no_match, "python", "topic")
        self.assertIn("No highly relevant sentences matching your query could be extracted", summary_no_match)

if __name__ == '__main__':
    unittest.main()

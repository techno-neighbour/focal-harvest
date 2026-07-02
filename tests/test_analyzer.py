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

if __name__ == '__main__':
    unittest.main()

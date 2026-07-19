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

    @patch('config_manager.load_config')
    @patch('analyzer.generate_gemini_summary')
    @patch('analyzer.generate_openai_summary')
    def test_synthesize_topics_failover_chain(self, mock_openai, mock_gemini, mock_load_config):
        # Configure both APIs to be available
        mock_load_config.return_value = {
            "preferred_provider": "gemini",
            "gemini_api_key": "gemini-key",
            "openai_api_key": "openai-key"
        }
        
        # 1. Test failover: Gemini fails, OpenAI succeeds
        mock_gemini.side_effect = Exception("Gemini Quota Exceeded")
        mock_openai.return_value = "OpenAI summary result"
        
        res = analyzer.synthesize_topics([], "query", "topic")
        self.assertEqual(res, "OpenAI summary result")
        
        # 2. Test complete failover to local if all APIs fail
        mock_openai.side_effect = Exception("OpenAI Connection Refused")
        res_fail = analyzer.synthesize_topics([], "query", "topic")
        self.assertIn("All configured AI providers failed during synthesis", res_fail)
        self.assertIn("Gemini API failed", res_fail)
        self.assertIn("OpenAI API failed", res_fail)

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

    def test_token_bucket_rate_limiter(self):
        from utils import TokenBucket
        import time
        
        # Capacity 2, fill rate 1 token per second
        bucket = TokenBucket(capacity=2.0, fill_rate=1.0)
        
        # Can consume 2 tokens immediately
        self.assertTrue(bucket.consume(1.0))
        self.assertTrue(bucket.consume(1.0))
        # Cannot consume a third token immediately
        self.assertFalse(bucket.consume(1.0))
        
        # Wait 1.1 seconds, should refill 1 token
        time.sleep(1.1)
        self.assertTrue(bucket.consume(1.0))
        self.assertFalse(bucket.consume(1.0))
        
        # Test wait_for_token blocks and lets us proceed
        start_time = time.time()
        bucket.wait_for_token(1.0)
        duration = time.time() - start_time
        # Duration should be at least 0.8s since we had 0 tokens
        self.assertGreaterEqual(duration, 0.8)

    def test_smart_sentence_filtering(self):
        text = (
            "This is the first sentence anchor. "  # Anchor 1
            "This is the second sentence anchor. " # Anchor 2
            "Too short. "                          # Too short (< 5 words)
            "This sentence is way too long. "
            "It has many words. "
            "Let us duplicate words to exceed sixty. "
            "One two three four five six seven eight nine ten "
            "eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty "
            "twentyone twentytwo twentythree twentyfour twentyfive twentysix twentyseven twentyeight twentynine thirty "
            "thirtyone thirtytwo thirtythree thirtyfour thirtyfive thirtysix thirtyseven thirtyeight thirtynine forty "
            "fortyone fortytwo fortythree fortyfour fortyfive fortysix fortyseven fortyeight fortynine fifty "
            "fiftyone fiftytwo fiftythree fiftyfour fiftyfive fiftysix fiftyseven fiftyeight fiftynine sixty sixtyone. " # Too long (> 60 words)
            "The core Gemini pricing structure is highly optimized. " # High relevance match
            "This is just an unrelated filler sentence with no keywords." # No keyword match
        )
        
        dense_text = analyzer.filter_dense_context(text, "Gemini pricing", "Optimize budget", max_sentences=5)
        
        # Should contain Anchor 1
        self.assertIn("This is the first sentence anchor", dense_text)
        # Should contain Anchor 2
        self.assertIn("This is the second sentence anchor", dense_text)
        # Should contain the high relevance matched sentence
        self.assertIn("Gemini pricing structure is highly optimized", dense_text)
        # Should NOT contain too short sentence
        self.assertNotIn("Too short", dense_text)
        # Should NOT contain too long sentence
        self.assertNotIn("sixtyone", dense_text)
        # Should NOT contain unrelated filler
        self.assertNotIn("unrelated filler sentence", dense_text)

    def test_content_classifier(self):
        # Dialogue heavy text
        narrative_text = (
            "\"Hello!\" she said. \"How are you doing today?\" "
            "\"I am fine,\" John replied, holding his bag. \"We should go to our house.\""
        )
        # Informational text
        info_text = (
            "Artificial intelligence is a branch of computer science. "
            "The industry grew significantly in the year 2020. "
            "Data centers consume large amounts of electricity."
        )
        
        self.assertEqual(analyzer._classify_content_style(narrative_text), "narrative")
        self.assertEqual(analyzer._classify_content_style(info_text), "informational")

    def test_text_rank_extraction(self):
        # A set of sentences where sentences share overlapping vocabulary terms
        sentences = [
            "Python programming language is great for developers.",
            "Developers love coding in Python.",
            "Coding in Java is also popular among developers.",
            "This is a completely random sentence with no common words.",
            "Another filler line about fruits and oranges."
        ]
        keywords = {"Python", "developers", "coding"}
        
        # Run TextRank extraction
        extracted = analyzer.text_rank_extract(sentences, keywords, max_sentences=2)
        
        # The top sentences should be the highly connected ones (Developers / Python / Coding)
        self.assertEqual(len(extracted), 2)
        self.assertTrue(any("Python" in s or "Coding" in s for s in extracted))

    def test_generate_local_summary_multi_perspective(self):
        scraped_data = [
            {
                "url": "http://example.com/tech",
                "title": "Technical Systems Spec",
                "success": True,
                "paragraphs": [
                    "System testing is a key part of technology.",
                    "Here is a second sentence about evaluation.",
                    "We need a third sentence about safety.",
                    "System analysis can discuss research designs.",
                    "The evaluation presents project scopes.",
                    "Safety explains baseline features.",
                    "This system architecture is built in python using clean code plugins.",
                    "We need an evaluation of the pricing and memory cost constraints for hardware ram.",
                    "Ensure safety guidelines, compliance rules, and privacy cookies tos are met.",
                    "Another system code implementation class is created."
                ]
            }
        ]
        summary = analyzer.generate_local_summary(scraped_data, "system evaluation", "safety")
        self.assertIn("Technical Architecture & Core Mechanisms", summary)
        self.assertIn("Feasibility & Resource Constraints", summary)
        self.assertIn("Operational, Legal & Safety Perspectives", summary)

    def test_generate_local_summary_incremental_append(self):
        prev_report = "# Original Report\n## Sources Scraped\n| 1 | Old Source | http://old.com | Success |"
        scraped_data = [
            {
                "url": "http://new.com",
                "title": "New Source",
                "success": True,
                "paragraphs": [
                    "This is a completely brand new incremental finding about system updates."
                ]
            }
        ]
        summary = analyzer.generate_local_summary(scraped_data, "system updates", "delta", previous_report=prev_report)
        self.assertIn("Incremental Update (Local", summary)
        self.assertIn("completely brand new incremental finding", summary)

if __name__ == '__main__':
    unittest.main()


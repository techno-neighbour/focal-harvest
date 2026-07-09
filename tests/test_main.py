import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main

class TestMain(unittest.TestCase):
    def test_calculate_scraped_hash_empty(self):
        # Empty inputs should produce a standard empty hash
        h = main.calculate_scraped_hash([])
        self.assertTrue(len(h) == 32) # Valid MD5 hex length

    def test_calculate_scraped_hash_stable_sorting(self):
        # Order of inputs should not change the generated hash
        data1 = [
            {"url": "http://a.com", "success": True, "raw_text": "Content A"},
            {"url": "http://b.com", "success": True, "raw_text": "Content B"}
        ]
        data2 = [
            {"url": "http://b.com", "success": True, "raw_text": "Content B"},
            {"url": "http://a.com", "success": True, "raw_text": "Content A"}
        ]
        hash1 = main.calculate_scraped_hash(data1)
        hash2 = main.calculate_scraped_hash(data2)
        self.assertEqual(hash1, hash2)

    def test_calculate_scraped_hash_skips_failed_scrapes(self):
        # Failed scrapes should not affect the hash
        data_base = [
            {"url": "http://a.com", "success": True, "raw_text": "Content A"}
        ]
        data_with_failed = [
            {"url": "http://a.com", "success": True, "raw_text": "Content A"},
            {"url": "http://b.com", "success": False, "raw_text": "Failed"}
        ]
        hash_base = main.calculate_scraped_hash(data_base)
        hash_failed = main.calculate_scraped_hash(data_with_failed)
        self.assertEqual(hash_base, hash_failed)

    @patch('main.console')
    @patch('analyzer.generate_gemini_grounding_search')
    @patch('notifier.dispatch_notifications')
    def test_execute_scrape_flow_grounding_path(self, mock_dispatch, mock_grounding, mock_console):
        from contextlib import contextmanager
        class MockStatus:
            def update(self, text):
                pass
        @contextmanager
        def mock_status_context(*args, **kwargs):
            yield MockStatus()
        mock_console.status.side_effect = mock_status_context

        # Setup mock grounding search result
        mock_grounding.return_value = {
            "success": True,
            "report": "# Grounded Report",
            "queries": ["grounding query"],
            "error": None
        }
        mock_dispatch.return_value = {
            "saved_paths": {
                "markdown_path": "reports/report.md",
                "json_path": "reports/raw.json"
            },
            "discord": True,
            "telegram": True
        }
        
        config = {
            "search_engine": "ai_grounding",
            "gemini_api_key": "fake-key"
        }
        
        report, hash_val = main.execute_scrape_flow("query", "topic", [], config)
        self.assertEqual(report, "# Grounded Report")
        self.assertEqual(hash_val, "")
        mock_grounding.assert_called_once_with("query", "topic", "fake-key")

    @patch('main.console')
    @patch('scraper.search_duckduckgo')
    @patch('scraper.scrape_urls_adaptive')
    @patch('analyzer.synthesize_topics')
    @patch('notifier.dispatch_notifications')
    def test_execute_scrape_flow_normal_path(self, mock_dispatch, mock_synthesize, mock_scrape, mock_search_ddg, mock_console):
        from contextlib import contextmanager
        class MockStatus:
            def update(self, text):
                pass
        @contextmanager
        def mock_status_context(*args, **kwargs):
            yield MockStatus()
        mock_console.status.side_effect = mock_status_context

        mock_search_ddg.return_value = [{"title": "Title", "url": "http://test.com", "snippet": "Snippet"}]
        mock_scrape.return_value = [{"url": "http://test.com", "success": True, "raw_text": "Text"}]
        mock_synthesize.return_value = "# Synthesized Report"
        mock_dispatch.return_value = {
            "saved_paths": {
                "markdown_path": "reports/report.md",
                "json_path": "reports/raw.json"
            },
            "discord": False,
            "telegram": False
        }
        
        config = {
            "search_engine": "duckduckgo",
            "default_max_results": 2
        }
        
        report, hash_val = main.execute_scrape_flow("query", "topic", [], config)
        self.assertEqual(report, "# Synthesized Report")
        self.assertTrue(len(hash_val) == 32)
        # Verify candidate pool size is max_results * 3
        mock_search_ddg.assert_called_once_with("query", max_results=6)
        mock_scrape.assert_called_once()
        mock_synthesize.assert_called_once()

if __name__ == '__main__':
    unittest.main()

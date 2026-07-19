import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import json
import datetime
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import notifier

class TestNotifier(unittest.TestCase):
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_report_to_files(self, mock_file, mock_makedirs):
        query = "Gemini vs Claude"
        spec_topic = "Context length and pricing"
        markdown_content = "# Gemini vs Claude Report"
        scraped_data = [{"url": "http://test.com", "title": "Test site", "success": True, "raw_text": "Sample text"}]
        
        paths = notifier.save_report_to_files(query, spec_topic, markdown_content, scraped_data)
        
        # Verify filenames
        norm_md = os.path.normpath(paths["markdown_path"])
        norm_json = os.path.normpath(paths["json_path"])
        self.assertTrue("markdown" in norm_md and "report_gemini_vs_claude_" in norm_md)
        self.assertTrue(norm_md.endswith(".md"))
        self.assertTrue("json" in norm_json and "raw_data_gemini_vs_claude_" in norm_json)
        self.assertTrue(norm_json.endswith(".json"))

        # Check file writes
        self.assertTrue(mock_file.call_count >= 2)
        
    @patch('requests.post')
    def test_send_discord_webhook(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response
        
        webhook_url = "http://discord.webhook"
        query = "AI agents"
        spec = "multi-agent orchestration"
        md_content = "## Executive Summary\n* Bullet point 1\n* Bullet point 2\n## Detailed Synthesis"
        
        success = notifier.send_discord_webhook(webhook_url, query, spec, md_content, "reports/report.md")
        self.assertTrue(success)
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["embeds"][0]["title"], f"🌐 Web Scraper Deep Dive: {query}")
        
    @patch('requests.post')
    def test_send_telegram_notification(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        token = "123456:bottoken"
        chat_id = "987654"
        query = "Self-driving cars"
        spec = "Lidar vs Cameras"
        md_content = "# Report\n* Some text here."
        
        success = notifier.send_telegram_notification(token, chat_id, query, spec, md_content)
        self.assertTrue(success)
        mock_post.assert_called_once()
        post_url = mock_post.call_args[0][0]
        self.assertEqual(post_url, f"https://api.telegram.org/bot{token}/sendMessage")
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["chat_id"], chat_id)

    @patch('notifier.save_report_to_files')
    @patch('notifier.print_to_console')
    @patch('notifier.send_discord_webhook')
    @patch('notifier.send_telegram_notification')
    def test_dispatch_notifications(self, mock_tg, mock_discord, mock_print, mock_save):
        mock_save.return_value = {
            "markdown_path": "reports/report.md",
            "json_path": "reports/raw.json"
        }
        mock_discord.return_value = True
        mock_tg.return_value = True
        
        query = "Test"
        spec = "Focus"
        md_content = "Report Content"
        scraped_data = []
        config = {
            "discord_webhook": "http://discord.webhook",
            "telegram_token": "token",
            "telegram_chat_id": "chat_id"
        }
        
        results = notifier.dispatch_notifications(query, spec, md_content, scraped_data, config)
        
        self.assertTrue(results["console"])
        self.assertTrue(results["discord"])
        self.assertTrue(results["telegram"])
        mock_save.assert_called_once_with(query, spec, md_content, scraped_data, previous_report_path=None)
        mock_print.assert_called_once_with(md_content)
        mock_discord.assert_called_once_with("http://discord.webhook", query, spec, md_content, "reports/report.md")
        mock_tg.assert_called_once_with("token", "chat_id", query, spec, md_content)

    @patch('utils.safe_request')
    def test_send_discord_webhook_boundaries_and_failures(self, mock_request):
        # 1. Null/empty validation
        self.assertFalse(notifier.send_discord_webhook("", "query", "spec", "content", "reports/report.md"))
        
        # 2. HTTP failure (status 400)
        mock_resp_400 = MagicMock()
        mock_resp_400.status_code = 400
        mock_request.return_value = mock_resp_400
        self.assertFalse(notifier.send_discord_webhook("http://webhook", "query", "spec", "content", "reports/report.md"))

        # 3. Connection Exception
        mock_request.side_effect = Exception("Connection timed out")
        self.assertFalse(notifier.send_discord_webhook("http://webhook", "query", "spec", "content", "reports/report.md"))

        # 4. Summary formatting fallback (no '## Executive Summary')
        mock_request.side_effect = None
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_request.return_value = mock_resp_200
        
        long_content = "Word " * 200
        self.assertTrue(notifier.send_discord_webhook("http://webhook", "query", "spec", long_content, "reports/report.md"))
        payload = mock_request.call_args[1]["json"]
        self.assertTrue(payload["embeds"][0]["description"].endswith("..."))

    @patch('utils.safe_request')
    def test_send_telegram_notification_boundaries_and_failures(self, mock_request):
        # 1. Null/empty validation
        self.assertFalse(notifier.send_telegram_notification("", "chat_id", "query", "spec", "content"))
        self.assertFalse(notifier.send_telegram_notification("token", "", "query", "spec", "content"))

        # 2. HTTP failure (status 401)
        mock_resp_401 = MagicMock()
        mock_resp_401.status_code = 401
        mock_request.return_value = mock_resp_401
        self.assertFalse(notifier.send_telegram_notification("token", "chat_id", "query", "spec", "content"))

        # 3. Connection Exception
        mock_request.side_effect = Exception("API Server unreachable")
        self.assertFalse(notifier.send_telegram_notification("token", "chat_id", "query", "spec", "content"))

    @patch('notifier.console.print')
    def test_print_to_console(self, mock_print):
        notifier.print_to_console("Markdown text")
        self.assertEqual(mock_print.call_count, 3)

if __name__ == '__main__':
    unittest.main()

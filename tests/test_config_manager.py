import unittest
from unittest.mock import patch, mock_open
import os
import json
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config_manager

class TestConfigManager(unittest.TestCase):
    def setUp(self):
        # Clear environment variables to avoid pollution
        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    @patch('os.path.exists')
    def test_load_config_default(self, mock_exists):
        mock_exists.return_value = False
        config = config_manager.load_config()
        self.assertEqual(config["preferred_provider"], "local")
        self.assertEqual(config["default_max_results"], 5)
        self.assertEqual(config["saved_searches"], [])

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='{"preferred_provider": "gemini", "default_max_results": 10}')
    def test_load_config_saved(self, mock_file, mock_exists):
        mock_exists.return_value = True
        config = config_manager.load_config()
        self.assertEqual(config["preferred_provider"], "gemini")
        self.assertEqual(config["default_max_results"], 10)

    @patch('os.path.exists')
    def test_load_config_env_overlay(self, mock_exists):
        mock_exists.return_value = False
        # Set mock environment variables
        with patch.dict(os.environ, {
            "GEMINI_API_KEY": "env-gemini-key",
            "DISCORD_WEBHOOK_URL": "http://discord.hook",
            "TELEGRAM_BOT_TOKEN": "env-tg-token",
            "TELEGRAM_CHAT_ID": "env-tg-chat-id"
        }):
            config = config_manager.load_config()
            self.assertEqual(config["gemini_api_key"], "env-gemini-key")
            self.assertEqual(config["discord_webhook"], "http://discord.hook")
            self.assertEqual(config["telegram_token"], "env-tg-token")
            self.assertEqual(config["telegram_chat_id"], "env-tg-chat-id")
            self.assertEqual(config["preferred_provider"], "gemini")

    @patch('builtins.open', new_callable=mock_open)
    def test_save_config(self, mock_file):
        config_data = {"preferred_provider": "openai", "default_max_results": 3}
        success = config_manager.save_config(config_data)
        self.assertTrue(success)
        mock_file.assert_called_once_with(config_manager.CONFIG_FILE, "w", encoding="utf-8")
        
        # Verify JSON writing
        write_calls = "".join(call.args[0] for call in mock_file().write.call_args_list)
        written_json = json.loads(write_calls)
        self.assertEqual(written_json["preferred_provider"], "openai")

    @patch('config_manager.load_config')
    @patch('config_manager.save_config')
    def test_add_saved_search(self, mock_save, mock_load):
        mock_load.return_value = {
            "saved_searches": []
        }
        config_manager.add_saved_search("robots", "languages in robotics")
        mock_save.assert_called_once()
        saved_call = mock_save.call_args[0][0]
        self.assertEqual(len(saved_call["saved_searches"]), 1)
        self.assertEqual(saved_call["saved_searches"][0]["query"], "robots")
        self.assertEqual(saved_call["saved_searches"][0]["spec_topic"], "languages in robotics")

    @patch('os.path.exists')
    @patch('builtins.open', side_effect=Exception("Permission denied"))
    def test_load_config_corrupt(self, mock_file, mock_exists):
        mock_exists.return_value = True
        config = config_manager.load_config()
        # Should gracefully fall back to default configuration
        self.assertEqual(config["preferred_provider"], "local")
        self.assertEqual(config["default_max_results"], 5)

    @patch('builtins.open', side_effect=Exception("Read-only system"))
    def test_save_config_failure(self, mock_file):
        config_data = {"preferred_provider": "local"}
        success = config_manager.save_config(config_data)
        self.assertFalse(success)

    @patch('os.path.exists')
    def test_load_config_other_env_overlays(self, mock_exists):
        mock_exists.return_value = False
        
        # Test OpenAI key overlay
        with patch.dict(os.environ, {"OPENAI_API_KEY": "openai-env-key"}):
            config = config_manager.load_config()
            self.assertEqual(config["openai_api_key"], "openai-env-key")
            self.assertEqual(config["preferred_provider"], "openai")

        # Test Anthropic key overlay
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "anthropic-env-key"}):
            config = config_manager.load_config()
            self.assertEqual(config["anthropic_api_key"], "anthropic-env-key")
            self.assertEqual(config["preferred_provider"], "anthropic")

        # Test Tavily key overlay
        with patch.dict(os.environ, {"TAVILY_API_KEY": "tavily-env-key"}):
            config = config_manager.load_config()
            self.assertEqual(config["tavily_api_key"], "tavily-env-key")

if __name__ == '__main__':
    unittest.main()

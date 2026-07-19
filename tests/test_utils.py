import unittest
from unittest.mock import patch, MagicMock
import requests
import sys
import os

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import utils

class TestUtils(unittest.TestCase):
    @patch('requests.get')
    def test_safe_request_success_first_try(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        response = utils.safe_request("get", "http://test.com")
        self.assertEqual(response.status_code, 200)
        mock_get.assert_called_once_with("http://test.com")

    @patch('time.sleep')
    @patch('requests.get')
    @patch('config_manager.load_config')
    def test_safe_request_retry_on_status(self, mock_load, mock_get, mock_sleep):
        mock_load.return_value = {
            "max_retries": 2,
            "backoff_factor": 0.1,
            "retry_on_status_codes": [503]
        }
        
        # 503 response then 200 response
        mock_resp_503 = MagicMock()
        mock_resp_503.status_code = 503
        
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        
        mock_get.side_effect = [mock_resp_503, mock_resp_200]
        
        response = utils.safe_request("get", "http://retry.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch('time.sleep')
    @patch('requests.get')
    @patch('config_manager.load_config')
    def test_safe_request_retry_on_exception(self, mock_load, mock_get, mock_sleep):
        mock_load.return_value = {
            "max_retries": 1,
            "backoff_factor": 0.1
        }
        
        # ConnectionError then success
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        
        mock_get.side_effect = [requests.exceptions.ConnectionError("Connection lost"), mock_resp_200]
        
        response = utils.safe_request("get", "http://exception-retry.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch('time.sleep')
    @patch('requests.get')
    @patch('config_manager.load_config')
    def test_safe_request_max_retries_exceeded(self, mock_load, mock_get, mock_sleep):
        mock_load.return_value = {
            "max_retries": 2,
            "backoff_factor": 0.1
        }
        
        # Always fail with ConnectionError
        mock_get.side_effect = requests.exceptions.ConnectionError("Constant fail")
        
        with self.assertRaises(requests.exceptions.ConnectionError):
            utils.safe_request("get", "http://always-fail.com")
            
        self.assertEqual(mock_get.call_count, 3) # Initial + 2 retries
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('os.makedirs')
    @patch('logging.getLogger')
    def test_setup_logging(self, mock_get_logger, mock_makedirs):
        mock_logger = MagicMock()
        mock_logger.handlers = []
        mock_get_logger.return_value = mock_logger
        
        logger = utils.setup_logging()
        self.assertEqual(logger, mock_logger)
        mock_makedirs.assert_called_once_with("reports", exist_ok=True)
        mock_logger.addHandler.assert_called_once()

    @patch('requests.get')
    def test_safe_request_immediate_timeout(self, mock_get):
        # Mocks a timeout exception during request
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        
        with self.assertRaises(requests.exceptions.Timeout):
            utils.safe_request("get", "http://timeout-site.com")
            
        mock_get.assert_called_once() # Zero retries on timeouts

    @patch('time.sleep')
    @patch('requests.get')
    @patch('config_manager.load_config')
    def test_safe_request_config_load_failure(self, mock_load, mock_get, mock_sleep):
        # Simulate config load failure
        mock_load.side_effect = Exception("Config file missing")
        
        # 500 response on first try, then 200 response
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        
        mock_get.side_effect = [mock_resp_500, mock_resp_200]
        
        # Should default to max_retries = 3 and status_codes = [429, 500, 502, 503, 504]
        response = utils.safe_request("get", "http://retry-default.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_get.call_count, 2)

    @patch('os.path.exists')
    @patch('requests.get')
    @patch('config_manager.load_config')
    def test_safe_request_cookie_injection(self, mock_load, mock_get, mock_exists):
        mock_exists.return_value = False
        mock_load.return_value = {
            "universal_cookies": {
                "reddit.com": "reddit_session=foo_reddit; edgebucket=9tysvcJHlTXd6YvPJm"
            }
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # 1. Test Reddit request (should auto-detect edgebucket cookie and set Edge User-Agent)
        utils.safe_request("get", "https://www.reddit.com/r/test")
        args, kwargs = mock_get.call_args
        self.assertIn("headers", kwargs)
        self.assertEqual(kwargs["headers"].get("Cookie"), "reddit_session=foo_reddit; edgebucket=9tysvcJHlTXd6YvPJm")
        self.assertEqual(kwargs["headers"].get("User-Agent"), "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0")
        
        # Reset mocks
        mock_get.reset_mock()
        
        # 3. Test custom User-Agent override
        mock_load.return_value = {
            "custom_user_agent": "CustomAgent/1.0"
        }
        utils.safe_request("get", "https://example.com")
        args, kwargs = mock_get.call_args
        self.assertIn("headers", kwargs)
        self.assertEqual(kwargs["headers"].get("User-Agent"), "CustomAgent/1.0")

        # Reset mocks
        mock_get.reset_mock()

        # 4. Test universal cookies mapping
        mock_load.return_value = {
            "universal_cookies": {
                "linkedin.com": "li_at=foo_linkedin",
                "twitter.com": "auth_token=foo_twitter"
            }
        }
        utils.safe_request("get", "https://www.linkedin.com/feed/")
        args, kwargs = mock_get.call_args
        self.assertIn("headers", kwargs)
        self.assertEqual(kwargs["headers"].get("Cookie"), "li_at=foo_linkedin")

        # Reset mocks
        mock_get.reset_mock()

        # 5. Test auto-extraction mapping
        mock_load.return_value = {
            "auto_extract_cookies": True,
            "browser_source": "chrome"
        }
        with patch('utils.get_cookies_from_browser') as mock_extract:
            mock_extract.return_value = "session=foo_auto"
            utils.safe_request("get", "https://facebook.com/home")
            mock_extract.assert_called_once_with("facebook.com", "chrome")
            args, kwargs = mock_get.call_args
            self.assertIn("headers", kwargs)
            self.assertEqual(kwargs["headers"].get("Cookie"), "session=foo_auto")

        # Reset mocks
        mock_get.reset_mock()

        # 6. Test cookies.txt Netscape parser and fallback
        mock_exists.side_effect = lambda path: True if path in ["cookies.txt", os.path.join("config", "cookies.txt")] else False
        with patch('builtins.open', unittest.mock.mock_open(read_data=".reddit.com\tTRUE\t/\tFALSE\t0\treddit_session\tfoo_netscape\n")):
            # Since cookies.txt is mocked to exist, it should override others
            utils.safe_request("get", "https://www.reddit.com/r/test")
            args, kwargs = mock_get.call_args
            self.assertIn("headers", kwargs)
            self.assertEqual(kwargs["headers"].get("Cookie"), "reddit_session=foo_netscape")

    def test_decompose_query_locally_comparison(self):
        query = "Gemini 1.5 Flash vs Gemini 1.5 Pro"
        sub_queries = utils.decompose_query_locally(query)
        self.assertEqual(len(sub_queries), 5)
        self.assertEqual(sub_queries[0], query)
        self.assertIn("Gemini 1.5 Flash vs Gemini 1.5 Pro pricing cost", sub_queries)
        self.assertIn("Gemini 1.5 Flash vs Gemini 1.5 Pro latency speed benchmarks", sub_queries)

    def test_decompose_query_locally_informational(self):
        query = "How to optimize FastAPI performance for high traffic"
        sub_queries = utils.decompose_query_locally(query)
        self.assertEqual(len(sub_queries), 5)
        self.assertEqual(sub_queries[0], query)
        self.assertIn("optimize fastapi performance high guide documentation tutorial", sub_queries)
        self.assertIn("optimize fastapi performance high code examples github implementation", sub_queries)

if __name__ == '__main__':
    unittest.main()


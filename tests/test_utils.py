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

if __name__ == '__main__':
    unittest.main()

import unittest
from unittest.mock import patch, MagicMock
import urllib.parse
import sys
import os

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import scraper

class TestScraper(unittest.TestCase):
    def test_get_headers(self):
        headers = scraper.get_headers()
        self.assertIn("User-Agent", headers)
        self.assertIn("Accept", headers)
        self.assertEqual(headers["Connection"], "keep-alive")

    @patch('requests.post')
    def test_search_tavily(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"title": "Test Title", "url": "http://example.com", "content": "Test content snippet"}
            ]
        }
        mock_post.return_value = mock_response
        
        results = scraper.search_tavily("test query", "fake-key", max_results=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Test Title")
        self.assertEqual(results[0]["url"], "http://example.com")
        self.assertEqual(results[0]["snippet"], "Test content snippet")

    @patch('requests.get')
    def test_search_duckduckgo_html_layout(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Simulated DuckDuckGo HTML layout
        mock_response.text = """
        <div class="result">
            <a class="result__a" href="https://duckduckgo.com/l/?uddg=http%3A%2F%2Fpython.org&rut=123">Python Programming Language</a>
            <a class="result__snippet">Python is an interpreted programming language.</a>
        </div>
        """
        mock_get.return_value = mock_response
        
        results = scraper.search_duckduckgo("python", max_results=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Python Programming Language")
        self.assertEqual(results[0]["url"], "http://python.org")
        self.assertEqual(results[0]["snippet"], "Python is an interpreted programming language.")

    @patch('requests.post')
    @patch('requests.get')
    def test_search_duckduckgo_lite_layout(self, mock_get, mock_post):
        # Force requests.get to fail to trigger fallback requests.post Lite layout
        mock_get_response = MagicMock()
        mock_get_response.status_code = 503
        mock_get.return_value = mock_get_response
        
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        # Simulated DuckDuckGo Lite layout using table rows
        mock_post_response.text = """
        <table>
            <tr>
                <td>
                    <a class="result-link" href="https://duckduckgo.com/l/?uddg=http%3A%2F%2Frealpython.com&rut=456">Real Python Tutorials</a>
                </td>
            </tr>
            <tr>
                <td class="result-snippet">Learn Python online with our tutorials.</td>
            </tr>
        </table>
        """
        mock_post.return_value = mock_post_response
        
        results = scraper.search_duckduckgo("python tutorials", max_results=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Real Python Tutorials")
        self.assertEqual(results[0]["url"], "http://realpython.com")
        self.assertEqual(results[0]["snippet"], "Learn Python online with our tutorials.")

    @patch('requests.get')
    def test_scrape_url_article(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = """
        <html>
            <head>
                <title>Awesome AI Article</title>
                <meta name="description" content="All about artificial intelligence.">
            </head>
            <body>
                <main>
                    <h1>The Future of AI</h1>
                    <p>AI is going to change the world in many unexpected ways.</p>
                    <h2>Deep Learning</h2>
                    <p>Deep neural networks are the core of modern systems.</p>
                </main>
            </body>
        </html>
        """
        mock_get.return_value = mock_response
        
        res = scraper.scrape_url("http://ai-article.com", timeout=5)
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Awesome AI Article")
        self.assertEqual(res["meta_description"], "All about artificial intelligence.")
        self.assertIn("The Future of AI", res["raw_text"])
        self.assertEqual(len(res["headings"]), 2)
        self.assertEqual(res["headings"][0]["text"], "The Future of AI")
        self.assertEqual(res["headings"][1]["text"], "Deep Learning")

    @patch('requests.get')
    def test_scrape_url_empty_or_error(self, mock_get):
        # Empty body test
        mock_resp_empty = MagicMock()
        mock_resp_empty.status_code = 200
        mock_resp_empty.headers = {"content-type": "text/html"}
        mock_resp_empty.text = "   "
        mock_get.return_value = mock_resp_empty
        
        res_empty = scraper.scrape_url("http://empty.com")
        self.assertFalse(res_empty["success"])
        self.assertEqual(res_empty["error"], "Empty response body")

        # 404 error test
        mock_resp_404 = MagicMock()
        mock_resp_404.status_code = 404
        mock_get.return_value = mock_resp_404
        res_404 = scraper.scrape_url("http://not-found.com")
        self.assertFalse(res_404["success"])
        self.assertEqual(res_404["error"], "HTTP status 404")

    @patch('scraper.scrape_url')
    def test_scrape_urls_concurrently(self, mock_scrape):
        mock_scrape.side_effect = lambda url, timeout: {
            "url": url,
            "success": True,
            "title": f"Title for {url}",
            "raw_text": "Content"
        }
        
        urls = ["http://a.com", "http://b.com"]
        callback_urls = []
        def test_callback(url):
            callback_urls.append(url)
            
        results = scraper.scrape_urls_concurrently(urls, timeout=5, status_callback=test_callback)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["url"], "http://a.com")
        self.assertEqual(results[1]["url"], "http://b.com")
        self.assertEqual(set(callback_urls), set(urls))

if __name__ == '__main__':
    unittest.main()

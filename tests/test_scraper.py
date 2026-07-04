import unittest
from unittest.mock import patch, MagicMock, mock_open
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

    @patch('config_manager.load_config')
    @patch('requests.get')
    def test_scrape_url_article(self, mock_get, mock_config):
        mock_config.return_value = {"cache_enabled": False}
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

    @patch('config_manager.load_config')
    @patch('requests.get')
    def test_scrape_url_empty_or_error(self, mock_get, mock_config):
        mock_config.return_value = {"cache_enabled": False}
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

    def test_get_cache_filepath(self):
        url = "http://example.com/test-url"
        path = scraper.get_cache_filepath(url)
        self.assertTrue(path.startswith("reports/cache"))
        self.assertTrue(path.endswith(".json"))

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_cached_url(self, mock_file, mock_makedirs):
        url = "http://test-cache.com"
        scraped_dict = {"url": url, "success": True, "title": "Cache Title"}
        
        scraper.save_cached_url(url, scraped_dict)
        mock_makedirs.assert_called_once_with("reports/cache", exist_ok=True)
        self.assertTrue(mock_file.called)

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_cached_url_valid(self, mock_file, mock_exists):
        mock_exists.return_value = True
        url = "http://test-cache.com"
        import datetime
        import json
        
        timestamp = datetime.datetime.now().isoformat()
        scraped_dict = {"url": url, "success": True, "title": "Cache Title"}
        cached_data = {
            "url": url,
            "timestamp": timestamp,
            "scraped_dict": scraped_dict
        }
        mock_file.return_value.read.return_value = json.dumps(cached_data)
        
        result = scraper.load_cached_url(url, expiration_hours=24)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Cache Title")

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_cached_url_expired(self, mock_file, mock_exists):
        mock_exists.return_value = True
        url = "http://test-cache.com"
        import datetime
        import json
        
        # Expired: 25 hours ago
        timestamp = (datetime.datetime.now() - datetime.timedelta(hours=25)).isoformat()
        scraped_dict = {"url": url, "success": True, "title": "Cache Title"}
        cached_data = {
            "url": url,
            "timestamp": timestamp,
            "scraped_dict": scraped_dict
        }
        mock_file.return_value.read.return_value = json.dumps(cached_data)
        
        result = scraper.load_cached_url(url, expiration_hours=24)
        self.assertIsNone(result)

    @patch('scraper.load_cached_url')
    @patch('scraper._perform_scrape_url')
    @patch('config_manager.load_config')
    def test_scrape_url_cache_hit(self, mock_load_config, mock_perform, mock_load_cache):
        mock_load_config.return_value = {"cache_enabled": True, "cache_expiration_hours": 24}
        mock_load_cache.return_value = {"title": "Cached Title", "success": True}
        
        # Call scrape_url
        res = scraper.scrape_url("http://example.com")
        self.assertEqual(res["title"], "Cached Title")
        
        # Verify _perform_scrape_url was NOT called
        mock_perform.assert_not_called()

    def test_parse_sitemap_xml(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
           <url>
              <loc>http://www.example.com/page1</loc>
              <lastmod>2026-01-01</lastmod>
           </url>
           <url>
              <loc>http://www.example.com/page2</loc>
           </url>
        </urlset>
        """
        urls = scraper._parse_sitemap_xml(xml_content, max_urls=5)
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], "http://www.example.com/page1")
        self.assertEqual(urls[1], "http://www.example.com/page2")

    @patch('utils.safe_request')
    def test_scan_sitemap_urls_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<url><loc>http://example.com/item</loc></url>"
        mock_request.return_value = mock_resp
        
        urls = scraper.scan_sitemap_urls("example.com")
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], "http://example.com/item")

    @patch('requests.get')
    def test_fetch_wayback_cache_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "http://web.archive.org/web/123/http://facebook.com/post"
        mock_resp.text = "<html><div id='wm-ipp'>Wayback Toolbar</div><body>Actual Post</body></html>"
        mock_get.return_value = mock_resp
        
        html = scraper._fetch_wayback_cache("http://facebook.com/post")
        self.assertEqual(html, mock_resp.text)
        
        clean = scraper._clean_wayback_html(html)
        self.assertNotIn("wm-ipp", clean)
        self.assertIn("Actual Post", clean)

    @patch('scraper._search_google_mobile')
    @patch('scraper.search_duckduckgo')
    def test_search_aggregated(self, mock_ddg, mock_google):
        mock_google.return_value = [{"title": "Google Title", "url": "http://test.com/1", "snippet": "Google"}]
        mock_ddg.return_value = [{"title": "DDG Title", "url": "http://test.com/2", "snippet": "DDG"}]
        
        results = scraper.search_aggregated("test", max_results=5)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["url"], "http://test.com/1")
        self.assertEqual(results[1]["url"], "http://test.com/2")

    @patch('scraper.scrape_url')
    def test_scrape_urls_adaptive_replenishes(self, mock_scrape):
        def mock_side_effect(url, timeout, fallback_snippet=""):
            if url == "http://a.com":
                return {"url": url, "success": False, "raw_text": "", "error": "Timeout"}
            elif url == "http://b.com":
                return {"url": url, "success": True, "title": "B", "raw_text": "Highly informative article content here."}
            elif url == "http://c.com":
                return {"url": url, "success": True, "title": "C", "raw_text": "Another rich and detailed article content."}
            return {"url": url, "success": False, "raw_text": ""}
            
        mock_scrape.side_effect = mock_side_effect
        
        candidates = [
            {"url": "http://a.com", "snippet": "A snippet"},
            {"url": "http://b.com", "snippet": "B snippet"},
            {"url": "http://c.com", "snippet": "C snippet"}
        ]
        
        results = scraper.scrape_urls_adaptive(candidates, target_count=2, timeout=5)
        
        # Verify it successfully replenished and returned the 2 rich sites (b and c)
        self.assertEqual(len(results), 2)
        urls_returned = [r["url"] for r in results]
        self.assertIn("http://b.com", urls_returned)
        self.assertIn("http://c.com", urls_returned)
        self.assertNotIn("http://a.com", urls_returned)

if __name__ == '__main__':
    unittest.main()

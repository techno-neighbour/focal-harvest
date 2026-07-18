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

    def test_parse_ssr_next_js_success(self):
        html_content = """
        <html>
          <head><title>My Next.js Article</title></head>
          <body>
            <script id="__NEXT_DATA__" type="application/json">
            {
              "props": {
                "pageProps": {
                  "post": {
                    "title": "My Next.js Article",
                    "content": "This is a very long paragraph that satisfies the minimum character count of 80 characters inside the recursive JSON parser.",
                    "details": {
                       "author": "John Doe",
                       "body": "Another long paragraph that satisfies the length limits of eighty characters to verify recursive extraction of page body content."
                    }
                  }
                }
              }
            }
            </script>
          </body>
        </html>
        """
        res = scraper._parse_html_to_scraped_dict("http://next-example.com", html_content)
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "My Next.js Article")
        self.assertEqual(len(res["paragraphs"]), 2)
        self.assertIn("This is a very long paragraph", res["paragraphs"][0])
        self.assertIn("Another long paragraph", res["paragraphs"][1])

    def test_parse_bot_blocked_failure(self):
        html_content = """
        <html>
          <head><title>Radware Bot Manager Captcha</title></head>
          <body>
            <h2>We apologize for the inconvenience...</h2>
            <p>To ensure we keep this website safe, please can you confirm you are a human by ticking the box below.</p>
          </body>
        </html>
        """
        res = scraper._parse_html_to_scraped_dict("http://blocked-site.com", html_content)
        self.assertFalse(res["success"])
        self.assertIn("Blocked by firewall", res["error"])
        self.assertEqual(len(res["paragraphs"]), 0)
        self.assertEqual(res["raw_text"], "")

    def test_get_youtube_video_id(self):
        urls = [
            ("https://www.youtube.com/watch?v=S_6DNS_z4DA", "S_6DNS_z4DA"),
            ("https://youtu.be/S_6DNS_z4DA", "S_6DNS_z4DA"),
            ("https://www.youtube.com/embed/S_6DNS_z4DA", "S_6DNS_z4DA"),
            ("https://www.youtube.com/shorts/S_6DNS_z4DA", "S_6DNS_z4DA"),
        ]
        for url, expected in urls:
            self.assertEqual(scraper._get_youtube_video_id(url), expected)

    @patch('scraper.YouTubeTranscriptApi.fetch')
    def test_scrape_youtube_transcript_success(self, mock_fetch):
        from collections import namedtuple
        Entry = namedtuple('Entry', ['text', 'start', 'duration'])
        mock_fetch.return_value = [
            Entry("Hello world", 0.0, 2.0),
            Entry("this is a test transcript", 2.0, 3.0)
        ]
        
        # Bypass config checks for cache_enabled defaults
        with patch('config_manager.load_config', return_value={"cache_enabled": False}):
            res = scraper.scrape_url("https://www.youtube.com/watch?v=S_6DNS_z4DA")
            self.assertTrue(res["success"])
            self.assertEqual(res["title"], "YouTube Video Transcript")
            self.assertEqual(res["raw_text"], "Hello world this is a test transcript")

    def test_parse_youtube_skeleton_failure(self):
        html_content = """
        <html>
          <head><title>Rick Astley - Never Gonna Give You Up - YouTube</title></head>
          <body>
            <p>How YouTube works</p>
            <p>Test new features</p>
            <p>© 2026 Google LLC</p>
          </body>
        </html>
        """
        res = scraper._parse_html_to_scraped_dict("https://www.youtube.com/watch?v=dQw4w9WgXcQ", html_content)
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "YouTube Transcript Unavailable (PoToken required)")
        self.assertEqual(len(res["paragraphs"]), 0)
        self.assertEqual(res["raw_text"], "")

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

    @patch('utils.safe_request')
    def test_scan_sitemap_urls_via_robots_txt(self, mock_request):
        mock_robots_resp = MagicMock()
        mock_robots_resp.status_code = 200
        mock_robots_resp.text = "User-agent: *\nDisallow: /private\nSitemap: https://example.com/custom_sitemap.xml"
        
        mock_sitemap_resp = MagicMock()
        mock_sitemap_resp.status_code = 200
        mock_sitemap_resp.text = "<url><loc>http://example.com/item-via-robots</loc></url>"
        
        mock_request.side_effect = [mock_robots_resp, mock_sitemap_resp]
        
        urls = scraper.scan_sitemap_urls("example.com")
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], "http://example.com/item-via-robots")

    def test_parse_sitemap_xml_filters_categories(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
           <url>
              <loc>http://www.example.com/posts/my-story</loc>
           </url>
           <url>
              <loc>http://www.example.com/tagged/simian-army</loc>
           </url>
           <url>
              <loc>http://www.example.com/@username</loc>
           </url>
           <url>
              <loc>http://www.example.com/posts/another-story</loc>
           </url>
        </urlset>
        """
        urls = scraper._parse_sitemap_xml(xml_content, max_urls=5)
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], "http://www.example.com/posts/my-story")
        self.assertEqual(urls[1], "http://www.example.com/posts/another-story")

    @patch('utils.safe_request')
    def test_scan_sitemap_index_resolution(self, mock_request):
        mock_robots = MagicMock()
        mock_robots.status_code = 404
        
        mock_index = MagicMock()
        mock_index.status_code = 200
        mock_index.text = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
           <sitemap>
              <loc>http://example.com/sitemap-tags.xml</loc>
           </sitemap>
           <sitemap>
              <loc>http://example.com/sitemap-posts.xml</loc>
           </sitemap>
        </sitemapindex>
        """
        
        mock_posts_sitemap = MagicMock()
        mock_posts_sitemap.status_code = 200
        mock_posts_sitemap.text = "<url><loc>http://example.com/story-1</loc></url>"
        
        mock_request.side_effect = [mock_robots, mock_index, mock_posts_sitemap]
        
        urls = scraper.scan_sitemap_urls("example.com")
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], "http://example.com/story-1")
        
        call_args = mock_request.call_args_list
        self.assertEqual(call_args[2][0][1], "http://example.com/sitemap-posts.xml")

    @patch('time.sleep')
    @patch('requests.get')
    def test_fetch_wayback_cache_success(self, mock_get, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "http://web.archive.org/web/123/http://facebook.com/post"
        mock_resp.text = "<html><div id='wm-ipp'>Wayback Toolbar</div><body>Actual Post</body></html>"
        mock_get.return_value = mock_resp
        
        html = scraper._fetch_wayback_cache("http://facebook.com/post")
        self.assertEqual(html, "<html><body>Actual Post</body></html>")
        
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

    @patch('utils.safe_request')
    def test_search_duckduckgo_lite_fallback_non_200(self, mock_request):
        # Mocks first request returning 500 (HTML DDG)
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        
        # Mocks second request returning 200 (Lite DDG) with results table
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.text = """
        <table>
          <tr>
            <td><a class="result-link" href="https://duckduckgo.com/l/?uddg=http%3A%2F%2Ftest.com&rut=456">Test Lite Title</a></td>
          </tr>
          <tr>
            <td class="result-snippet">Test Lite Snippet Description.</td>
          </tr>
        </table>
        """
        mock_request.side_effect = [mock_resp_500, mock_resp_200]
        
        results = scraper.search_duckduckgo("query", max_results=2)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Test Lite Title")
        self.assertEqual(results[0]["url"], "http://test.com")
        self.assertEqual(results[0]["snippet"], "Test Lite Snippet Description.")

    @patch('time.sleep')
    @patch('requests.get')
    def test_fetch_wayback_cache_failures(self, mock_get, mock_sleep):
        # 1. Non-200 HTTP code
        mock_resp_404 = MagicMock()
        mock_resp_404.status_code = 404
        mock_get.return_value = mock_resp_404
        self.assertIsNone(scraper._fetch_wayback_cache("http://site.com"))

        # 2. Connection Exception raised
        mock_get.side_effect = Exception("Wayback is down")
        self.assertIsNone(scraper._fetch_wayback_cache("http://site.com"))

    @patch('utils.safe_request')
    def test_scan_sitemap_urls_robots_txt_failures(self, mock_request):
        # Mock robots.txt failure and guessing sitemap failure
        mock_resp_404 = MagicMock()
        mock_resp_404.status_code = 404
        mock_request.return_value = mock_resp_404
        
        urls = scraper.scan_sitemap_urls("site.com", max_urls=5)
        self.assertEqual(len(urls), 0)

    def test_clean_wayback_html(self):
        dirty_html = """
        <html>
          <!-- BEGIN WAYBACK TOOLBAR INSERT -->
          <div id="wm-ipp-base">Toolbar banner here</div>
          <!-- END WAYBACK TOOLBAR INSERT -->
          <body>Real Content</body>
        </html>
        """
        cleaned = scraper._clean_wayback_html(dirty_html)
        self.assertNotIn("wm-ipp-base", cleaned)
        self.assertIn("Real Content", cleaned)

    def test_custom_parser_plugin_routing(self):
        # Define mock custom parser function
        def mock_parser(html_text, url):
            return {
                "title": "Custom Plugin Parsed Title",
                "raw_text": "Parsed custom paragraph text.",
                "headings": [{"level": 1, "text": "Custom Heading"}],
                "paragraphs": ["Parsed custom paragraph text."]
            }
            
        # Register in PLUGIN_REGISTRY
        scraper.PLUGIN_REGISTRY["testplugin.com"] = mock_parser
        
        try:
            # Test direct routing
            res = scraper._parse_html_to_scraped_dict("http://testplugin.com/page", "<html><body>Raw HTML</body></html>")
            self.assertTrue(res["success"])
            self.assertEqual(res["title"], "Custom Plugin Parsed Title")
            self.assertEqual(res["raw_text"], "Parsed custom paragraph text.")
            self.assertEqual(res["headings"][0]["text"], "Custom Heading")
            self.assertEqual(res["paragraphs"][0], "Parsed custom paragraph text.")
            
            # Test subdomain routing (e.g. sub.testplugin.com)
            res_sub = scraper._parse_html_to_scraped_dict("http://sub.testplugin.com/page", "<html>Raw HTML</html>")
            self.assertTrue(res_sub["success"])
            self.assertEqual(res_sub["title"], "Custom Plugin Parsed Title")
            
            # Test bot blocker checks remain active on plugin parsed output
            def mock_blocker_parser(html_text, url):
                return {
                    "title": "Access Denied",
                    "raw_text": "attention required | cloudflare ray ID",
                    "headings": [],
                    "paragraphs": []
                }
            scraper.PLUGIN_REGISTRY["blockedplugin.com"] = mock_blocker_parser
            res_blocked = scraper._parse_html_to_scraped_dict("http://blockedplugin.com/page", "<html>Raw HTML</html>")
            self.assertFalse(res_blocked["success"])
            self.assertIn("Blocked by firewall", res_blocked["error"])
            
        finally:
            # Clean up the registry entries
            if "testplugin.com" in scraper.PLUGIN_REGISTRY:
                del scraper.PLUGIN_REGISTRY["testplugin.com"]
            if "blockedplugin.com" in scraper.PLUGIN_REGISTRY:
                del scraper.PLUGIN_REGISTRY["blockedplugin.com"]

    def test_hackernews_plugin_parsing(self):
        from std_plugins import hackernews
        
        # 1. Test thread parser
        thread_html = """
        <html>
          <span class="titleline"><a href="http://link.com">Test Post Thread</a></span>
          <table>
            <tr class="comtr">
              <td>
                <img src="s.gif" width="40" />
                <a class="hnuser" href="user?id=tester">tester</a>
                <div class="comment">
                  This is comment text.
                  <div class="reply">reply link</div>
                </div>
              </td>
            </tr>
          </table>
        </html>
        """
        res_thread = hackernews.parse(thread_html, "https://news.ycombinator.com/item?id=123")
        self.assertEqual(res_thread["title"], "Hacker News: Test Post Thread")
        self.assertIn("* **@tester**: This is comment text.", res_thread["raw_text"])
        self.assertNotIn("reply link", res_thread["raw_text"])
        
        # 2. Test listing parser (like /shownew)
        listing_html = """
        <table>
          <tr class="athing">
            <td><span class="titleline"><a href="http://show-post.com">Show HN: Cool Project</a></span></td>
          </tr>
          <tr>
            <td class="subtext">
              <span class="score">99 points</span>
              <a href="item?id=999">5 comments</a>
            </td>
          </tr>
        </table>
        """
        res_list = hackernews.parse(listing_html, "https://news.ycombinator.com/shownew")
        self.assertEqual(res_list["title"], "Hacker News - SHOWNEW")
        self.assertIn("* **Show HN: Cool Project**", res_list["raw_text"])
        self.assertIn("Stats: 99 points | 5 comments", res_list["raw_text"])

    @patch('utils.safe_request')
    def test_reddit_plugin_parsing(self, mock_request):
        from std_plugins import reddit
        
        # 1. Mock successful API response
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = [
            {
                "data": {
                    "children": [
                        {
                            "data": {
                                "title": "Scraper Framework Release",
                                "author": "op_author",
                                "subreddit_name_prefixed": "r/programming",
                                "selftext": "Check out this cool new tool."
                            }
                        }
                    ]
                }
            },
            {
                "data": {
                    "children": [
                        {
                            "kind": "t1",
                            "data": {
                                "author": "reply_user_1",
                                "body": "This is great!\nLove it.",
                                "distinguished": None,
                                "replies": {
                                    "data": {
                                        "children": [
                                            {
                                                "kind": "t1",
                                                "data": {
                                                    "author": "reply_user_2",
                                                    "body": "Agree.",
                                                    "distinguished": None,
                                                    "replies": ""
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        {
                            "kind": "t1",
                            "data": {
                                "author": "automoderator",
                                "body": "Rules here.",
                                "distinguished": "moderator",
                                "replies": ""
                            }
                        }
                    ]
                }
            }
        ]
        mock_request.return_value = mock_resp_200
        
        res = reddit.parse("html_stub", "https://www.reddit.com/r/programming/comments/123/scraper_release/")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Reddit: Scraper Framework Release (r/programming)")
        self.assertIn("Posted by: @op_author", res["raw_text"])
        self.assertIn("Check out this cool new tool.", res["raw_text"])
        
        # Verify comment parsing and nested indentation
        self.assertIn("* **@reply_user_1**: This is great! Love it.", res["raw_text"])
        self.assertIn("    * **@reply_user_2**: Agree.", res["raw_text"])
        # Verify moderator auto-comment filter is applied
        self.assertNotIn("automoderator", res["raw_text"])

        # 2. Mock API request failure (HTTP 403 Forbidden)
        mock_resp_403 = MagicMock()
        mock_resp_403.status_code = 403
        mock_request.return_value = mock_resp_403
        
        res_fail = reddit.parse("html_stub", "https://www.reddit.com/r/programming/comments/123/scraper_release/")
        self.assertFalse(res_fail["success"])
        self.assertIn("Failed to retrieve Reddit JSON feed", res_fail["raw_text"])

        # 3. Mock invalid payload structure
        mock_resp_invalid = MagicMock()
        mock_resp_invalid.status_code = 200
        mock_resp_invalid.json.return_value = {"error": "bad format"}
        mock_request.return_value = mock_resp_invalid
        
        res_invalid = reddit.parse("html_stub", "https://www.reddit.com/r/programming/comments/123/scraper_release/")
        self.assertFalse(res_invalid["success"])
        self.assertIn("Unsupported Reddit layout page.", res_invalid["raw_text"])

    def test_stackoverflow_plugin_parsing(self):
        from std_plugins import stackoverflow
        
        html_content = """
        <html>
          <h1 id="question-header">How to write Python unit tests?</h1>
          <div id="question">
            <div class="js-post-body">
              This is question details.
              <pre><code>import unittest
class Test(unittest.TestCase):
    pass</code></pre>
              Use <code>unittest.main()</code>.
            </div>
          </div>
          <div id="answers">
            <div class="answer" id="answer-1">
              <div class="js-vote-count" data-value="10">10</div>
              <div class="js-post-body">Try this simple solution.</div>
            </div>
            <div class="answer accepted-answer" id="answer-2">
              <div class="js-vote-count" data-value="5">5</div>
              <div class="js-accepted-answer-indicator">Accepted</div>
              <div class="js-post-body">This is the best solution with <code>mock</code>.</div>
            </div>
          </div>
        </html>
        """
        res = stackoverflow.parse(html_content, "https://stackoverflow.com/questions/12345/how-to-write-tests")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Stack Overflow: How to write Python unit tests?")
        self.assertIn("Question Details", res["headings"][0]["text"])
        self.assertIn("Answers (2)", res["headings"][1]["text"])
        
        # Verify code block fences
        self.assertIn("```\nimport unittest\nclass Test(unittest.TestCase):\n    pass\n```", res["raw_text"])
        # Verify inline code backticks
        self.assertIn("`unittest.main()`", res["raw_text"])
        
        # Verify sorting order (Accepted answer is index 1, but sorted to top index 0)
        self.assertIn("### Answer 1 [ACCEPTED ANSWER] (Score: 5)", res["raw_text"])
        self.assertIn("This is the best solution with `mock`.", res["raw_text"])
        self.assertIn("### Answer 2 (Score: 10)", res["raw_text"])
        self.assertIn("Try this simple solution.", res["raw_text"])

    @patch('utils.safe_request')
    def test_reddit_listing_json_parsing(self, mock_request):
        from std_plugins import reddit
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "title": "Cool Open Source Project",
                            "url": "/r/opensource/comments/123/cool_project",
                            "author": "dev_user",
                            "score": 150,
                            "num_comments": 25,
                            "subreddit_name_prefixed": "r/opensource"
                        }
                    }
                ]
            }
        }
        mock_request.return_value = mock_resp
        
        res = reddit.parse("html_stub", "https://www.reddit.com/r/opensource/")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Reddit Listing: https://www.reddit.com/r/opensource/")
        self.assertIn("Cool Open Source Project", res["raw_text"])
        self.assertIn("Score: 150 | Comments: 25", res["raw_text"])
        self.assertIn("https://reddit.com/r/opensource/comments/123/cool_project", res["raw_text"])

    @patch('utils.safe_request')
    def test_reddit_listing_html_parsing(self, mock_safe):
        # Force JSON fetch failure to trigger HTML fallback parsing
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_safe.return_value = mock_resp

        from std_plugins import reddit
        
        html_content = """
        <html>
          <div class="linkarea">
            <div class="thing link" id="thing_1">
              <p class="title">
                <a class="title" href="https://opensource.org/blog/123">Celebrating Maintainers</a>
              </p>
              <p class="tagline">
                submitted by <a class="author">osi_author</a>
              </p>
              <div class="score">320</div>
              <a class="comments" href="/r/opensource/comments/123/celebrating">15 comments</a>
            </div>
          </div>
        </html>
        """
        res = reddit.parse(html_content, "https://old.reddit.com/r/opensource/")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Reddit Listing: https://old.reddit.com/r/opensource/")
        self.assertIn("Celebrating Maintainers", res["raw_text"])
        self.assertIn("Score: 320 | 15 comments", res["raw_text"])
        self.assertIn("Posted by: @osi_author", res["raw_text"])

    @patch('utils.safe_request')
    def test_reddit_redesign_html_parsing(self, mock_safe):
        # Force JSON fetch failure to trigger HTML fallback parsing
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_safe.return_value = mock_resp

        from std_plugins import reddit
        
        html_content = """
        <html>
          <h1>Eli5-What does a stack overflow mean?</h1>
          <a href="/r/explainlikeimfive/">r/explainlikeimfive</a>
          <a href="/user/what_r_u_casul/">what_r_u_casul</a>
          <div data-testid="post-container">
            <p>This is the post description paragraph.</p>
          </div>
          <div class="comment-tree">
            <div id="t1_c1" style="padding-left:16px">
              <a href="/user/Laerson123/">Laerson123</a>
              <div data-testid="comment">Stack is a data structure.</div>
            </div>
            <div id="t1_c2" style="padding-left:32px">
              <a href="/user/bremen_/">bremen_</a>
              <div data-testid="comment">So if you only have room...</div>
            </div>
          </div>
        </html>
        """
        res = reddit.parse(html_content, "https://www.reddit.com/r/explainlikeimfive/comments/123/eli5/")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Reddit: Eli5-What does a stack overflow mean? (r/explainlikeimfive)")
        self.assertIn("This is the post description paragraph.", res["raw_text"])
        # Level 1 indentation (padding 16px -> depth 1 -> 4 spaces)
        self.assertIn("    * **@Laerson123**: Stack is a data structure.", res["raw_text"])
        # Level 2 indentation (padding 32px -> depth 2 -> 8 spaces)
        self.assertIn("        * **@bremen_**: So if you only have room...", res["raw_text"])

    def test_github_thread_parsing(self):
        from std_plugins import github
        
        html_content = """
        <html>
          <span class="js-issue-title">Issues with setup script</span>
          <div class="TimelineItem">
            <a class="author" href="/octocat">octocat</a>
            <div class="comment-body">
              This is the main post body containing inline `setup` code.
            </div>
          </div>
          <div class="TimelineItem">
            <a class="author" href="/tester">tester</a>
            <div class="comment-body">
              Please try running:
              <pre><code>python setup.py install</code></pre>
            </div>
          </div>
        </html>
        """
        res = github.parse(html_content, "https://github.com/octocat/hello-world/issues/1")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "GitHub Issue: Issues with setup script in octocat/hello-world")
        self.assertIn("This is the main post body containing inline `setup` code.", res["raw_text"])
        self.assertIn("* **@tester**: Please try running:", res["raw_text"])
        self.assertIn("python setup.py install", res["raw_text"])

    def test_github_listing_parsing(self):
        from std_plugins import github
        
        html_content = """
        <html>
          <div class="js-issue-row Box-row">
            <a class="markdown-title" href="/octocat/hello-world/issues/2">Documentation Bug</a>
            <span class="IssueLabel">bug</span>
            <a class="author" href="/octocat">octocat</a>
            <a aria-label="3 comments">3</a>
          </div>
        </html>
        """
        res = github.parse(html_content, "https://github.com/octocat/hello-world/issues")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "GitHub Issues Listing: octocat/hello-world")
        self.assertIn("**Documentation Bug** [bug]", res["raw_text"])
        self.assertIn("Posted by: @octocat", res["raw_text"])
        self.assertIn("Link: https://github.com/octocat/hello-world/issues/2", res["raw_text"])
        self.assertIn("Status: 3 comments", res["raw_text"])

    def test_github_repo_home_parsing(self):
        from std_plugins import github
        
        html_content = """
        <html>
          <p class="f4">The Web framework for perfectionists with deadlines.</p>
          <div class="react-directory-row">
            <a href="/django/django/blob/main/LICENSE">LICENSE</a>
          </div>
          <div class="react-directory-row">
            <a href="/django/django/tree/main/django">django</a>
          </div>
          <div class="markdown-body">
            <h1>Django</h1>
            <p>Django is a high-level Python web framework.</p>
            <pre><code>pip install Django</code></pre>
          </div>
        </html>
        """
        res = github.parse(html_content, "https://github.com/django/django")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "GitHub Repository: django/django")
        self.assertIn("Description: The Web framework for perfectionists with deadlines.", res["raw_text"])
        self.assertIn("- LICENSE", res["raw_text"])
        self.assertIn("- django", res["raw_text"])
        self.assertIn("Django is a high-level Python web framework.", res["raw_text"])
        self.assertIn("```\npip install Django\n```", res["raw_text"])

    @patch('utils.safe_request')
    def test_github_blob_parsing(self, mock_request):
        from std_plugins import github
        
        # 1. Test raw fetch success
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Hello Raw Content File"
        mock_request.return_value = mock_resp
        
        res = github.parse("html_content", "https://github.com/octocat/hello-world/blob/main/README.md")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "GitHub File: README.md in octocat/hello-world")
        self.assertIn("Hello Raw Content File", res["raw_text"])
        
        # 2. Test HTML fallback (when raw fetch fails)
        mock_resp.status_code = 404
        html_fallback = """
        <html>
          <div class="blob-wrapper">
            <div class="blob-code">import math</div>
            <div class="blob-code">print(math.pi)</div>
          </div>
        </html>
        """
        res = github.parse(html_fallback, "https://github.com/octocat/hello-world/blob/main/main.py")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "GitHub File: main.py in octocat/hello-world")
        self.assertIn("import math\nprint(math.pi)", res["raw_text"])

    def test_github_tree_parsing(self):
        from std_plugins import github
        
        html_content = """
        <html>
          <div class="react-directory-row">
            <a href="/django/django/blob/main/django/db">db</a>
          </div>
          <div class="react-directory-row">
            <a href="/django/django/blob/main/django/forms">forms</a>
          </div>
        </html>
        """
        res = github.parse(html_content, "https://github.com/django/django/tree/main/django")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "GitHub Directory: django in django/django (main)")
        self.assertIn("- db", res["raw_text"])
        self.assertIn("- forms", res["raw_text"])

    def test_arxiv_abstract_parsing(self):
        from std_plugins import arxiv
        
        html_content = """
        <html>
          <h1 class="title mathjax"><span class="descriptor">Title:</span>Attention Is All You Need</h1>
          <div class="authors">
            <span class="descriptor">Authors:</span>
            <a href="/search?query=Vaswani">Ashish Vaswani</a>, 
            <a href="/search?query=Shazeer">Noam Shazeer</a>
          </div>
          <blockquote class="abstract mathjax">
            <span class="descriptor">Abstract:</span>We propose a new simple network architecture, the Transformer.
          </blockquote>
          <div class="dateline">Submitted on 12 Jun 2017</div>
          <td class="tablecell subjects"><span class="primary-subject">Computation and Language (cs.CL)</span></td>
        </html>
        """
        res = arxiv.parse(html_content, "https://arxiv.org/abs/1706.03762")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "arXiv Abstract: Attention Is All You Need (1706.03762)")
        self.assertIn("Authors: Ashish Vaswani, Noam Shazeer", res["raw_text"])
        self.assertIn("Abstract:\nWe propose a new simple network architecture, the Transformer.", res["raw_text"])
        self.assertIn("Date: Submitted on 12 Jun 2017", res["raw_text"])
        self.assertIn("PDF Link: https://arxiv.org/pdf/1706.03762", res["raw_text"])

    def test_arxiv_listing_parsing(self):
        from std_plugins import arxiv
        
        html_content = """
        <html>
          <li class="arxiv-result">
            <div class="list-title"><a href="https://arxiv.org/abs/1706.03762">arXiv:1706.03762</a> [<a href="https://arxiv.org/pdf/1706.03762">pdf</a>]</div>
            <p class="title">Attention Is All You Need</p>
            <p class="authors"><span>Authors:</span><a href="/search?query=Vaswani">Ashish Vaswani</a></p>
            <p class="abstract"><span>Abstract:</span>We introduce the Transformer.</p>
          </li>
        </html>
        """
        res = arxiv.parse(html_content, "https://arxiv.org/search/?query=transformer")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "arXiv Search Results Listing")
        self.assertIn("* **Attention Is All You Need**", res["raw_text"])
        self.assertIn("Authors: Ashish Vaswani", res["raw_text"])
        self.assertIn("Abstract: We introduce the Transformer.", res["raw_text"])
        self.assertIn("Link: https://arxiv.org/abs/1706.03762 | PDF: https://arxiv.org/pdf/1706.03762", res["raw_text"])

    def test_pubmed_abstract_parsing(self):
        from std_plugins import pubmed
        
        html_content = """
        <html>
          <h1 class="heading-title">Hypusinated EIF5A as a drug target</h1>
          <div class="authors-list">
            <span class="authors-list-item">
              <a class="full-name" href="/?term=Kaiser+A">Annette Kaiser</a>
              <sup class="affiliation-links"><a href="#full-view-affiliation-1">1</a></sup>
            </span>
          </div>
          <div class="affiliations">
            <ul class="item-list">
              <li id="full-view-affiliation-1"><sup>1</sup> Medical Research Centre, Essen, Germany.</li>
            </ul>
          </div>
          <div class="abstract-content" id="eng-abstract">
            <p>Cancer drug resistance is an emerging problem.</p>
          </div>
          <a class="id-link" data-ga-action="DOI">10.1007/s00726-021-03120-6</a>
        </html>
        """
        res = pubmed.parse(html_content, "https://pubmed.ncbi.nlm.nih.gov/35000000/")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "PubMed Abstract: Hypusinated EIF5A as a drug target (PMID: 35000000)")
        self.assertIn("Authors: Annette Kaiser", res["raw_text"])
        self.assertIn("DOI: 10.1007/s00726-021-03120-6", res["raw_text"])
        self.assertIn("- Medical Research Centre, Essen, Germany.", res["raw_text"])
        self.assertIn("Abstract:\nCancer drug resistance is an emerging problem.", res["raw_text"])

    def test_pubmed_listing_parsing(self):
        from std_plugins import pubmed
        
        html_content = """
        <html>
          <div class="doc-sum">
            <a class="doc-sum-title" href="/35000000/">Hypusinated EIF5A</a>
            <span class="doc-sum-authors">Annette Kaiser</span>
            <div class="doc-sum-snippet">Cancer drug resistance...</div>
            <span class="doc-sum-pmid">35000000</span>
          </div>
        </html>
        """
        res = pubmed.parse(html_content, "https://pubmed.ncbi.nlm.nih.gov/?term=hypusine")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "PubMed Search Results Listing")
        self.assertIn("* **Hypusinated EIF5A** (PMID: 35000000)", res["raw_text"])
        self.assertIn("Authors: Annette Kaiser", res["raw_text"])
        self.assertIn("Snippet: Cancer drug resistance...", res["raw_text"])
        self.assertIn("Link: https://pubmed.ncbi.nlm.nih.gov/35000000/", res["raw_text"])

    def test_google_scholar_listing_parsing(self):
        from std_plugins import google_scholar
        
        html_content = """
        <html>
          <div class="gs_r gs_or gs_scl">
            <div class="gs_or_ggside"><a href="https://arxiv.org/pdf/1706.03762">PDF</a></div>
            <h3 class="gs_rt"><a href="https://arxiv.org/abs/1706.03762">Attention Is All You Need</a></h3>
            <div class="gs_a">A Vaswani, N Shazeer - NeurIPS, 2017</div>
            <div class="gs_rs">We propose a new simple network architecture...</div>
            <div class="gs_fl">
              <a href="/scholar?cites=1234">Cited by 115000</a>
            </div>
          </div>
        </html>
        """
        res = google_scholar.parse(html_content, "https://scholar.google.com/scholar?q=attention")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Google Scholar Search Results")
        self.assertIn("* **Attention Is All You Need**", res["raw_text"])
        self.assertIn("Metadata: A Vaswani, N Shazeer - NeurIPS, 2017", res["raw_text"])
        self.assertIn("Link: https://arxiv.org/abs/1706.03762 | PDF: https://arxiv.org/pdf/1706.03762", res["raw_text"])
        self.assertIn("Status: Cited by 115000", res["raw_text"])

    def test_google_scholar_profile_parsing(self):
        from std_plugins import google_scholar
        
        html_content = """
        <html>
          <div id="gsc_prf_in">Jeff Dean</div>
          <div class="gsc_prf_il">Google Senior Fellow</div>
          <table id="gsc_rsb_table">
            <tr><th></th><th>All</th></tr>
            <tr><td>Citations</td><td>200000</td></tr>
          </table>
          <tr class="gsc_a_tr">
            <td class="gsc_a_t">
              <a class="gsc_a_at" href="/citations?view_op=view_citation&citation_for_view=1">MapReduce</a>
              <div class="gs_gray">J Dean, S Ghemawat</div>
              <div class="gs_gray">OSDI, 2004</div>
            </td>
            <td class="gsc_a_c"><a class="gsc_a_ac">50000</a></td>
            <td class="gsc_a_y"><span class="gsc_a_h">2004</span></td>
          </tr>
        </html>
        """
        res = google_scholar.parse(html_content, "https://scholar.google.com/citations?user=yP7u3s4AAAAJ")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Google Scholar Profile: Jeff Dean")
        self.assertIn("Affiliation: Google Senior Fellow", res["raw_text"])
        self.assertIn("- Citations: 200000", res["raw_text"])
        self.assertIn("* **MapReduce** (2004)", res["raw_text"])
        self.assertIn("Authors: J Dean, S Ghemawat", res["raw_text"])
        self.assertIn("Journal: OSDI, 2004", res["raw_text"])
        self.assertIn("Citations: 50000", res["raw_text"])

    def test_medium_article_parsing(self):
        from std_plugins import medium
        
        html_content = """
        <html>
          <article>
            <h1>How to scrape Medium</h1>
            <p>This is a guide on scraping Medium posts.</p>
            <blockquote>Keep it simple.</blockquote>
            <pre>pip install beautifulsoup4</pre>
            <div class="signup-modal-wrapper">Sign up for more stories</div>
          </article>
        </html>
        """
        res = medium.parse(html_content, "https://medium.com/scrappy-capybara/how-to-scrape-medium-1234abcd")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Medium Article: How to scrape Medium")
        self.assertIn("This is a guide on scraping Medium posts.", res["raw_text"])
        self.assertIn("> Keep it simple.", res["raw_text"])
        self.assertIn("```\npip install beautifulsoup4\n```", res["raw_text"])
        self.assertNotIn("Sign up for more stories", res["raw_text"])

    def test_substack_article_parsing(self):
        from std_plugins import substack
        
        html_content = """
        <html>
          <h1 class="post-title">The Engineering Career Ladder</h1>
          <h3 class="subtitle">A detailed breakdown</h3>
          <a class="post-author-name">Gergely Orosz</a>
          <div class="available-content">
            <p>Career paths in tech are expanding.</p>
            <div class="subscription-widget-wrap">
              <form>Subscribe to this newsletter</form>
            </div>
          </div>
        </html>
        """
        res = substack.parse(html_content, "https://pragmaticengineer.substack.com/p/engineering-career-paths")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Substack: The Engineering Career Ladder")
        self.assertIn("Subtitle: A detailed breakdown", res["raw_text"])
        self.assertIn("Author: Gergely Orosz", res["raw_text"])
        self.assertIn("Career paths in tech are expanding.", res["raw_text"])
        self.assertNotIn("Subscribe to this newsletter", res["raw_text"])

    def test_wikipedia_article_parsing(self):
        from std_plugins import wikipedia
        
        html_content = """
        <html>
          <h1 id="firstHeading">Superconductivity</h1>
          <div class="mw-parser-output">
            <div class="hatnote">This article is about the physical property. For other uses, see...</div>
            <table class="infobox">Info box details</table>
            <p>Superconductivity is a physical property<sup class="reference">[1]</sup>.</p>
            <h2>Overview<span class="mw-editsection">[edit]</span></h2>
            <p>It was discovered by Heike Kamerlingh Onnes.</p>
          </div>
        </html>
        """
        res = wikipedia.parse(html_content, "https://en.wikipedia.org/wiki/Superconductivity")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Wikipedia: Superconductivity")
        self.assertIn("Superconductivity is a physical property.", res["raw_text"])
        self.assertIn("## Overview", res["raw_text"])
        self.assertNotIn("[edit]", res["raw_text"])
        self.assertNotIn("[1]", res["raw_text"])
        self.assertNotIn("This article is about", res["raw_text"])
        self.assertNotIn("Info box details", res["raw_text"])

    def test_quora_article_parsing(self):
        from std_plugins import quora
        
        html_content = """
        <html>
          <h1 class="q-title">What is superconductivity?</h1>
          <div class="answer_content">
            <a href="/profile/John-Doe">John Doe</a>
            <span class="credential">PhD in Condensed Matter Physics</span>
            <div class="answer_text">
              <p class="q-text">Superconductivity is a zero-resistance state.</p>
            </div>
          </div>
        </html>
        """
        res = quora.parse(html_content, "https://www.quora.com/What-is-superconductivity")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Quora: What is superconductivity?")
        self.assertIn("### Answer by John Doe (PhD in Condensed Matter Physics)", res["raw_text"])
        self.assertIn("Superconductivity is a zero-resistance state.", res["raw_text"])

        # Test failure on empty answers
        empty_html = "<html><h1>What is superconductivity?</h1></html>"
        res_empty = quora.parse(empty_html, "https://www.quora.com/What-is-superconductivity")
        self.assertFalse(res_empty["success"])

    def test_yahoo_finance_quote_parsing(self):
        from std_plugins import yahoo_finance
        
        html_content = """
        <html>
          <h1>Tesla, Inc. (TSLA)</h1>
          <fin-streamer data-field="regularMarketPrice">180.57</fin-streamer>
          <fin-streamer data-field="regularMarketChange">-2.10</fin-streamer>
          <fin-streamer data-field="regularMarketChangePercent">-1.15%</fin-streamer>
          <table>
            <tr><td>Market Cap</td><td>580B</td></tr>
            <tr><td>PE Ratio</td><td>65.4</td></tr>
          </table>
        </html>
        """
        res = yahoo_finance.parse(html_content, "https://finance.yahoo.com/quote/TSLA")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Yahoo Finance Quote: Tesla, Inc. (TSLA)")
        self.assertIn("Price: 180.57 (-2.10 / -1.15%)", res["raw_text"])
        self.assertIn("| Market Cap | 580B |", res["raw_text"])
        self.assertIn("| PE Ratio | 65.4 |", res["raw_text"])

    def test_yahoo_finance_news_parsing(self):
        from std_plugins import yahoo_finance
        
        html_content = """
        <html>
          <h1>Tesla Stock Slides</h1>
          <div class="caas-body">
            <p>Tesla shares fell on Monday due to production issues.</p>
            <div class="ad-wrapper">Fake Ad Banner</div>
          </div>
        </html>
        """
        res = yahoo_finance.parse(html_content, "https://finance.yahoo.com/news/tesla-stock-slides-1234.html")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Yahoo News: Tesla Stock Slides")
        self.assertIn("Tesla shares fell on Monday due to production issues.", res["raw_text"])
        self.assertNotIn("Fake Ad Banner", res["raw_text"])

    def test_sec_gov_filing_parsing(self):
        from std_plugins import sec_gov
        
        html_content = """
        <html>
          <title>Apple Inc. 10-K Filing</title>
          <p>Item 1. Business</p>
          <p>Apple Inc. designs, manufactures and markets smartphones.</p>
          <table>
            <tr><th>Financial Item</th><th>2023</th></tr>
            <tr><td>Total Revenue</td><td>383B</td></tr>
          </table>
        </html>
        """
        res = sec_gov.parse(html_content, "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "SEC EDGAR: Apple Inc. 10-K Filing")
        self.assertIn("## Item 1. Business", res["raw_text"])
        self.assertIn("Apple Inc. designs, manufactures and markets smartphones.", res["raw_text"])
        self.assertIn("| Financial Item | 2023 |", res["raw_text"])
        self.assertIn("| Total Revenue | 383B |", res["raw_text"])

    def test_readthedocs_article_parsing(self):
        from std_plugins import readthedocs
        
        html_content = """
        <html>
          <div role="main" class="document">
            <nav class="wy-nav-side">Sidebar links</nav>
            <h1>Requests Documentation</h1>
            <p>Requests is an elegant HTTP library.</p>
            <div class="admonition note">
              <p class="admonition-title">Note</p>
              <p>Always use a timeout.</p>
            </div>
            <div class="highlight-python"><pre>import requests</pre></div>
          </div>
        </html>
        """
        res = readthedocs.parse(html_content, "https://requests.readthedocs.io/en/latest/")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Documentation: Requests Documentation")
        self.assertIn("Requests is an elegant HTTP library.", res["raw_text"])
        self.assertIn("> **Note**: Always use a timeout.", res["raw_text"])
        self.assertIn("```python\nimport requests\n```", res["raw_text"])
        self.assertNotIn("Sidebar links", res["raw_text"])

    def test_dev_to_article_parsing(self):
        from std_plugins import dev_to
        
        html_content = """
        <html>
          <h1 class="crayons-article__title">Building a CLI tool</h1>
          <div class="spec-author-name">Saurabh</div>
          <div id="article-body" class="crayons-article__body">
            <p>Python makes CLI development fast.</p>
            <div class="crayons-article__reactions">Likes: 120</div>
            <pre class="highlight"><code class="language-python">print("Hello")</code></pre>
          </div>
        </html>
        """
        res = dev_to.parse(html_content, "https://dev.to/saurabh/building-a-cli-tool-in-python-1234")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Dev.to: Building a CLI tool")
        self.assertIn("Author: Saurabh", res["raw_text"])
        self.assertIn("Python makes CLI development fast.", res["raw_text"])
        self.assertIn("```python\nprint(\"Hello\")\n```", res["raw_text"])
        self.assertNotIn("Likes: 120", res["raw_text"])

    def test_amazon_product_parsing(self):
        from std_plugins import amazon
        
        html_content = """
        <html>
          <span id="productTitle">M1 MacBook Air</span>
          <span class="apexPriceToPay"><span class="a-offscreen">$999.00</span></span>
          <span class="a-star-4-5" title="4.7 out of 5 stars">4.7 out of 5 stars</span>
          <span id="acrCustomerReviewText">15000 ratings</span>
          <div id="feature-bullets">
            <li class="a-list-item">Apple-designed M1 chip</li>
          </div>
          <div id="prodDetails">
            <table>
              <tr><td>ASIN</td><td>B08N5LNXC5</td></tr>
              <tr><td>Manufacturer</td><td>Apple</td></tr>
            </table>
          </div>
        </html>
        """
        res = amazon.parse(html_content, "https://www.amazon.com/dp/B08N5LNXC5")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Amazon Product: M1 MacBook Air")
        self.assertIn("Price: $999.00 | Rating: 4.7 out of 5 stars (15000 ratings)", res["raw_text"])
        self.assertIn("* Apple-designed M1 chip", res["raw_text"])
        self.assertIn("| ASIN | B08N5LNXC5 |", res["raw_text"])
        self.assertIn("| Manufacturer | Apple |", res["raw_text"])

    def test_amazon_search_parsing(self):
        from std_plugins import amazon
        
        html_content = """
        <html>
          <div data-component-type="s-search-result">
            <a class="a-link-normal a-text-normal" href="/dp/B08N5LNXC5">MacBook Air</a>
            <span class="a-price-whole">999</span>
            <span class="a-price-fraction">00</span>
            <span class="a-star-4-5" title="4.7 out of 5 stars"></span>
          </div>
        </html>
        """
        res = amazon.parse(html_content, "https://www.amazon.com/s?k=macbook")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Amazon Search Results")
        self.assertIn("* **MacBook Air**", res["raw_text"])
        self.assertIn("Price: $999.00 | Rating: 4.7 out of 5 stars", res["raw_text"])
        self.assertIn("Link: https://www.amazon.com/dp/B08N5LNXC5", res["raw_text"])

    def test_producthunt_post_parsing(self):
        from std_plugins import producthunt
        
        html_content = """
        <html>
          <h1>Focal Harvest</h1>
          <div class="tagline">An AI OSINT research automation CLI.</div>
          <button>150 upvotes</button>
          <div class="styles_description">
            <p>Focal Harvest is an open-source OSINT research automation script.</p>
          </div>
          <div class="styles_username">Hunter1</div>
          <div class="styles_comment">Great tool for research workflow!</div>
        </html>
        """
        res = producthunt.parse(html_content, "https://www.producthunt.com/posts/focal-harvest")
        self.assertTrue(res["success"])
        self.assertEqual(res["title"], "Product Hunt: Focal Harvest")
        self.assertIn("Stats: 150 upvotes", res["raw_text"])
        self.assertIn("Tagline: An AI OSINT research automation CLI.", res["raw_text"])
        self.assertIn("Focal Harvest is an open-source OSINT research automation script.", res["raw_text"])
        self.assertIn("* **Hunter1**: \"Great tool for research workflow!\"", res["raw_text"])

    def test_clean_slug_url(self):
        # Reddit URL cleaning
        reddit_full = "https://www.reddit.com/r/watchesindia/comments/1fsycjm/what_are_you_honest_thoughts_about_smartwatches/"
        reddit_expected = "https://www.reddit.com/r/watchesindia/comments/1fsycjm"
        self.assertEqual(scraper._clean_slug_url(reddit_full), reddit_expected)

        # Stack Overflow URL cleaning
        so_full = "https://stackoverflow.com/questions/11227809/why-is-processing-a-sorted-array-faster-than-an-unsorted-array"
        so_expected = "https://stackoverflow.com/questions/11227809"
        self.assertEqual(scraper._clean_slug_url(so_full), so_expected)

        # Unaffected URL
        unaffected = "https://www.wikipedia.org/wiki/Artificial_intelligence"
        self.assertIsNone(scraper._clean_slug_url(unaffected))

if __name__ == '__main__':
    unittest.main()

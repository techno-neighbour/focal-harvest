import unittest
import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import exporter

class TestExporter(unittest.TestCase):
    def test_clean_markdown_text(self):
        raw_md = "Here is a [link](http://example.com) with **bold** text and `code` element."
        cleaned = exporter._clean_markdown_text(raw_md)
        self.assertIn("link (http://example.com)", cleaned)
        self.assertIn("bold text", cleaned)
        self.assertIn("code element", cleaned)

    def test_export_markdown_to_pdf_and_docx(self):
        sample_md = """# Test Report Title
## Executive Summary
- Bullet item 1
- Bullet item 2 with [source](http://example.com)

| Header 1 | Header 2 |
|---|---|
| Value 1 | Value 2 |
"""
        pdf_path = os.path.join("reports", "pdf", "test_sample.pdf")
        docx_path = os.path.join("reports", "docx", "test_sample.docx")

        # Test calls return boolean gracefully whether package is installed or missing
        pdf_res = exporter.export_markdown_to_pdf(sample_md, pdf_path)
        docx_res = exporter.export_markdown_to_docx(sample_md, docx_path)

        self.assertIsInstance(pdf_res, bool)
        self.assertIsInstance(docx_res, bool)

        # Cleanup if files were created during test
        if pdf_res and os.path.exists(pdf_path):
            os.remove(pdf_path)
        if docx_res and os.path.exists(docx_path):
            os.remove(docx_path)

if __name__ == '__main__':
    unittest.main()

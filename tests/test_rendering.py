"""Tests for ResumeRenderer and CoverLetterRenderer."""

import os
import pytest

from rendering.renderer import ResumeRenderer, CoverLetterRenderer

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
CSS_PATH = os.path.join(os.path.dirname(__file__), "..", "rendering", "templates", "resume.css")


@pytest.fixture
def renderer():
    return ResumeRenderer(CSS_PATH)


@pytest.fixture
def good_resume():
    with open(os.path.join(FIXTURES_DIR, "resumes", "good_resume.md")) as f:
        return f.read()


class TestRendering:
    def test_markdown_to_html(self, renderer, good_resume):
        """Verify markdown converts to valid HTML."""
        html = renderer.to_html(good_resume)
        assert "<html>" in html
        assert "<body>" in html
        assert "</html>" in html
        # Should contain some content
        assert "Sanofi" in html
        assert "Biostatistician" in html

    def test_css_applied(self, renderer, good_resume):
        """Verify the CSS is embedded in the HTML."""
        html = renderer.to_html(good_resume)
        assert "<style>" in html
        assert "font-family" in html

    def test_pdf_generation(self, renderer, good_resume, tmp_path):
        """Generate PDF from good_resume.md, verify file exists and is > 0 bytes."""
        output = str(tmp_path / "resume.pdf")
        try:
            renderer.to_pdf(good_resume, output)
            assert os.path.exists(output)
            assert os.path.getsize(output) > 0
        except ImportError:
            pytest.skip("WeasyPrint not installed")
        except OSError:
            pytest.skip("WeasyPrint dependencies not available")

    def test_html_contains_lists(self, renderer, good_resume):
        """Resume bullets should render as HTML lists."""
        html = renderer.to_html(good_resume)
        assert "<li>" in html

    def test_cover_letter_renderer(self):
        """CoverLetterRenderer works similarly."""
        cl_css = os.path.join(
            os.path.dirname(__file__), "..", "rendering", "templates", "cover_letter.css"
        )
        renderer = CoverLetterRenderer(cl_css)
        html = renderer.to_html("Dear Hiring Manager,\n\nI am writing about the role.")
        assert "<html>" in html
        assert "Dear Hiring Manager" in html

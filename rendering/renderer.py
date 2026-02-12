"""ResumeRenderer and CoverLetterRenderer: Markdown to PDF/DOCX conversion.

Uses markdown library for HTML conversion, WeasyPrint for PDF,
and pandoc (subprocess) for DOCX.
"""

import os
import subprocess
import markdown


class ResumeRenderer:
    def __init__(self, css_path: str = "rendering/templates/resume.css"):
        self.css_path = css_path
        if os.path.exists(css_path):
            with open(css_path) as f:
                self.css = f.read()
        else:
            self.css = ""

    def to_html(self, md_content: str) -> str:
        """Convert markdown to HTML with embedded CSS."""
        html_body = markdown.markdown(md_content, extensions=["extra"])
        return (
            f"<html><head><style>{self.css}</style></head>"
            f"<body>{html_body}</body></html>"
        )

    def to_pdf(self, md_content: str, output_path: str):
        """Convert markdown to PDF via WeasyPrint."""
        from weasyprint import HTML

        html = self.to_html(md_content)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        HTML(string=html).write_pdf(output_path)

    def to_docx(self, md_content: str, output_path: str):
        """Convert markdown to DOCX via pandoc subprocess."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = [
            "pandoc", "--from", "markdown", "--to", "docx",
            "-o", output_path,
        ]
        # Add reference doc if it exists
        ref_path = os.path.join(
            os.path.dirname(self.css_path), "resume_reference.docx"
        )
        if os.path.exists(ref_path):
            cmd.extend(["--reference-doc", ref_path])

        subprocess.run(
            cmd, input=md_content, text=True, check=True,
        )


class CoverLetterRenderer:
    def __init__(self, css_path: str = "rendering/templates/cover_letter.css"):
        self.css_path = css_path
        if os.path.exists(css_path):
            with open(css_path) as f:
                self.css = f.read()
        else:
            self.css = ""

    def to_html(self, md_content: str) -> str:
        """Convert markdown to HTML with embedded CSS."""
        html_body = markdown.markdown(md_content, extensions=["extra"])
        return (
            f"<html><head><style>{self.css}</style></head>"
            f"<body>{html_body}</body></html>"
        )

    def to_pdf(self, md_content: str, output_path: str):
        """Convert markdown to PDF via WeasyPrint."""
        from weasyprint import HTML

        html = self.to_html(md_content)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        HTML(string=html).write_pdf(output_path)

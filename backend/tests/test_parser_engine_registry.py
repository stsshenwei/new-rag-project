import tempfile
import unittest
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.document_parser import (
    BuiltinDocxParser,
    BuiltinExcelParser,
    BuiltinMarkdownParser,
    BuiltinPDFParser,
    DoclingDocumentParser,
    MarkdownFallbackParser,
    ParserEngineRegistry,
    PARSER_REGISTRY,
)


class ParserEngineRegistryTests(unittest.TestCase):
    def test_builtin_default_resolution(self):
        registry = ParserEngineRegistry()
        registry.register("builtin", {"md": BuiltinMarkdownParser})
        parser, effective, fallback = registry.resolve("builtin", ".md")
        self.assertIs(BuiltinMarkdownParser, parser)
        self.assertEqual("builtin", effective)
        self.assertEqual("", fallback)

    def test_global_builtin_registry_uses_focused_parsers(self):
        self.assertIs(BuiltinMarkdownParser, PARSER_REGISTRY.resolve("builtin", "md")[0])
        self.assertIs(BuiltinDocxParser, PARSER_REGISTRY.resolve("builtin", "docx")[0])
        self.assertIs(BuiltinExcelParser, PARSER_REGISTRY.resolve("builtin", "xlsx")[0])

    def test_unavailable_optional_engine_falls_back_to_builtin(self):
        registry = ParserEngineRegistry()
        registry.register("builtin", {"pdf": BuiltinPDFParser})
        registry.register("optional", {"pdf": DoclingDocumentParser}, lambda: False)
        parser, effective, fallback = registry.resolve("optional", "pdf")
        self.assertIs(BuiltinPDFParser, parser)
        self.assertEqual("builtin", effective)
        self.assertIn("unavailable", fallback)

    def test_requested_engine_without_format_falls_back(self):
        registry = ParserEngineRegistry()
        registry.register("builtin", {"md": BuiltinMarkdownParser})
        registry.register("other", {"pdf": BuiltinPDFParser})
        parser, effective, fallback = registry.resolve("other", "md")
        self.assertIs(BuiltinMarkdownParser, parser)
        self.assertEqual("builtin", effective)
        self.assertIn("does not support", fallback)

    def test_docling_conversion_path_is_reachable(self):
        fake_document = MagicMock()
        fake_document.export_to_markdown.return_value = "# Parsed\nbody"
        fake_document.export_to_html.return_value = "<h1>Parsed</h1><p>body</p>"
        fake_result = MagicMock(document=fake_document)
        converter = MagicMock()
        converter.convert.return_value = fake_result
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            path.write_bytes(b"fixture")
            fake_module = types.ModuleType("docling.document_converter")
            fake_module.DocumentConverter = MagicMock(return_value=converter)
            fake_package = types.ModuleType("docling")
            fake_package.__path__ = []
            with patch.dict(sys.modules, {"docling": fake_package, "docling.document_converter": fake_module}):
                parsed = DoclingDocumentParser().parse(path)
        converter.convert.assert_called_once_with(path)
        self.assertEqual("# Parsed\nbody", parsed.markdown)
        self.assertEqual("docling", parsed.diagnostics.effective_engine)


if __name__ == "__main__":
    unittest.main()

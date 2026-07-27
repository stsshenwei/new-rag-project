import unittest

from app.services.adaptive_chunker import (
    AdaptiveChunkConfig,
    profile_document,
    select_strategy,
    split_with_diagnostics,
    validate_chunks,
)


class AdaptiveChunkerTests(unittest.TestCase):
    def test_weknora_auto_chain_order_is_invariant(self):
        text = "# A\nbody\n# B\nbody\n# C\nbody\n\f\nChapter 2 More\n" + ("detail sentence. " * 80)
        chain = select_strategy(profile_document(text))
        self.assertEqual(["heading", "heuristic", "legacy"], chain)

    def test_plain_document_always_has_legacy_fallback(self):
        self.assertEqual(["legacy"], select_strategy(profile_document("plain text " * 100)))

    def test_explicit_heading_falls_back_only_to_legacy(self):
        _, diagnostics = split_with_diagnostics(
            "plain text " * 200,
            AdaptiveChunkConfig(chunk_size_chars=120, chunk_overlap_chars=20, strategy="heading"),
        )
        self.assertEqual(["heading", "legacy"], diagnostics.tier_chain)

    def test_explicit_heuristic_falls_back_only_to_legacy(self):
        _, diagnostics = split_with_diagnostics(
            "plain text " * 200,
            AdaptiveChunkConfig(chunk_size_chars=120, chunk_overlap_chars=20, strategy="heuristic"),
        )
        self.assertEqual(["heuristic", "legacy"], diagnostics.tier_chain)

    def test_recursive_and_legacy_are_legacy_only(self):
        for strategy in ("recursive", "legacy"):
            with self.subTest(strategy=strategy):
                _, diagnostics = split_with_diagnostics(
                    "plain text " * 200,
                    AdaptiveChunkConfig(chunk_size_chars=120, chunk_overlap_chars=20, strategy=strategy),
                )
                self.assertEqual(["legacy"], diagnostics.tier_chain)

    def test_heading_strategy_keeps_breadcrumb_separate(self):
        text = "# Guide\n" + ("intro. " * 60) + "\n## Install\n" + ("step. " * 80) + "\n# FAQ\n" + ("answer. " * 40)
        chunks, diagnostics = split_with_diagnostics(
            text, AdaptiveChunkConfig(chunk_size_chars=180, chunk_overlap_chars=20, strategy="auto")
        )
        self.assertEqual("heading", diagnostics.selected_tier)
        self.assertTrue(any("# Guide" in chunk.context_header for chunk in chunks))
        self.assertTrue(all(chunk.end - chunk.start == len(chunk.content) for chunk in chunks))

    def test_fake_heading_inside_code_is_not_boundary(self):
        text = "# One\nbody\n# Two\n```python\n# fake\n```\nbody\n# Three\nbody " + ("x" * 300)
        profile = profile_document(text)
        self.assertEqual(3, profile.md_heading_total)

    def test_heuristic_selected_for_chinese_chapter(self):
        text = "第一章 概述\n" + ("内容。" * 100) + "\n第二章 方法\n" + ("方法。" * 100)
        chunks, diagnostics = split_with_diagnostics(
            text, AdaptiveChunkConfig(chunk_size_chars=160, chunk_overlap_chars=20, strategy="auto")
        )
        self.assertEqual(["heuristic", "legacy"], diagnostics.tier_chain)
        self.assertEqual(2, diagnostics.profile.chinese_chapter_count)
        self.assertTrue(chunks)

    def test_recursive_respects_cjk_sentence_separator_and_overlap(self):
        text = ("这是第一句。" * 100) + "结束。"
        chunks, diagnostics = split_with_diagnostics(
            text, AdaptiveChunkConfig(chunk_size_chars=100, chunk_overlap_chars=20, strategy="recursive")
        )
        self.assertEqual("legacy", diagnostics.selected_tier)
        self.assertEqual(["legacy"], diagnostics.tier_chain)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.content) <= 200 for chunk in chunks))

    def test_recursive_handles_empty_input(self):
        chunks, diagnostics = split_with_diagnostics(
            "",
            AdaptiveChunkConfig(chunk_size_chars=80, chunk_overlap_chars=10, strategy="recursive"),
        )

        self.assertEqual([], chunks)
        self.assertEqual("legacy", diagnostics.selected_tier)
        self.assertEqual([], diagnostics.tier_chain)

    def test_recursive_uses_ordered_english_separators_and_offsets(self):
        text = (
            "Alpha paragraph one sentence. Another sentence.\n\n"
            "Beta paragraph has enough words to force a second chunk. "
            "More words keep it above the configured boundary.\n\n"
            "Gamma final paragraph closes the sample cleanly."
        )
        chunks, _ = split_with_diagnostics(
            text,
            AdaptiveChunkConfig(chunk_size_chars=90, chunk_overlap_chars=20, strategy="recursive"),
        )

        self.assertGreater(len(chunks), 1)
        self.assertTrue(any(chunk.content.endswith("\n\n") for chunk in chunks[:-1]))
        self.assertTrue(all(text[chunk.start:chunk.end] == chunk.content for chunk in chunks))

    def test_recursive_preserves_protected_code_and_formula_offsets(self):
        text = (
            "Intro paragraph.\n\n"
            "```python\n# not a heading\nprint('x')\n```\n\n"
            "$$\na^2 + b^2 = c^2\n$$\n\n"
            + ("tail sentence. " * 20)
        )
        chunks, _ = split_with_diagnostics(
            text,
            AdaptiveChunkConfig(chunk_size_chars=120, chunk_overlap_chars=15, strategy="recursive"),
        )
        joined = "\n".join(chunk.content for chunk in chunks)

        self.assertIn("```python\n# not a heading\nprint('x')\n```", joined)
        self.assertIn("$$\na^2 + b^2 = c^2\n$$", joined)
        self.assertTrue(all(text[chunk.start:chunk.end] == chunk.content for chunk in chunks))

    def test_parity_fixture_preserves_chinese_table_image_and_markers(self):
        text = (
            "第一章 系统概述\n"
            "本章说明设备形态、接口能力和部署条件。重要参数包括功耗、端口和管理方式。\n\n"
            "1.1 安装条件\n"
            "请确认机房温度、供电和接地条件满足要求。\n\n"
            "| 参数 | 取值 |\n"
            "| --- | --- |\n"
            "| 端口 | 8 个 GPON |\n"
            "| 功耗 | 36W |\n\n"
            "![拓扑图](images/topology.png)\n\n"
            "```text\n# 这里不是标题\ninterface gpon 0/1\n```\n\n"
            "$$\nP = U \\times I\n$$\n\n"
            "第二章 运维说明\n"
            "告警、升级和回滚流程需要记录操作人和时间。"
        )

        chunks, diagnostics = split_with_diagnostics(
            text, AdaptiveChunkConfig(chunk_size_chars=120, chunk_overlap_chars=20, strategy="auto")
        )
        joined = "\n".join(chunk.content for chunk in chunks)

        self.assertIn("heuristic", diagnostics.tier_chain)
        self.assertEqual(2, diagnostics.profile.chinese_chapter_count)
        self.assertIn("| 端口 | 8 个 GPON |", joined)
        self.assertIn("![拓扑图](images/topology.png)", joined)
        self.assertIn("```text\n# 这里不是标题\ninterface gpon 0/1\n```", joined)
        self.assertIn("$$\nP = U \\times I\n$$", joined)
        self.assertTrue(all(text[chunk.start:chunk.end] == chunk.content for chunk in chunks))

    def test_recursive_bounds_large_protected_formula(self):
        formula = "$$\n" + ("x" * 260) + "\n$$"
        chunks, _ = split_with_diagnostics(
            "before\n" + formula + "\nafter",
            AdaptiveChunkConfig(
                chunk_size_chars=80,
                chunk_overlap_chars=10,
                strategy="recursive",
                max_protected_chars=90,
            ),
        )

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.content) <= 160 for chunk in chunks))
        self.assertTrue(all(chunk.end - chunk.start == len(chunk.content) for chunk in chunks))

    def test_recursive_repeats_table_header_in_context_without_changing_offsets(self):
        rows = "\n".join(f"| r{i} | {i} |" for i in range(1, 18))
        text = "Before table.\n\n| Name | Value |\n| --- | --- |\n" + rows + "\n\nAfter table."
        chunks, _ = split_with_diagnostics(
            text,
            AdaptiveChunkConfig(chunk_size_chars=85, chunk_overlap_chars=10, strategy="recursive"),
        )
        table_chunks = [chunk for chunk in chunks if "| r" in chunk.content]
        repeated = [chunk for chunk in table_chunks if chunk.context_header]

        self.assertGreaterEqual(len(table_chunks), 2)
        self.assertTrue(repeated)
        self.assertTrue(any("| Name | Value |\n| --- | --- |" in chunk.context_header for chunk in repeated))
        self.assertTrue(all(text[chunk.start:chunk.end] == chunk.content for chunk in chunks))
        self.assertTrue(all(not chunk.content.startswith("| Name | Value |") for chunk in repeated))
        self.assertTrue(all("| Name | Value |" in chunk.embedding_content for chunk in repeated))

    def test_strategy_thresholds_and_deterministic_output(self):
        two_headings = "# A\nbody\n# B\nbody\n" + ("plain. " * 40)
        three_headings = "# A\nbody\n# B\nbody\n# C\nbody\n" + ("plain. " * 40)
        page_break = "Intro\f" + ("body. " * 80)

        self.assertEqual(["legacy"], select_strategy(profile_document(two_headings)))
        self.assertEqual(["heading", "legacy"], select_strategy(profile_document(three_headings)))
        self.assertEqual(["heuristic", "legacy"], select_strategy(profile_document(page_break)))

        first, first_diag = split_with_diagnostics(
            three_headings,
            AdaptiveChunkConfig(chunk_size_chars=120, chunk_overlap_chars=20, strategy="auto"),
        )
        second, second_diag = split_with_diagnostics(
            three_headings,
            AdaptiveChunkConfig(chunk_size_chars=120, chunk_overlap_chars=20, strategy="auto"),
        )
        self.assertEqual(first_diag.tier_chain, second_diag.tier_chain)
        self.assertEqual(
            [(c.content, c.start, c.end, c.context_header, c.strategy) for c in first],
            [(c.content, c.start, c.end, c.context_header, c.strategy) for c in second],
        )

    def test_rejected_structural_tier_falls_through_to_legacy(self):
        text = "\n".join(f"# H{i}\nx" for i in range(12)) + "\n" + ("plain sentence. " * 80)
        chunks, diagnostics = split_with_diagnostics(
            text, AdaptiveChunkConfig(chunk_size_chars=260, chunk_overlap_chars=30, strategy="auto")
        )

        self.assertEqual(["heading", "legacy"], diagnostics.tier_chain)
        self.assertEqual("heading", diagnostics.rejected[0].tier)
        self.assertEqual("too many tiny chunks", diagnostics.rejected[0].reason)
        self.assertEqual("legacy", diagnostics.selected_tier)
        self.assertTrue(chunks)

    def test_validator_matches_weknora_rejection_rules(self):
        tiny = [type("C", (), {"content": "x"})() for _ in range(8)]
        ok, reason = validate_chunks(tiny, 1000, 512)
        self.assertFalse(ok)
        self.assertEqual("too many tiny chunks", reason)


if __name__ == "__main__":
    unittest.main()

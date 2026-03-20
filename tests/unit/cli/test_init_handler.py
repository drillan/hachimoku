"""InitHandler のテスト。

FR-CLI-007: .hachimoku/ ディレクトリ構造の初期化。
FR-CLI-008: 既存ファイルのスキップと --force による上書き。
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from hachimoku.cli._init_handler import (
    GITIGNORE_ENTRY,
    GITIGNORE_SECTION,
    InitError,
    InitResult,
    _copy_builtin_agents,
    _ensure_gitignore,
    _generate_config_template,
    run_init,
)

# --- ビルトインエージェント定義ファイル名（ソート済み） ---

BUILTIN_AGENT_NAMES: tuple[str, ...] = (
    "aggregator.toml",
    "architecture-reviewer.toml",
    "code-reviewer.toml",
    "code-simplifier.toml",
    "comment-analyzer.toml",
    "performance-analyzer.toml",
    "pr-test-analyzer.toml",
    "security-analyzer.toml",
    "selector.toml",
    "silent-failure-hunter.toml",
    "type-design-analyzer.toml",
)


# --- TestInitResult ---


class TestInitResult:
    """InitResult モデルのバリデーションを検証する。"""

    def test_default_empty_tuples(self) -> None:
        """デフォルトコンストラクタで created=(), skipped=() となる。"""
        result = InitResult()
        assert result.created == ()
        assert result.skipped == ()

    def test_with_paths(self, tmp_path: Path) -> None:
        """Path オブジェクトのタプルを受け付ける。"""
        p1 = tmp_path / "a.toml"
        p2 = tmp_path / "b.toml"
        result = InitResult(created=(p1,), skipped=(p2,))
        assert result.created == (p1,)
        assert result.skipped == (p2,)

    def test_is_frozen(self, tmp_path: Path) -> None:
        """frozen モデルであること。"""
        result = InitResult()
        with pytest.raises(ValidationError):
            result.created = (tmp_path,)  # type: ignore[misc]

    def test_forbids_extra(self) -> None:
        """extra='forbid' が効いている。"""
        with pytest.raises(ValidationError, match="extra"):
            InitResult(unknown_field="x")  # type: ignore[call-arg]


# --- TestInitError ---


class TestInitError:
    """InitError 例外クラスを検証する。"""

    def test_is_exception(self) -> None:
        assert issubclass(InitError, Exception)

    def test_message(self) -> None:
        err = InitError("test message")
        assert str(err) == "test message"


# --- TestGenerateConfigTemplate ---


class TestGenerateConfigTemplate:
    """_generate_config_template の動作を検証する。"""

    def test_returns_string(self) -> None:
        assert isinstance(_generate_config_template(), str)

    def test_contains_model(self) -> None:
        template = _generate_config_template()
        assert "model" in template

    def test_contains_timeout(self) -> None:
        template = _generate_config_template()
        assert "timeout" in template

    def test_contains_max_turns(self) -> None:
        template = _generate_config_template()
        assert "max_turns" in template

    def test_contains_parallel(self) -> None:
        template = _generate_config_template()
        assert "parallel" in template

    def test_contains_base_branch(self) -> None:
        template = _generate_config_template()
        assert "base_branch" in template

    def test_contains_output_format(self) -> None:
        template = _generate_config_template()
        assert "output_format" in template

    def test_contains_save_reviews(self) -> None:
        template = _generate_config_template()
        assert "save_reviews" in template

    def test_contains_show_cost(self) -> None:
        template = _generate_config_template()
        assert "show_cost" in template

    def test_contains_max_files_per_review(self) -> None:
        template = _generate_config_template()
        assert "max_files_per_review" in template

    def test_does_not_contain_provider(self) -> None:
        """provider はテンプレートに含まれない（#125 で廃止）。"""
        template = _generate_config_template()
        assert "provider" not in template

    def test_contains_default_values(self) -> None:
        """デフォルト値が含まれている。"""
        from hachimoku.models.config import DEFAULT_MAX_TURNS

        template = _generate_config_template()
        assert '"claudecode:claude-opus-4-6"' in template
        assert "600" in template
        assert f"max_turns = {DEFAULT_MAX_TURNS}" in template
        assert "true" in template
        assert '"main"' in template
        assert '"markdown"' in template
        assert "100" in template

    def test_all_settings_commented(self) -> None:
        """設定行が全てコメント（# で始まる）である。"""
        template = _generate_config_template()
        for line in template.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # 設定行（key = value）はコメントであるべき
            if (
                "=" in stripped
                and not stripped.startswith("#")
                and not stripped.startswith("[")
            ):
                pytest.fail(f"Uncommented setting found: {stripped}")

    def test_valid_toml_when_uncommented(self) -> None:
        """コメントを解除すると有効な TOML としてパースできる。"""
        template = _generate_config_template()
        uncommented_lines: list[str] = []
        for line in template.splitlines():
            stripped = line.strip()
            if stripped.startswith("# ["):
                # テーブルヘッダー（例: "# [selector]"）をアンコメント
                uncommented_lines.append(stripped[2:])
            elif stripped.startswith("# ") and "=" in stripped:
                # 設定行（例: "# model = 'sonnet'"）をアンコメント
                uncommented_lines.append(stripped[2:])
            elif stripped.startswith("#"):
                # 説明コメントはスキップ
                continue
            else:
                uncommented_lines.append(line)
        uncommented = "\n".join(uncommented_lines)
        # パースエラーが発生しないことを検証
        tomllib.loads(uncommented)

    def test_contains_selector_section(self) -> None:
        """[selector] セクションの記載がある。"""
        template = _generate_config_template()
        assert "selector" in template

    def test_contains_agents_section_hint(self) -> None:
        """エージェント個別設定の記載がある。"""
        template = _generate_config_template()
        assert "agents" in template


# --- TestEnsureGitignore ---


class TestEnsureGitignore:
    """_ensure_gitignore の動作を検証する。"""

    def test_creates_gitignore_when_missing(self, tmp_path: Path) -> None:
        """.gitignore が存在しない場合、新規作成して /.hachimoku/ を追加する。"""
        result = _ensure_gitignore(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.is_file()
        content = gitignore.read_text(encoding="utf-8")
        assert GITIGNORE_ENTRY in content
        assert result == "created"

    def test_new_gitignore_contains_section_comment(self, tmp_path: Path) -> None:
        """新規作成時にセクションコメント '# hachimoku' が付与される。"""
        _ensure_gitignore(tmp_path)
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert GITIGNORE_SECTION in content

    def test_appends_to_existing_gitignore(self, tmp_path: Path) -> None:
        """.gitignore が存在し /.hachimoku/ が未登録の場合、末尾に追加する。"""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n", encoding="utf-8")

        result = _ensure_gitignore(tmp_path)
        content = gitignore.read_text(encoding="utf-8")
        assert content.startswith("node_modules/\n")
        assert GITIGNORE_ENTRY in content
        assert result == "created"

    def test_preserves_existing_content(self, tmp_path: Path) -> None:
        """既存 .gitignore の内容が破壊されない。"""
        gitignore = tmp_path / ".gitignore"
        original = "# my project\nnode_modules/\n*.pyc\n"
        gitignore.write_text(original, encoding="utf-8")

        _ensure_gitignore(tmp_path)
        content = gitignore.read_text(encoding="utf-8")
        assert content.startswith(original)

    def test_skips_when_entry_already_exists(self, tmp_path: Path) -> None:
        """.gitignore に /.hachimoku/ が既に存在する場合、スキップする。"""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(
            "node_modules/\n# hachimoku\n/.hachimoku/\n", encoding="utf-8"
        )

        result = _ensure_gitignore(tmp_path)
        content = gitignore.read_text(encoding="utf-8")
        # 重複追加されていないことを確認
        assert content.count(GITIGNORE_ENTRY) == 1
        assert result == "skipped"

    def test_adds_even_with_partial_entry(self, tmp_path: Path) -> None:
        """部分的エントリ（.hachimoku/reviews 等）がある場合でも /.hachimoku/ を追加する。"""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".hachimoku/reviews\n", encoding="utf-8")

        result = _ensure_gitignore(tmp_path)
        content = gitignore.read_text(encoding="utf-8")
        assert GITIGNORE_ENTRY in content
        assert result == "created"

    def test_appends_newline_separator(self, tmp_path: Path) -> None:
        """既存ファイル末尾に改行がない場合、改行を挟んで追加する。"""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/", encoding="utf-8")  # 末尾改行なし

        _ensure_gitignore(tmp_path)
        content = gitignore.read_text(encoding="utf-8")
        # 既存内容とセクションコメントの間に改行がある
        assert "node_modules/\n" in content
        assert GITIGNORE_SECTION in content

    def test_new_gitignore_format(self, tmp_path: Path) -> None:
        """新規作成時のフォーマットが仕様通りである。"""
        _ensure_gitignore(tmp_path)
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        expected = f"{GITIGNORE_SECTION}\n{GITIGNORE_ENTRY}\n"
        assert content == expected

    def test_non_utf8_gitignore_raises_init_error(self, tmp_path: Path) -> None:
        """非 UTF-8 エンコーディングの .gitignore で InitError が送出される。"""
        gitignore = tmp_path / ".gitignore"
        # Shift_JIS でエンコードされた日本語コメントを含む .gitignore
        gitignore.write_bytes("# プロジェクト設定\nnode_modules/\n".encode("shift_jis"))

        with pytest.raises(InitError):
            _ensure_gitignore(tmp_path)

    def test_non_utf8_gitignore_error_contains_hint(self, tmp_path: Path) -> None:
        """非 UTF-8 .gitignore のエラーメッセージに解決方法ヒントが含まれる。"""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_bytes("# プロジェクト設定\n".encode("shift_jis"))

        with pytest.raises(InitError, match=r"Convert .gitignore to UTF-8"):
            _ensure_gitignore(tmp_path)


# --- TestCopyBuiltinAgents ---


class TestCopyBuiltinAgents:
    """_copy_builtin_agents の動作を検証する。"""

    def test_copies_all_builtin_agents(self, tmp_path: Path) -> None:
        """全ビルトイン .toml ファイルがコピーされる。"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        created, _skipped = _copy_builtin_agents(agents_dir, force=False)
        assert len(created) == len(BUILTIN_AGENT_NAMES)

    def test_copied_filenames_match_builtin(self, tmp_path: Path) -> None:
        """コピーされたファイル名がビルトイン定義と一致する。"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        created, _ = _copy_builtin_agents(agents_dir, force=False)
        copied_names = sorted(p.name for p in created)
        assert tuple(copied_names) == BUILTIN_AGENT_NAMES

    def test_returns_empty_skipped_on_fresh(self, tmp_path: Path) -> None:
        """新規コピー時は skipped リストが空。"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _, skipped = _copy_builtin_agents(agents_dir, force=False)
        assert skipped == []

    def test_skips_existing_no_force(self, tmp_path: Path) -> None:
        """force=False で既存ファイルをスキップ。"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        # 1つファイルを事前作成
        existing = agents_dir / "code-reviewer.toml"
        existing.write_text("custom content")

        created, skipped = _copy_builtin_agents(agents_dir, force=False)
        assert existing in skipped
        assert existing not in created
        # 内容が変更されていない
        assert existing.read_text() == "custom content"

    def test_force_overwrites_existing(self, tmp_path: Path) -> None:
        """force=True で既存ファイルが上書きされる。"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        existing = agents_dir / "code-reviewer.toml"
        existing.write_text("custom content")

        created, skipped = _copy_builtin_agents(agents_dir, force=True)
        assert existing in created
        assert skipped == []
        # 内容がビルトイン定義に上書きされている
        assert existing.read_text() != "custom content"

    def test_copied_content_matches_builtin(self, tmp_path: Path) -> None:
        """コピーされたファイルの内容が空でない。"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        created, _ = _copy_builtin_agents(agents_dir, force=False)
        for path in created:
            content = path.read_text()
            assert len(content) > 0
            # 有効な TOML であること
            tomllib.loads(content)


# --- TestRunInit ---


class TestRunInit:
    """run_init の統合テスト。"""

    def test_creates_hachimoku_dir(self, tmp_path: Path) -> None:
        """.hachimoku/ ディレクトリが作成される。"""
        (tmp_path / ".git").mkdir()
        run_init(tmp_path)
        assert (tmp_path / ".hachimoku").is_dir()

    def test_creates_config_toml(self, tmp_path: Path) -> None:
        """.hachimoku/config.toml が作成される。"""
        (tmp_path / ".git").mkdir()
        run_init(tmp_path)
        assert (tmp_path / ".hachimoku" / "config.toml").is_file()

    def test_creates_agents_dir_with_all_builtins(self, tmp_path: Path) -> None:
        """.hachimoku/agents/ に全ビルトインファイルが作成される。"""
        (tmp_path / ".git").mkdir()
        run_init(tmp_path)
        agents_dir = tmp_path / ".hachimoku" / "agents"
        assert agents_dir.is_dir()
        toml_files = sorted(p.name for p in agents_dir.iterdir() if p.suffix == ".toml")
        assert tuple(toml_files) == BUILTIN_AGENT_NAMES

    def test_creates_reviews_dir(self, tmp_path: Path) -> None:
        """.hachimoku/reviews/ ディレクトリが作成される。"""
        (tmp_path / ".git").mkdir()
        run_init(tmp_path)
        assert (tmp_path / ".hachimoku" / "reviews").is_dir()

    def test_creates_gitignore_entry(self, tmp_path: Path) -> None:
        """.gitignore に /.hachimoku/ が追加される。"""
        (tmp_path / ".git").mkdir()
        run_init(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.is_file()
        content = gitignore.read_text(encoding="utf-8")
        assert GITIGNORE_ENTRY in content

    def test_gitignore_skipped_when_already_present(self, tmp_path: Path) -> None:
        """.gitignore に /.hachimoku/ が既にある場合はスキップされる。"""
        (tmp_path / ".git").mkdir()
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("# hachimoku\n/.hachimoku/\n", encoding="utf-8")

        result = run_init(tmp_path)
        assert gitignore in result.skipped
        # 重複追加されていない
        content = gitignore.read_text(encoding="utf-8")
        assert content.count(GITIGNORE_ENTRY) == 1

    def test_result_created_contains_all_files(self, tmp_path: Path) -> None:
        """InitResult.created に作成した全ファイルパスが含まれる。"""
        (tmp_path / ".git").mkdir()
        result = run_init(tmp_path)
        # config.toml + builtin agents + .gitignore
        expected_count = 1 + len(BUILTIN_AGENT_NAMES) + 1
        assert len(result.created) == expected_count
        assert result.skipped == ()

    def test_non_git_repo_succeeds(self, tmp_path: Path) -> None:
        """.git/ なしでも run_init() が正常終了する。"""
        result = run_init(tmp_path)
        assert (tmp_path / ".hachimoku").is_dir()
        assert (tmp_path / ".hachimoku" / "config.toml").is_file()
        assert result.created  # 何かしら作成されている

    def test_non_git_repo_no_gitignore_created(self, tmp_path: Path) -> None:
        """Git リポジトリ外では .gitignore が作成されない。"""
        run_init(tmp_path)
        assert not (tmp_path / ".gitignore").exists()

    def test_non_git_repo_result_excludes_gitignore(self, tmp_path: Path) -> None:
        """Git リポジトリ外では .gitignore が結果に含まれない。"""
        result = run_init(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore not in result.created
        assert gitignore not in result.skipped

    def test_non_git_repo_creates_all_other_files(self, tmp_path: Path) -> None:
        """Git リポジトリ外でも .hachimoku/ 配下のファイルが全て作成される。"""
        result = run_init(tmp_path)
        # config.toml + builtin agents (.gitignore は含まれない)
        expected_count = 1 + len(BUILTIN_AGENT_NAMES)
        assert len(result.created) == expected_count
        assert (tmp_path / ".hachimoku" / "config.toml").is_file()
        assert (tmp_path / ".hachimoku" / "agents").is_dir()
        assert (tmp_path / ".hachimoku" / "reviews").is_dir()

    def test_git_repo_still_creates_gitignore(self, tmp_path: Path) -> None:
        """Git リポジトリ内では従来通り .gitignore にエントリが追加される。"""
        (tmp_path / ".git").mkdir()
        result = run_init(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.is_file()
        assert gitignore in result.created
        content = gitignore.read_text(encoding="utf-8")
        assert GITIGNORE_ENTRY in content

    def test_existing_files_skipped_no_force(self, tmp_path: Path) -> None:
        """既存ファイルがスキップされる。"""
        (tmp_path / ".git").mkdir()
        hachimoku_dir = tmp_path / ".hachimoku"
        hachimoku_dir.mkdir()
        config_path = hachimoku_dir / "config.toml"
        config_path.write_text("# custom config")

        result = run_init(tmp_path)
        assert config_path in result.skipped
        assert config_path not in result.created
        # 内容が変更されていない
        assert config_path.read_text() == "# custom config"

    def test_missing_files_created_when_partial_exists(self, tmp_path: Path) -> None:
        """一部ファイルが存在する場合、不足分のみが作成される。"""
        (tmp_path / ".git").mkdir()
        hachimoku_dir = tmp_path / ".hachimoku"
        hachimoku_dir.mkdir()
        agents_dir = hachimoku_dir / "agents"
        agents_dir.mkdir()
        # 1つだけ事前作成
        (agents_dir / "code-reviewer.toml").write_text("custom")

        result = run_init(tmp_path)
        # config.toml + (builtin agents - 1) + .gitignore
        expected_created = 1 + (len(BUILTIN_AGENT_NAMES) - 1) + 1
        assert len(result.created) == expected_created
        # code-reviewer.toml は skipped
        assert len(result.skipped) == 1

    def test_force_overwrites_all(self, tmp_path: Path) -> None:
        """force=True で全ファイルが上書きされる。"""
        (tmp_path / ".git").mkdir()
        # 初回実行
        run_init(tmp_path)
        # config.toml をカスタマイズ
        config_path = tmp_path / ".hachimoku" / "config.toml"
        config_path.write_text("# custom config")

        # force で再実行
        result = run_init(tmp_path, force=True)
        # config.toml + builtin agents = created, .gitignore は skipped（既に存在）
        expected_count = 1 + len(BUILTIN_AGENT_NAMES)
        assert len(result.created) == expected_count
        # .gitignore は既に /.hachimoku/ エントリがあるので skipped
        gitignore = tmp_path / ".gitignore"
        assert gitignore in result.skipped

    def test_config_content_is_template(self, tmp_path: Path) -> None:
        """生成された config.toml がテンプレートと一致する。"""
        (tmp_path / ".git").mkdir()
        run_init(tmp_path)
        config_content = (tmp_path / ".hachimoku" / "config.toml").read_text()
        assert config_content == _generate_config_template()

    def test_idempotent_no_force(self, tmp_path: Path) -> None:
        """2回実行しても既存ファイルが変更されない。"""
        (tmp_path / ".git").mkdir()
        first = run_init(tmp_path)
        second = run_init(tmp_path)
        assert len(second.created) == 0
        assert len(second.skipped) == len(first.created)

    def test_permission_error_raises_init_error(self, tmp_path: Path) -> None:
        """ディレクトリ作成権限がない場合 InitError が送出される。"""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        # 書き込み不可にして .hachimoku/ 作成を失敗させる
        project.chmod(0o555)
        try:
            with pytest.raises(InitError, match="permissions|Permission"):
                run_init(project)
        finally:
            project.chmod(0o755)

    def test_permission_error_contains_hint(self, tmp_path: Path) -> None:
        """FS エラー時のメッセージに解決方法ヒントが含まれる。"""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        project.chmod(0o555)
        try:
            with pytest.raises(InitError, match="Check directory permissions"):
                run_init(project)
        finally:
            project.chmod(0o755)

    def test_non_utf8_gitignore_raises_init_error(self, tmp_path: Path) -> None:
        """非 UTF-8 .gitignore が存在する場合、InitError が送出される。

        UnicodeDecodeError は ValueError のサブクラスであり OSError ではないため、
        明示的に InitError に変換する必要がある（Issue #247）。
        """
        (tmp_path / ".git").mkdir()
        gitignore = tmp_path / ".gitignore"
        gitignore.write_bytes("# プロジェクト設定\n".encode("shift_jis"))

        with pytest.raises(InitError, match=r"\.gitignore"):
            run_init(tmp_path)


# --- TestRunInitUpgrade ---


class TestRunInitUpgrade:
    """run_init(upgrade=True) のテスト。Issue #317."""

    def test_force_and_upgrade_raises_value_error(self, tmp_path: Path) -> None:
        """force=True と upgrade=True の同時指定で ValueError が送出される。"""
        with pytest.raises(ValueError, match="force.*upgrade"):
            run_init(tmp_path, force=True, upgrade=True)

    def test_upgrade_adds_missing_agents(self, tmp_path: Path) -> None:
        """ビルトインに存在するが agents/ に存在しないエージェントのみ追加される。"""
        (tmp_path / ".git").mkdir()
        hachimoku_dir = tmp_path / ".hachimoku"
        hachimoku_dir.mkdir()
        agents_dir = hachimoku_dir / "agents"
        agents_dir.mkdir()
        # 1つだけ事前作成
        (agents_dir / "code-reviewer.toml").write_text("custom content")

        result = run_init(tmp_path, upgrade=True)
        # code-reviewer.toml 以外の全ビルトインが追加される
        assert len(result.created) == len(BUILTIN_AGENT_NAMES) - 1

    def test_upgrade_skips_existing_agents(self, tmp_path: Path) -> None:
        """既存のエージェント TOML が上書きされない。"""
        (tmp_path / ".git").mkdir()
        hachimoku_dir = tmp_path / ".hachimoku"
        hachimoku_dir.mkdir()
        agents_dir = hachimoku_dir / "agents"
        agents_dir.mkdir()
        existing = agents_dir / "code-reviewer.toml"
        existing.write_text("custom content")

        result = run_init(tmp_path, upgrade=True)
        assert existing in result.skipped
        assert existing not in result.created

    def test_upgrade_preserves_existing_agent_content(self, tmp_path: Path) -> None:
        """既存エージェントのカスタマイズ内容が保持される。"""
        hachimoku_dir = tmp_path / ".hachimoku"
        hachimoku_dir.mkdir()
        agents_dir = hachimoku_dir / "agents"
        agents_dir.mkdir()
        existing = agents_dir / "code-reviewer.toml"
        existing.write_text("# user customized content")

        run_init(tmp_path, upgrade=True)
        assert existing.read_text() == "# user customized content"

    def test_upgrade_skips_config_toml_creation(self, tmp_path: Path) -> None:
        """upgrade 時に config.toml が作成されない。"""
        hachimoku_dir = tmp_path / ".hachimoku"
        hachimoku_dir.mkdir()
        agents_dir = hachimoku_dir / "agents"
        agents_dir.mkdir()

        result = run_init(tmp_path, upgrade=True)
        config_path = hachimoku_dir / "config.toml"
        assert not config_path.exists()
        assert config_path not in result.created

    def test_upgrade_skips_existing_config_toml(self, tmp_path: Path) -> None:
        """upgrade 時に既存の config.toml が変更されない。"""
        hachimoku_dir = tmp_path / ".hachimoku"
        hachimoku_dir.mkdir()
        agents_dir = hachimoku_dir / "agents"
        agents_dir.mkdir()
        config_path = hachimoku_dir / "config.toml"
        config_path.write_text("# user custom config")

        result = run_init(tmp_path, upgrade=True)
        assert config_path.read_text() == "# user custom config"
        assert config_path not in result.created
        assert config_path not in result.skipped

    def test_upgrade_skips_gitignore(self, tmp_path: Path) -> None:
        """upgrade 時に .gitignore が変更されない。"""
        (tmp_path / ".git").mkdir()
        hachimoku_dir = tmp_path / ".hachimoku"
        hachimoku_dir.mkdir()
        agents_dir = hachimoku_dir / "agents"
        agents_dir.mkdir()

        result = run_init(tmp_path, upgrade=True)
        gitignore = tmp_path / ".gitignore"
        assert not gitignore.exists()
        assert gitignore not in result.created

    def test_upgrade_creates_agents_dir_if_missing(self, tmp_path: Path) -> None:
        """agents/ ディレクトリが存在しない場合に作成される。"""
        hachimoku_dir = tmp_path / ".hachimoku"
        hachimoku_dir.mkdir()

        result = run_init(tmp_path, upgrade=True)
        agents_dir = hachimoku_dir / "agents"
        assert agents_dir.is_dir()
        assert len(result.created) == len(BUILTIN_AGENT_NAMES)

    def test_upgrade_creates_hachimoku_dir_if_missing(self, tmp_path: Path) -> None:
        """.hachimoku/ ディレクトリが存在しない場合に作成される。"""
        result = run_init(tmp_path, upgrade=True)
        assert (tmp_path / ".hachimoku" / "agents").is_dir()
        assert len(result.created) == len(BUILTIN_AGENT_NAMES)

    def test_upgrade_result_only_contains_agents(self, tmp_path: Path) -> None:
        """upgrade の結果にはエージェントファイルのみが含まれる。"""
        (tmp_path / ".git").mkdir()
        hachimoku_dir = tmp_path / ".hachimoku"
        hachimoku_dir.mkdir()
        agents_dir = hachimoku_dir / "agents"
        agents_dir.mkdir()

        result = run_init(tmp_path, upgrade=True)
        for path in (*result.created, *result.skipped):
            assert path.parent == agents_dir

    def test_upgrade_preserves_custom_agents(self, tmp_path: Path) -> None:
        """ユーザー独自のカスタムエージェントが影響を受けない。"""
        hachimoku_dir = tmp_path / ".hachimoku"
        hachimoku_dir.mkdir()
        agents_dir = hachimoku_dir / "agents"
        agents_dir.mkdir()
        custom_agent = agents_dir / "scope-drift-detector.toml"
        custom_agent.write_text("# custom agent")

        run_init(tmp_path, upgrade=True)
        assert custom_agent.exists()
        assert custom_agent.read_text() == "# custom agent"

    def test_upgrade_noop_when_all_present(self, tmp_path: Path) -> None:
        """全ビルトインエージェントが既に存在する場合、何も作成されない。"""
        (tmp_path / ".git").mkdir()
        # 通常の init で全ファイル作成
        run_init(tmp_path)

        result = run_init(tmp_path, upgrade=True)
        assert len(result.created) == 0
        assert len(result.skipped) == len(BUILTIN_AGENT_NAMES)

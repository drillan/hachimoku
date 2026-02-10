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
    InitError,
    InitResult,
    _copy_builtin_agents,
    _ensure_git_repository,
    _generate_config_template,
    run_init,
)

# --- ビルトインエージェント定義ファイル名（ソート済み） ---

BUILTIN_AGENT_NAMES: tuple[str, ...] = (
    "aggregator.toml",
    "code-reviewer.toml",
    "code-simplifier.toml",
    "comment-analyzer.toml",
    "pr-test-analyzer.toml",
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


# --- TestEnsureGitRepository ---


class TestEnsureGitRepository:
    """_ensure_git_repository の動作を検証する。"""

    def test_git_repo_exists_no_error(self, tmp_path: Path) -> None:
        """.git/ が存在する場合、例外が発生しない。"""
        (tmp_path / ".git").mkdir()
        _ensure_git_repository(tmp_path)  # 例外なし

    def test_non_git_repo_raises_init_error(self, tmp_path: Path) -> None:
        """.git/ が存在しない場合、InitError が送出される。"""
        with pytest.raises(InitError):
            _ensure_git_repository(tmp_path)

    def test_error_contains_hint(self, tmp_path: Path) -> None:
        """エラーメッセージに解決方法のヒントが含まれる。"""
        with pytest.raises(InitError, match="git init"):
            _ensure_git_repository(tmp_path)


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
        template = _generate_config_template()
        assert '"claudecode:claude-sonnet-4-5"' in template
        assert "600" in template
        assert "20" in template
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

    def test_result_created_contains_all_files(self, tmp_path: Path) -> None:
        """InitResult.created に作成した全ファイルパスが含まれる。"""
        (tmp_path / ".git").mkdir()
        result = run_init(tmp_path)
        # config.toml + builtin agents
        expected_count = 1 + len(BUILTIN_AGENT_NAMES)
        assert len(result.created) == expected_count
        assert result.skipped == ()

    def test_non_git_repo_raises_init_error(self, tmp_path: Path) -> None:
        """.git/ なしの場合に InitError が送出される。"""
        with pytest.raises(InitError):
            run_init(tmp_path)

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
        # config.toml + 7 agents (selector.toml, aggregator.toml 含む) = 8 created
        assert len(result.created) == 8
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
        expected_count = 1 + len(BUILTIN_AGENT_NAMES)
        assert len(result.created) == expected_count
        assert result.skipped == ()
        # テンプレートに上書きされている
        assert config_path.read_text() != "# custom config"

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

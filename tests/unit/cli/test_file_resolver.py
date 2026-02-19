"""FileResolver のテスト。

FR-CLI-009: ファイル・ディレクトリ・glob パターンの展開。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from hachimoku.cli._file_resolver import (
    FileResolutionError,
    ResolvedFiles,
    _expand_single_path,
    _is_binary_file,
    _is_glob_pattern,
    _resolve_if_text,
    resolve_files,
)


# --- ResolvedFiles モデルバリデーション ---


class TestResolvedFilesModel:
    """ResolvedFiles モデルのバリデーションを検証する。"""

    def test_paths_stored(self) -> None:
        """paths が正しく格納される。"""
        result = ResolvedFiles(paths=("/tmp/a.py",))
        assert result.paths == ("/tmp/a.py",)

    def test_multiple_paths_stored(self) -> None:
        """複数パスが格納される。"""
        result = ResolvedFiles(paths=("/tmp/a.py", "/tmp/b.py"))
        assert len(result.paths) == 2

    def test_warnings_default_empty(self) -> None:
        """warnings のデフォルトは空タプル。"""
        result = ResolvedFiles(paths=("/tmp/a.py",))
        assert result.warnings == ()

    def test_warnings_stored(self) -> None:
        """warnings が正しく格納される。"""
        result = ResolvedFiles(paths=("/tmp/a.py",), warnings=("cycle detected",))
        assert result.warnings == ("cycle detected",)

    def test_empty_paths_raises_validation_error(self) -> None:
        """空の paths で ValidationError。"""
        with pytest.raises(ValidationError, match="too_short"):
            ResolvedFiles(paths=())

    def test_empty_string_path_raises_validation_error(self) -> None:
        """空文字列の paths 要素で ValidationError。"""
        with pytest.raises(ValidationError, match="too_short"):
            ResolvedFiles(paths=("",))

    def test_is_frozen(self) -> None:
        """frozen=True で代入不可。"""
        result = ResolvedFiles(paths=("/tmp/a.py",))
        with pytest.raises(ValidationError, match="frozen"):
            result.paths = ("/tmp/b.py",)  # type: ignore[misc]

    def test_forbids_extra_fields(self) -> None:
        """extra="forbid" で未知フィールド不可。"""
        with pytest.raises(ValidationError, match="extra"):
            ResolvedFiles(paths=("/tmp/a.py",), unknown="x")  # type: ignore[call-arg]


# --- FileResolutionError ---


class TestFileResolutionError:
    """FileResolutionError 例外クラスを検証する。"""

    def test_is_exception(self) -> None:
        assert issubclass(FileResolutionError, Exception)

    def test_message_preserved(self) -> None:
        err = FileResolutionError("path not found")
        assert str(err) == "path not found"


# --- _is_glob_pattern ---


class TestIsGlobPattern:
    """_is_glob_pattern() ヘルパーを検証する。"""

    def test_star_is_glob(self) -> None:
        assert _is_glob_pattern("*.py") is True

    def test_double_star_is_glob(self) -> None:
        assert _is_glob_pattern("src/**/*.py") is True

    def test_question_mark_is_glob(self) -> None:
        assert _is_glob_pattern("file?.py") is True

    def test_bracket_is_glob(self) -> None:
        assert _is_glob_pattern("file[0-9].py") is True

    def test_plain_path_not_glob(self) -> None:
        assert _is_glob_pattern("src/auth.py") is False

    def test_dot_not_glob(self) -> None:
        assert _is_glob_pattern("auth.py") is False

    def test_slash_not_glob(self) -> None:
        assert _is_glob_pattern("src/dir/") is False

    def test_empty_not_glob(self) -> None:
        assert _is_glob_pattern("") is False


# --- _expand_single_path: ファイル ---


class TestExpandSinglePathFile:
    """_expand_single_path() の単一ファイル展開を検証する。"""

    def test_existing_file_returns_resolved_path(self, tmp_path: Path) -> None:
        """既存ファイル → 解決済み絶対パスのリスト。"""
        f = tmp_path / "hello.py"
        f.write_text("# hello")
        paths, warnings = _expand_single_path(str(f), set())
        assert paths == [str(f.resolve())]
        assert warnings == []

    def test_resolved_path_is_absolute(self, tmp_path: Path) -> None:
        """結果パスは絶対パス。"""
        f = tmp_path / "hello.py"
        f.write_text("# hello")
        paths, _ = _expand_single_path(str(f), set())
        assert Path(paths[0]).is_absolute()

    def test_nonexistent_file_raises_error(self) -> None:
        """存在しないパスで FileResolutionError。"""
        with pytest.raises(FileResolutionError):
            _expand_single_path("/nonexistent/path/file.py", set())

    def test_error_contains_hint(self) -> None:
        """エラーメッセージに解決方法のヒントを含む。"""
        with pytest.raises(FileResolutionError, match="Check the file path"):
            _expand_single_path("/nonexistent/path/file.py", set())

    def test_unsupported_file_type_raises_error(self, tmp_path: Path) -> None:
        """通常ファイルでもディレクトリでもないパス → FileResolutionError。"""
        import socket

        sock_path = tmp_path / "test.sock"
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.bind(str(sock_path))
            with pytest.raises(FileResolutionError, match="Unsupported file type"):
                _expand_single_path(str(sock_path), set())
        finally:
            s.close()


# --- _expand_single_path: ディレクトリ ---


class TestExpandSinglePathDirectory:
    """_expand_single_path() のディレクトリ展開を検証する。"""

    def test_directory_returns_all_files(self, tmp_path: Path) -> None:
        """ディレクトリ内の全ファイルを返す。"""
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.py").write_text("b")
        (tmp_path / "c.txt").write_text("c")
        paths, warnings = _expand_single_path(str(tmp_path), set())
        assert len(paths) == 3
        assert warnings == []

    def test_directory_recursive(self, tmp_path: Path) -> None:
        """サブディレクトリ内のファイルも再帰的に返す。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "top.py").write_text("top")
        (sub / "nested.py").write_text("nested")
        paths, _ = _expand_single_path(str(tmp_path), set())
        assert len(paths) == 2
        resolved_names = {Path(p).name for p in paths}
        assert resolved_names == {"top.py", "nested.py"}

    def test_directory_skips_subdirectories(self, tmp_path: Path) -> None:
        """ディレクトリエントリ自体は結果に含まない。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "file.py").write_text("file")
        paths, _ = _expand_single_path(str(tmp_path), set())
        for p in paths:
            assert Path(p).is_file()

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        """空ディレクトリ → 空リスト。"""
        empty = tmp_path / "empty"
        empty.mkdir()
        paths, warnings = _expand_single_path(str(empty), set())
        assert paths == []
        assert warnings == []

    def test_permission_denied_raises_error(self, tmp_path: Path) -> None:
        """読み取り権限なしのディレクトリ → FileResolutionError。"""
        no_read = tmp_path / "no_read"
        no_read.mkdir()
        (no_read / "file.py").write_text("content")
        no_read.chmod(0o000)
        try:
            with pytest.raises(FileResolutionError, match="Permission denied"):
                _expand_single_path(str(no_read), set())
        finally:
            no_read.chmod(0o755)


# --- _expand_single_path: glob パターン ---


class TestExpandSinglePathGlob:
    """_expand_single_path() の glob パターン展開を検証する。"""

    def test_glob_star_py(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """*.py パターンで .py ファイルのみ展開。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.py").write_text("b")
        (tmp_path / "c.txt").write_text("c")
        paths, warnings = _expand_single_path("*.py", set())
        assert len(paths) == 2
        assert all(p.endswith(".py") for p in paths)
        assert warnings == []

    def test_glob_double_star(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**/*.py パターンで再帰的に展開。"""
        monkeypatch.chdir(tmp_path)
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "top.py").write_text("top")
        (sub / "nested.py").write_text("nested")
        paths, _ = _expand_single_path("**/*.py", set())
        assert len(paths) == 2

    def test_glob_no_match_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """マッチなし → 空リスト。"""
        monkeypatch.chdir(tmp_path)
        paths, warnings = _expand_single_path("*.nonexistent", set())
        assert paths == []
        assert warnings == []

    def test_glob_question_mark(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """? パターンで1文字マッチ。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "file1.txt").write_text("1")
        (tmp_path / "file2.txt").write_text("2")
        (tmp_path / "file10.txt").write_text("10")
        paths, _ = _expand_single_path("file?.txt", set())
        assert len(paths) == 2
        names = {Path(p).name for p in paths}
        assert names == {"file1.txt", "file2.txt"}

    def test_glob_matching_directory_expands_contents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """glob がディレクトリにマッチした場合、内容を再帰展開する。"""
        monkeypatch.chdir(tmp_path)
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "nested.py").write_text("nested")
        (tmp_path / "top.py").write_text("top")
        # * パターンで subdir/ にもマッチする
        paths, _ = _expand_single_path("*", set())
        names = {Path(p).name for p in paths}
        assert "nested.py" in names
        assert "top.py" in names


# --- _expand_single_path: シンボリックリンク ---


class TestExpandSinglePathSymlink:
    """_expand_single_path() のシンボリックリンク処理を検証する。"""

    def test_symlink_to_file_resolved(self, tmp_path: Path) -> None:
        """ファイルへのシンボリックリンク → 実体パスに解決。"""
        real_file = tmp_path / "real.py"
        real_file.write_text("real")
        link = tmp_path / "link.py"
        link.symlink_to(real_file)
        paths, warnings = _expand_single_path(str(link), set())
        assert paths == [str(real_file.resolve())]
        assert warnings == []

    def test_symlink_cycle_in_directory_detected(self, tmp_path: Path) -> None:
        """ディレクトリ内のシンボリックリンク循環参照を検出。"""
        dir_a = tmp_path / "dir_a"
        dir_a.mkdir()
        (dir_a / "file.py").write_text("content")
        # dir_a/loop -> dir_a（循環参照）
        loop_link = dir_a / "loop"
        loop_link.symlink_to(dir_a)
        paths, warnings = _expand_single_path(str(dir_a), set())
        # file.py は取得できるが、無限ループしない
        assert any(Path(p).name == "file.py" for p in paths)
        assert len(warnings) > 0

    def test_symlink_cycle_warning_contains_path(self, tmp_path: Path) -> None:
        """循環参照の警告にパス情報を含む。"""
        dir_a = tmp_path / "dir_a"
        dir_a.mkdir()
        (dir_a / "file.py").write_text("content")
        loop_link = dir_a / "loop"
        loop_link.symlink_to(dir_a)
        _, warnings = _expand_single_path(str(dir_a), set())
        assert any("symlink cycle" in w.lower() for w in warnings)

    def test_seen_real_dirs_prevents_revisit(self, tmp_path: Path) -> None:
        """seen_real_dirs に登録済みのディレクトリは再探索しない。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "file.py").write_text("content")
        # sub を既探索としてマーク
        seen = {sub.resolve()}
        paths, warnings = _expand_single_path(str(sub), seen)
        # 既探索のため結果は空（循環参照として扱う）
        assert paths == []
        assert len(warnings) > 0


# --- resolve_files ---


class TestResolveFiles:
    """resolve_files() の統合テストを検証する。"""

    def test_single_file(self, tmp_path: Path) -> None:
        """単一ファイルの解決。"""
        f = tmp_path / "a.py"
        f.write_text("a")
        result, _ = resolve_files((str(f),))
        assert result is not None
        assert len(result.paths) == 1
        assert result.paths[0] == str(f.resolve())

    def test_multiple_files(self, tmp_path: Path) -> None:
        """複数ファイルの解決。"""
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("a")
        f2.write_text("b")
        result, _ = resolve_files((str(f1), str(f2)))
        assert result is not None
        assert len(result.paths) == 2

    def test_directory(self, tmp_path: Path) -> None:
        """ディレクトリの解決。"""
        (tmp_path / "x.py").write_text("x")
        (tmp_path / "y.py").write_text("y")
        result, _ = resolve_files((str(tmp_path),))
        assert result is not None
        assert len(result.paths) == 2

    def test_glob_pattern(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """glob パターンの解決。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        result, _ = resolve_files(("*.py",))
        assert result is not None
        assert len(result.paths) == 1

    def test_mixed_file_and_directory(self, tmp_path: Path) -> None:
        """ファイルとディレクトリの混合入力。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        f = tmp_path / "standalone.py"
        f.write_text("standalone")
        (sub / "nested.py").write_text("nested")
        result, _ = resolve_files((str(f), str(sub)))
        assert result is not None
        assert len(result.paths) == 2

    def test_results_sorted(self, tmp_path: Path) -> None:
        """結果がソート済み。"""
        (tmp_path / "z.py").write_text("z")
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "m.py").write_text("m")
        result, _ = resolve_files((str(tmp_path),))
        assert result is not None
        assert list(result.paths) == sorted(result.paths)

    def test_results_deduplicated(self, tmp_path: Path) -> None:
        """同一ファイルの重複排除。"""
        f = tmp_path / "a.py"
        f.write_text("a")
        result, _ = resolve_files((str(f), str(f)))
        assert result is not None
        assert len(result.paths) == 1

    def test_nonexistent_path_raises_error(self) -> None:
        """存在しないパスで FileResolutionError。"""
        with pytest.raises(FileResolutionError):
            resolve_files(("/nonexistent/path.py",))

    def test_relative_path_resolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """相対パスは cwd から解決。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "rel.py").write_text("rel")
        result, _ = resolve_files(("rel.py",))
        assert result is not None
        assert Path(result.paths[0]).is_absolute()

    def test_absolute_path_accepted(self, tmp_path: Path) -> None:
        """絶対パスを受け入れる。"""
        f = tmp_path / "abs.py"
        f.write_text("abs")
        result, _ = resolve_files((str(f.resolve()),))
        assert result is not None
        assert len(result.paths) == 1

    def test_warnings_collected(self, tmp_path: Path) -> None:
        """シンボリックリンク循環参照の警告が伝播される。"""
        dir_a = tmp_path / "dir_a"
        dir_a.mkdir()
        (dir_a / "file.py").write_text("content")
        (dir_a / "loop").symlink_to(dir_a)
        _, warnings = resolve_files((str(dir_a),))
        assert len(warnings) > 0

    def test_all_empty_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """全パスが空結果 → None。"""
        monkeypatch.chdir(tmp_path)
        # glob パターンでマッチなし → 空
        result, _ = resolve_files(("*.nonexistent_extension",))
        assert result is None

    def test_empty_directory_returns_none(self, tmp_path: Path) -> None:
        """空ディレクトリのみ → None。"""
        empty = tmp_path / "empty"
        empty.mkdir()
        result, _ = resolve_files((str(empty),))
        assert result is None

    def test_duplicate_directory_across_paths_not_skipped(self, tmp_path: Path) -> None:
        """同じディレクトリを複数パスで指定しても循環参照扱いにならない。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "file.py").write_text("content")
        # sub を直接パスで2回指定
        result, warnings = resolve_files((str(sub), str(sub)))
        assert result is not None
        # 重複排除で1ファイル
        assert len(result.paths) == 1
        # 循環参照の警告は出ない（重複排除で処理される）
        assert not any("symlink cycle" in w.lower() for w in warnings)


# --- _is_binary_file ---


class TestIsBinaryFile:
    """_is_binary_file() ヘルパーを検証する。"""

    def test_text_file_returns_false(self, tmp_path: Path) -> None:
        """テキストファイル → False。"""
        f = tmp_path / "text.py"
        f.write_text("# Python code\nprint('hello')")
        assert _is_binary_file(f) is False

    def test_binary_file_with_null_bytes_returns_true(self, tmp_path: Path) -> None:
        """NULL バイトを含むファイル → True。"""
        f = tmp_path / "binary.dat"
        f.write_bytes(b"some\x00data")
        assert _is_binary_file(f) is True

    def test_empty_file_returns_false(self, tmp_path: Path) -> None:
        """空ファイル → False（有効なテキストファイル）。"""
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        assert _is_binary_file(f) is False

    def test_null_byte_at_start_returns_true(self, tmp_path: Path) -> None:
        """先頭が NULL バイト → True。"""
        f = tmp_path / "null_start.bin"
        f.write_bytes(b"\x00rest of file")
        assert _is_binary_file(f) is True

    def test_null_byte_within_check_size_returns_true(self, tmp_path: Path) -> None:
        """チェックサイズ内の NULL バイト → True。"""
        f = tmp_path / "within.dat"
        f.write_bytes(b"a" * 8191 + b"\x00")
        assert _is_binary_file(f) is True

    def test_null_byte_beyond_check_size_returns_false(self, tmp_path: Path) -> None:
        """チェックサイズ（8KB）超過位置の NULL バイト → False。"""
        f = tmp_path / "beyond.dat"
        f.write_bytes(b"a" * 8192 + b"\x00")
        assert _is_binary_file(f) is False

    def test_pyc_like_content_detected(self, tmp_path: Path) -> None:
        """.pyc 風コンテンツ（NULL バイト含む）→ True。"""
        f = tmp_path / "module.pyc"
        f.write_bytes(b"\x3f\r\r\n" + b"\x00" * 100)
        assert _is_binary_file(f) is True


# --- _expand_single_path: バイナリファイル ---


class TestExpandSinglePathBinary:
    """_expand_single_path() のバイナリファイル除外を検証する。"""

    def test_single_binary_file_returns_empty_with_warning(
        self, tmp_path: Path
    ) -> None:
        """単一バイナリファイル指定 → 空結果 + 警告。"""
        binary_file = tmp_path / "data.bin"
        binary_file.write_bytes(b"\xff\xfe\x00\x01")
        paths, warnings = _expand_single_path(str(binary_file), set())
        assert paths == []
        assert len(warnings) == 1

    def test_binary_file_warning_contains_path(self, tmp_path: Path) -> None:
        """バイナリスキップの警告にパス情報を含む。"""
        binary_file = tmp_path / "module.pyc"
        binary_file.write_bytes(b"\x00" * 10)
        _, warnings = _expand_single_path(str(binary_file), set())
        assert any("binary file" in w.lower() for w in warnings)
        assert any(str(binary_file.resolve()) in w for w in warnings)

    def test_directory_with_mixed_text_and_binary(self, tmp_path: Path) -> None:
        """ディレクトリ内にテキスト + バイナリ混在 → テキストのみ返す。"""
        (tmp_path / "code.py").write_text("# Python")
        (tmp_path / "module.pyc").write_bytes(b"\x00\x01\x02")
        (tmp_path / "data.txt").write_text("data")
        paths, warnings = _expand_single_path(str(tmp_path), set())
        assert len(paths) == 2
        path_names = {Path(p).name for p in paths}
        assert path_names == {"code.py", "data.txt"}
        assert len(warnings) == 1
        assert "binary file" in warnings[0].lower()

    def test_nested_pycache_skips_pyc(self, tmp_path: Path) -> None:
        """__pycache__/*.pyc ファイルがスキップされる。"""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        pycache = src_dir / "__pycache__"
        pycache.mkdir()
        (src_dir / "module.py").write_text("# module")
        (pycache / "module.cpython-313.pyc").write_bytes(b"\x00" * 50)
        paths, warnings = _expand_single_path(str(src_dir), set())
        assert len(paths) == 1
        assert paths[0].endswith("module.py")
        assert len(warnings) == 1

    def test_glob_pattern_skips_binary_matches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """glob パターンでバイナリファイルがスキップされる。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "script.py").write_text("print('hi')")
        (tmp_path / "data.bin").write_bytes(b"\x00\xff")
        paths, warnings = _expand_single_path("*", set())
        assert len(paths) == 1
        assert Path(paths[0]).name == "script.py"
        assert len(warnings) == 1


# --- resolve_files: バイナリファイル ---


class TestResolveFilesBinary:
    """resolve_files() のバイナリファイル関連統合テスト。"""

    def test_directory_excludes_binary_from_result(self, tmp_path: Path) -> None:
        """ディレクトリモードでバイナリが除外される。"""
        (tmp_path / "valid.py").write_text("code")
        (tmp_path / "binary.so").write_bytes(b"\x7fELF" + b"\x00" * 100)
        result, _ = resolve_files((str(tmp_path),))
        assert result is not None
        assert len(result.paths) == 1
        assert result.paths[0].endswith("valid.py")

    def test_binary_warning_in_result(self, tmp_path: Path) -> None:
        """バイナリスキップの警告が結果に含まれる。"""
        (tmp_path / "code.py").write_text("code")
        (tmp_path / "image.bin").write_bytes(b"\xff\xfe" + b"\x00" * 50)
        _, warnings = resolve_files((str(tmp_path),))
        assert len(warnings) > 0
        assert any("binary file" in w.lower() for w in warnings)

    def test_all_binary_files_returns_none(self, tmp_path: Path) -> None:
        """全ファイルがバイナリ → None。"""
        (tmp_path / "a.pyc").write_bytes(b"\x00\x01\x02")
        (tmp_path / "b.so").write_bytes(b"\x7fELF\x00")
        result, _ = resolve_files((str(tmp_path),))
        assert result is None

    def test_all_binary_warnings_preserved_on_none(self, tmp_path: Path) -> None:
        """全バイナリで None 時も警告が保存される。"""
        (tmp_path / "a.pyc").write_bytes(b"\x00\x01\x02")
        (tmp_path / "b.so").write_bytes(b"\x7fELF\x00")
        result, warnings = resolve_files((str(tmp_path),))
        assert result is None
        assert len(warnings) == 2
        assert all("binary file" in w.lower() for w in warnings)


# --- _resolve_if_text: OSError ハンドリング ---


class TestResolveIfText:
    """_resolve_if_text() のテスト。"""

    def test_text_file_returns_path(self, tmp_path: Path) -> None:
        """テキストファイル → (パス, None)。"""
        f = tmp_path / "text.py"
        f.write_text("# code")
        path_str, warning = _resolve_if_text(f)
        assert path_str == str(f.resolve())
        assert warning is None

    def test_binary_file_returns_warning(self, tmp_path: Path) -> None:
        """バイナリファイル → (None, 警告)。"""
        f = tmp_path / "binary.dat"
        f.write_bytes(b"\x00data")
        path_str, warning = _resolve_if_text(f)
        assert path_str is None
        assert warning is not None
        assert "binary file" in warning.lower()

    def test_unreadable_file_returns_warning(self, tmp_path: Path) -> None:
        """読み取り権限なしのファイル → (None, 警告)。"""
        f = tmp_path / "no_read.py"
        f.write_text("content")
        f.chmod(0o000)
        try:
            path_str, warning = _resolve_if_text(f)
            assert path_str is None
            assert warning is not None
            assert "unreadable file" in warning.lower()
        finally:
            f.chmod(0o644)

    def test_unreadable_file_skipped_in_directory(self, tmp_path: Path) -> None:
        """ディレクトリ内の読み取り不可ファイルがスキップされる。"""
        (tmp_path / "readable.py").write_text("content")
        no_read = tmp_path / "no_read.py"
        no_read.write_text("secret")
        no_read.chmod(0o000)
        try:
            paths, warnings = _expand_single_path(str(tmp_path), set())
            assert len(paths) == 1
            assert Path(paths[0]).name == "readable.py"
            assert any("unreadable file" in w.lower() for w in warnings)
        finally:
            no_read.chmod(0o644)

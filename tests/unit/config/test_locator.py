"""プロジェクト探索のテスト。

T010: find_project_root — カレント, 親, 見つからない
T011: find_config_file — ルートあり → パス構築, ルートなし → None
T012: find_pyproject_toml — カレント, 親, 見つからない, 独立探索
T013: get_user_config_path — ~/.config/hachimoku/config.toml
"""

from __future__ import annotations

from pathlib import Path

from hachimoku.config._locator import (
    find_config_file,
    find_project_root,
    find_pyproject_toml,
    get_user_config_path,
)

# =============================================================================
# ヘルパー
# =============================================================================

_PROJECT_DIR_NAME = ".hachimoku"


def _create_project_dir(base: Path) -> Path:
    """base に .hachimoku/ ディレクトリを作成し base を返す。"""
    (base / _PROJECT_DIR_NAME).mkdir()
    return base


def _create_pyproject_toml(base: Path) -> Path:
    """base に pyproject.toml を作成し、そのパスを返す。"""
    path = base / "pyproject.toml"
    path.write_text("[project]\nname = 'test'\n", encoding="utf-8")
    return path


# =============================================================================
# T010: find_project_root()
# =============================================================================


class TestFindProjectRootInCurrent:
    """カレントディレクトリに .hachimoku/ がある場合。"""

    def test_returns_current_directory(self, tmp_path: Path) -> None:
        """カレントに .hachimoku/ あり → そのパスを返す。"""
        _create_project_dir(tmp_path)
        result = find_project_root(tmp_path)
        assert result == tmp_path.resolve()


class TestFindProjectRootInParent:
    """親ディレクトリに .hachimoku/ がある場合。"""

    def test_returns_parent_directory(self, tmp_path: Path) -> None:
        """親に .hachimoku/ あり → 親パスを返す。"""
        _create_project_dir(tmp_path)
        child = tmp_path / "src" / "subdir"
        child.mkdir(parents=True)
        result = find_project_root(child)
        assert result == tmp_path.resolve()


class TestFindProjectRootNotFound:
    """ルートまで見つからない場合。"""

    def test_returns_none(self, tmp_path: Path) -> None:
        """ルートまで見つからない → None。"""
        result = find_project_root(tmp_path)
        assert result is None


# =============================================================================
# T011: find_config_file()
# =============================================================================


class TestFindConfigFileFound:
    """プロジェクトルートが見つかる場合。"""

    def test_returns_config_toml_path(self, tmp_path: Path) -> None:
        """プロジェクトルートあり → .hachimoku/config.toml のパスを返す。"""
        _create_project_dir(tmp_path)
        result = find_config_file(tmp_path)
        expected = tmp_path.resolve() / ".hachimoku" / "config.toml"
        assert result == expected

    def test_path_constructed_without_file_existence(self, tmp_path: Path) -> None:
        """config.toml が実際に存在しなくてもパスを構築する。"""
        _create_project_dir(tmp_path)
        result = find_config_file(tmp_path)
        assert result is not None
        assert not result.exists()


class TestFindConfigFileNotFound:
    """プロジェクトルートが見つからない場合。"""

    def test_returns_none(self, tmp_path: Path) -> None:
        """プロジェクトルートなし → None。"""
        result = find_config_file(tmp_path)
        assert result is None


# =============================================================================
# T012: find_pyproject_toml()
# =============================================================================


class TestFindPyprojectTomlInCurrent:
    """カレントディレクトリに pyproject.toml がある場合。"""

    def test_returns_pyproject_path(self, tmp_path: Path) -> None:
        """カレントに pyproject.toml あり → そのパスを返す。"""
        _create_pyproject_toml(tmp_path)
        result = find_pyproject_toml(tmp_path)
        assert result == tmp_path.resolve() / "pyproject.toml"


class TestFindPyprojectTomlInParent:
    """親ディレクトリに pyproject.toml がある場合。"""

    def test_returns_parent_pyproject_path(self, tmp_path: Path) -> None:
        """親に pyproject.toml あり → そのパスを返す。"""
        _create_pyproject_toml(tmp_path)
        child = tmp_path / "src"
        child.mkdir()
        result = find_pyproject_toml(child)
        assert result == tmp_path.resolve() / "pyproject.toml"


class TestFindPyprojectTomlNotFound:
    """見つからない場合。"""

    def test_returns_none(self, tmp_path: Path) -> None:
        """見つからない → None。"""
        result = find_pyproject_toml(tmp_path)
        assert result is None


class TestFindPyprojectTomlIndependentSearch:
    """pyproject.toml と .hachimoku/ の独立探索 (FR-CF-005)。"""

    def test_different_directories(self, tmp_path: Path) -> None:
        """.hachimoku/ と pyproject.toml が異なるディレクトリにある場合、独立に検出。"""
        # pyproject.toml は grandparent に配置
        grandparent = tmp_path
        _create_pyproject_toml(grandparent)

        # .hachimoku/ は parent に配置
        parent = grandparent / "project"
        parent.mkdir()
        _create_project_dir(parent)

        # child から探索
        child = parent / "src"
        child.mkdir()

        # find_project_root は parent を返す
        assert find_project_root(child) == parent.resolve()
        # find_pyproject_toml は grandparent の pyproject.toml を返す
        assert find_pyproject_toml(child) == grandparent.resolve() / "pyproject.toml"


# =============================================================================
# T013: get_user_config_path()
# =============================================================================


class TestGetUserConfigPath:
    """ユーザーグローバル設定パスのテスト。"""

    def test_returns_expected_path(self) -> None:
        """~/.config/hachimoku/config.toml のパスを返す。"""
        result = get_user_config_path()
        expected = Path.home() / ".config" / "hachimoku" / "config.toml"
        assert result == expected

    def test_return_type_is_path(self) -> None:
        """戻り値が Path インスタンスであること。"""
        result = get_user_config_path()
        assert isinstance(result, Path)

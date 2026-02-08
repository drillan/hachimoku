def main() -> None:
    """パッケージエントリポイント。cli.main() に委譲する。

    pyproject.toml の [project.scripts] は hachimoku.cli:main を直接参照するため、
    この関数はスクリプトエントリポイントとしては呼ばれない。
    プログラムから hachimoku.main() として呼び出す場合の互換用。
    """
    from hachimoku.cli import main as cli_main

    cli_main()

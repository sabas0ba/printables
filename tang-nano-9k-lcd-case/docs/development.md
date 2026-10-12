# 開発手順

## 生成環境

生成環境はリポジトリ直下の`flake.nix`、`pyproject.toml`、`uv.lock`で固定している。構築手順と全設計の一括検証は[リポジトリのREADME](../../README.md)に記載している。

この設計が使用する依存は次のとおりである。

- STL生成（`tools/generate_stl.py`、`tools/profiles.py`）: Python標準ライブラリのみ
- レンダリング（`tools/create_visuals.py`）: Matplotlib、NumPy、ReportLab
- 図面と設計書（`tools/create_scale_drawing.py`、`tools/create_retention_design.py`）: ReportLab
- PDFのフォント: DejaVu Sans。flakeの開発シェルが`DEJAVU_FONT_PATH`で指定する

## 生成とテスト

リポジトリ直下で実行する。

```sh
nix develop --command .venv/bin/python tang-nano-9k-lcd-case/generate.py
nix develop --command .venv/bin/python tang-nano-9k-lcd-case/render.py
nix develop --command .venv/bin/python -m unittest discover -s tang-nano-9k-lcd-case/tests
```

`generate.py`は`stl/<profile>/`、`render.py`は`output/<profile>/images/`と`output/<profile>/pdf/`へ出力する。生成物はGit管理し、CIが`scripts/generate_all.py --check`でコミット済みのファイルとバイト単位で比較する。寸法や図面を変更した場合は、再生成したファイルを同じcommitに含める。

## LCDプロファイル

LCDに依存する寸法は`tools/profiles.py`の`CaseProfile`に定義する。STL生成、断面図、レンダリング、原寸図および固定設計書は、すべて同じプロファイルから寸法を取得する。共通の機構寸法（壁厚、スナップ形状、基板保持、奥行き基準）は`tools/generate_stl.py`に置く。

座標系は背面から見た向きで、ベゼル左下を原点とし、USB-C側を下（y小）とする。データシートの外形図は通常前面から見た向きで描かれているため、表示領域とFPCの左右方向の位置は鏡像変換して登録する。

プロファイルを追加する手順は次のとおりである。

1. データシートの外形図から、LCD外形、表示領域とその位置、FPCの出る辺と範囲を`LcdModule`へ登録する。出典の版とページを注記する。
2. `CaseProfile`に本体外形、リテーナー開口、各スナップの位置、コネクタ開口、背面板スロット位置を定義する。基板端と壁内面の距離が1 mmを超える場合は、`PortBulkhead`でリアカバーのコネクタ隔壁を定義する。
3. `PROFILES`へ登録し、`tests/test_stl.py`の`EXPECTED_BOUNDS`へ各STLの外形境界を追加する。
4. `design.toml`の部品表へ新しいプロファイルのSTLを追加し、`scripts/build_site.py --write-readme`で設計一覧を更新する。
5. STL、PNG、PDFを再生成し、メッシュ、組立干渉、断面位置、図面レイアウトの各テストを通す。

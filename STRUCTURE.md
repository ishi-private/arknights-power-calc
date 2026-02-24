# プロジェクト構成

アークナイツ キャラ火力計算ツールのフォルダ構成。

```
arknights-power-calc/
├── .claude/
│   └── settings.local.json
├── app/
│   ├── power_calc.py
│   └── update_structure.py
├── src/
│   ├── .claude/
│   │   └── settings.local.json
│   ├── images/  （126 ファイル）
│   ├── xlsx/  （115 ファイル）
│   └── arknights_star6.csv
├── .gitattributes
├── .gitignore
└── STRUCTURE.md
```

## 各ファイルの説明

### app/power_calc.py
Python 製 CLI ツール。主な機能：
- キャラ・スキル・ランク選択（ランク1〜7、特化I/II/III）
- ダメージ計算（物理 / 術、軽減前・軽減後・総ダメージ・DPS）
- 計算結果を `src/calc_log.txt` にタイムスタンプ付きで追記
- 実行: `python app/power_calc.py`（リポジトリルートから）
- 実装詳細: `app/power_calc_doc.md` を参照

### app/power_calc_doc.md
`power_calc.py` の実装内容・ロジックのドキュメント。
関数一覧・スパース xlsx 解析アルゴリズム・ダメージ計算式・データ構造・制限事項を記載。
コードを変更した際は合わせて更新すること。

### src/arknights_star6.csv
列構成: 画像, 名前, 職業, 職分, HP, 攻撃力, 防御力, 術耐性, 再配置, コスト, ブロック数, 攻撃速度, 入手方法, 募集タグ
- 攻撃力には信頼度ボーナス（+25）が含まれている

### src/xlsx/{キャラ名}.xlsx
シート構成:
- `スキルN 名前`  : スキル概要
- `スキルN 名前1` : ランク別詳細データ（解析対象）
  - 列 A: ランク（1〜7, 特化I/II/III）
  - 列 B〜E: 初期SP / 必要SP / 持続 / 効果テキスト（スパース形式）

スキルデータがないキャラ（12体）: W, ケルシー, リィン, レイディアン, マントラ, 聖聆プラマニクス, 溯光アステジーニ, 凛御シルバーアッシュ, ナスティ, ティティ, 赤刃明霄チェン, ウァン

## 構成変更時のルール

- ディレクトリ追加・移動・削除を行ったときは、このファイルを更新する
- `app/power_calc.py` のパス定数（`DATA_DIR`）も必要に応じて更新する

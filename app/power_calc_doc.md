# power_calc.py 実装ドキュメント

`app/power_calc.py` の実装内容・ロジックの記録。
コードを変更した際はこのファイルも更新すること。

---

## 目次

1. [概要](#概要)
2. [実行方法・起動フロー](#実行方法起動フロー)
3. [定数・パス設定](#定数パス設定)
4. [関数一覧](#関数一覧)
5. [主要ロジック詳解](#主要ロジック詳解)
   - [スパース左詰めxlsx解析](#スパース左詰めxlsx解析)
   - [攻撃倍率の正規表現抽出](#攻撃倍率の正規表現抽出)
   - [ダメージ計算式](#ダメージ計算式)
6. [データ構造](#データ構造)
7. [既知の制限・注意事項](#既知の制限注意事項)

---

## 概要

アークナイツ（明日方舟）の6★キャラのスキル火力を計算する Python 製 CLI ツール。

**計算できる値:**
- スキル発動時のダメージ（軽減前）
- 実ダメージ（敵の防御・術耐性による軽減後）
- スキル継続中の総ダメージ
- スキル中 DPS（ダメージ / 秒）

**依存ライブラリ:**
- `openpyxl` — xlsx ファイルの読み込み
- 標準ライブラリのみ（csv, os, sys, re, io, datetime）

---

## 実行方法・起動フロー

```
python app/power_calc.py   # リポジトリルートから実行
```

```
main()
 └─ load_characters()          # CSV を一度だけ読み込む
 └─ ループ:
     └─ calc_session()         # 1回分の計算セッション
         ├─ キャラ選択（名前/番号/部分一致）
         ├─ load_skills()      # xlsx 読み込み
         ├─ スキル選択
         ├─ ランク選択
         ├─ ダメージ種別選択（物理 or 術、自動推定あり）
         ├─ 敵ステータス入力
         ├─ calc_damage()      # ダメージ計算
         ├─ calc_total_damage() # 総ダメージ計算
         └─ 結果表示 + calc_log.txt に追記
```

---

## 定数・パス設定

```python
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))       # app/
DATA_DIR    = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "src"))
CSV_FILE    = os.path.join(DATA_DIR, "arknights_star6.csv")
XLSX_DIR    = os.path.join(DATA_DIR, "xlsx")
LOG_FILE    = os.path.join(DATA_DIR, "calc_log.txt")
```

`__file__` を基準にパスを解決しているため、どのディレクトリから実行しても動作する。

```python
SKILL_RANK_ORDER = ["1","2","3","4","5","6","7","特化I","特化II","特化III"]
RANK_DISPLAY     = {"特化I": "特化Ⅰ", ...}  # 表示用マッピング
```

**Windows UTF-8 対応:**
Windows の標準出力は CP932 のため、起動時に `io.TextIOWrapper` で強制的に UTF-8 に差し替える。

```python
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8")
```

---

## 関数一覧

### データ読み込み系

#### `parse_atk_speed(s: str) -> float`
`"1.25s(やや遅い)"` などの文字列から秒数を抽出。正規表現 `(\d+(?:\.\d+)?)s` を使用。マッチしない場合は `1.0` を返す。

#### `load_characters() -> list[dict]`
`arknights_star6.csv` を読み込み、キャラ辞書のリストを返す。
スキップ条件: 行数不足・名前が空・名前が `"名前"`（テンプレート行）・ATK が 0 または非数値。
CSV の ATK 値には信頼度ボーナス（+25）が既に含まれている。

**返値の辞書キー:**
| キー | 型 | 内容 |
|---|---|---|
| name | str | キャラ名 |
| class | str | 職業（例: 術師, 前衛） |
| subclass | str | 職分（例: 核心術師） |
| atk | int | 攻撃力（信頼度込み） |
| atk_speed | float | 攻撃間隔（秒） |
| hp, def, res | int | HP・防御・術耐性 |
| cost, block | int | コスト・ブロック数 |

---

### スキルデータ解析系

#### `_closest_field(value, prev_init, prev_cost, prev_dur) -> str`
スパース左詰め形式の xlsx において、1つの数値がどのフィールド（init/cost/dur）を表すか判定する内部関数。
→ 詳細は[スパース左詰めxlsx解析](#スパース左詰めxlsx解析)を参照。

#### `_update_state(prev_init, prev_cost, prev_dur, numerics) -> tuple`
数値リスト（長さ 0〜3）から `(init_sp, cost_sp, duration)` の状態を更新する。
- 長さ 3 → そのまま `init, cost, dur` に代入
- 長さ 2 → `_closest_field()` で v1 を特定、残りフィールドで v2 を特定
- 長さ 1 → `_closest_field()` で単一フィールドを特定

#### `parse_damage_multiplier(effect: str) -> float | None`
効果テキストから攻撃倍率を抽出する。→ [攻撃倍率の正規表現抽出](#攻撃倍率の正規表現抽出)を参照。

#### `parse_skill_sheet(ws) -> dict`
xlsx のスキル詳細シート（`スキルN 名前1`）を解析し、ランクごとのデータ辞書を返す。

処理フロー:
1. 全行を `{列名: 値}` の辞書リストに変換（None セルは除外）
2. ヘッダー行をスキップし、A列がランク名の行のみ処理
3. B〜E 列の値を数値・効果テキスト・`"-"` に分類
4. `"-"` は持続なし（`None`）として扱う
5. `_update_state()` で状態を更新し、`parse_damage_multiplier()` で倍率を抽出

**返値:**
```python
{
  "特化III": {
    "init_sp":    int | None,
    "cost_sp":    int | None,
    "duration":   float | None,   # None = 持続なし（瞬時/パッシブ）
    "effect":     str | None,     # 効果テキスト
    "multiplier": float | None,   # 攻撃倍率（1.0 = 等倍）
  },
  ...
}
```

#### `load_skills(char_name: str) -> list[dict] | None`
キャラ名に対応する `xlsx/{キャラ名}.xlsx` を読み込む。
シート名が `スキルN 名前1`（末尾が `1`）のシートのみ解析対象。
xlsx ファイルが存在しないキャラには `None` を返す。

---

### ダメージ計算系

#### `calc_damage(atk, multiplier, enemy_def, enemy_res, is_arts) -> tuple[float, float]`
`(軽減前ダメージ, 軽減後ダメージ)` を返す。→ [ダメージ計算式](#ダメージ計算式)を参照。

#### `calc_total_damage(actual_per_hit, duration, atk_speed, targets) -> float | None`
スキル継続中の総ダメージを返す。
`hits = int(duration / atk_speed)` でヒット数を算出（端数切り捨て）。
`duration` が `None` または 0 以下の場合は `None` を返す。

---

### ユーティリティ系

#### `fmt_sp(val) -> str`
`None` → `"-"`、それ以外 → `str(val)` に変換。
`val or "-"` とすると `0` が falsy で `"-"` になってしまうバグを回避するために用意。

#### `input_int(prompt, default) -> int`
整数入力プロンプト。空入力でデフォルト値を返す。

#### `select_from_list(items, prompt, display_fn) -> int`
番号付きリスト選択。0-indexed の選択インデックスを返す。

---

### メイン系

#### `calc_session(characters)`
1回分の対話計算セッション。選択・入力・計算・出力を一貫して行う。
結果は画面表示と同時に `src/calc_log.txt` にタイムスタンプ付きで追記される。

**ダメージ種別の自動推定ロジック:**
```python
arts_auto = (
    char["class"] == "術師"          # 職業が術師
    or "術ダメージ" in rank_data["effect"]  # 効果テキストに「術ダメージ」
)
```
ユーザーはデフォルト選択（Enter）で推定に従うか、手動で上書きできる。

#### `main()`
エントリーポイント。`load_characters()` で CSV を一度読み込み、`calc_session()` を while ループで繰り返す。
`KeyboardInterrupt` / `EOFError` で正常終了。

---

## 主要ロジック詳解

### スパース左詰めxlsx解析

xlsx のスキル詳細シートは以下の形式。変化しなかったフィールドは省略され、残りの値が左詰めになる。

```
列:   A        B       C      D        E
      ランク   初期SP  必要SP  持続     効果
rank1    0      50      -     効果テキスト
rank2           45             効果テキスト   ← cost のみ変化 → B=45, C=効果
rank3    0      40      -     効果テキスト   ← init,cost,dur 全変化
```

**判定アルゴリズム (`_closest_field`):**

各フィールドには変化方向の制約がある:
- `init_sp`: ランクが上がると**増加**（または不変）
- `cost_sp`: ランクが上がると**減少**（または不変）
- `duration`: ランクが上がると**増加**（または不変）

この制約を使って候補フィールドを絞り、さらに前の値との差が**最小**のものを選択する。

```python
# init 候補: value > prev_init
# cost 候補: value < prev_cost
# dur  候補: value > prev_dur
# → 条件を満たす候補のうち差が最小のフィールドを選択
return min(dists, key=dists.get)
```

**2値の場合の処理順序:**
1. v1 のフィールドを判定
2. v1 が使ったフィールドを候補から除外し、残りで v2 を判定

**検証例:**
| キャラ | ランク | 数値列 | 判定結果 |
|---|---|---|---|
| スルト スキル2 | 特化I | [10, 21] | init=10, cost=21 |
| ソーンズ スキル2 | rank2 | [34, 31] | cost=34, dur=31 |
| スカジ スキル3 | rank4 | [55, 38] | init=55, dur=38 |

---

### 攻撃倍率の正規表現抽出

`parse_damage_multiplier()` は以下の順で試行する。

| # | パターン例 | 正規表現 | 変換式 |
|---|---|---|---|
| 1 | `攻撃力が350%まで上昇` | `攻撃力[がが](\d+...)%[まにに]で?上昇` | `X / 100` |
| 2 | `攻撃力+130%` | `攻撃力[^+\n]*?\+(\d+...)%` | `1 + X/100` |
| 2 | `攻撃力、防御力、最大HP+130%` | 同上（`[^+\n]*?` で間の文字列を読み飛ばす） | `1 + X/100` |
| 3 | `攻撃力×3.5` | `攻撃力[××x](\d+...)` | `X`（そのまま） |

いずれにもマッチしない場合は `None` を返し、`calc_session()` でユーザーに手動入力を求める。

---

### ダメージ計算式

#### 物理ダメージ
```
raw    = ATK × multiplier
actual = max(raw - DEF,  raw × 0.05)
```
最小保証: raw の 5%（防御貫通下限）

#### 術ダメージ
```
raw       = ATK × multiplier
reduction = min(RES / 100, 0.95)   # 最大 95% 軽減
actual    = raw × (1 - reduction)
```
最小保証: raw の 5%（術耐性 95 が上限）

#### 総ダメージ・DPS
```
hits        = int(duration / atk_speed)   # 端数切り捨て
total       = actual × hits × targets
DPS         = actual / atk_speed × targets
```

---

## データ構造

### キャラ辞書（`load_characters` 返値の要素）

```python
{
    "name":          str,    # キャラ名
    "class":         str,    # 職業
    "subclass":      str,    # 職分
    "atk":           int,    # 攻撃力（信頼度ボーナス込み）
    "atk_speed":     float,  # 攻撃間隔（秒）
    "atk_speed_str": str,    # 攻撃速度の元テキスト
    "hp":            int,
    "def":           int,
    "res":           int,
    "cost":          int,
    "block":         int,
    "redeploy":      str,
    "source":        str,    # 入手方法
    "tags":          str,    # 募集タグ
    "image":         str,    # 画像ファイル名
}
```

### スキル辞書（`load_skills` 返値の要素）

```python
{
    "num":   int,   # スキル番号（1/2/3）
    "name":  str,   # スキル名
    "ranks": {
        "特化III": {
            "init_sp":    int | None,
            "cost_sp":    int | None,
            "duration":   float | None,
            "effect":     str | None,
            "multiplier": float | None,
        },
        ...
    }
}
```

---

## 既知の制限・注意事項

**スキルデータなし（12体）**
xlsx ファイルが存在せず計算不可:
W, ケルシー, リィン, レイディアン, マントラ, 聖聆プラマニクス, 溯光アステジーニ,
凛御シルバーアッシュ, ナスティ, ティティ, 赤刃明霄チェン, ウァン

**倍率の自動解析失敗ケース**
以下のような特殊記述は自動解析できず、手動入力が必要:
- 条件付き倍率（例: HP に応じて変動）
- 複数回攻撃の個別倍率記述
- 非標準表記

**持続時間なし（瞬時/パッシブ型スキル）**
`duration = None` の場合、総ダメージ・DPS の計算はスキップ。
代わりに通常攻撃 DPS（`ATK / atk_speed`）を参考表示する。

**ATK 値について**
CSV の ATK 値は信頼度ボーナス（+25）を含む最大値。
モジュール強化や潜在能力による ATK 上昇は反映されていない。

**ヒット数の計算**
`int(duration / atk_speed)` で端数切り捨て。アークナイツ公式の挙動と
完全に一致しない場合がある（攻撃判定タイミングによる誤差）。

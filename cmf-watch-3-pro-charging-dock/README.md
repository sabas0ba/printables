# CMF Watch 3 Pro 充電 dock

CMF Watch 3 Pro を文字盤を上にして机に平置きしたまま充電するための dock です。付属の充電ケーブルは先端の小さな磁気充電 head だけで時計を支える構造のため、時計を上向きに置くと head を支点に傾き、ケーブルに引かれて外れやすくなります。この dock は時計の裏面外周を環状の座で受け、head を座の下の pocket に収め、ケーブルを溝に収めて互い違いの返しで押さえます。band は外さずに両端から垂らします。

状態: prototype。時計の寸法は公開値ですが、充電 head、ケーブル、裏面の充電端子位置は実測前の仮の値です。実機を測って `generate.py` の parameter を更新し、`coupon.stl` で嵌合を確認してから `dock.stl` を印刷してください。

- [`dock.stl`](dock.stl): dock 本体、64 × 40 × 14 mm、一体、サポート不要。
- [`coupon.stl`](coupon.stl): pocket から溝の出口までを切り出した 44 × 28 × 14 mm の嵌合確認用 coupon。dock の前に印刷して head の嵌合、ケーブル溝の幅、返しの下へのケーブルの通しやすさ、座に対する head の高さを確認します。
- [`generate.py`](generate.py): CadQuery の parametric source。単位は mm。
- [`render.py`](render.py): 画像の決定的な offline 生成。
- [`views.png`](views.png): 三面図と coupon。
- [`sections.png`](sections.png): 返しの位置での溝の横断面と、返しを通る溝の縦断面。
- [`preview.png`](preview.png): 斜視図。
- [`usage.png`](usage.png): 時計、band、充電 head、ケーブルの簡略化した stand-in を置いた使用状態。製品形状ではなく配置を示します。

![斜視図](preview.png)

![三面図と coupon](views.png)

![溝の断面](sections.png)

![使用状態](usage.png)

## 構造

- **環状の座。** 上面に直径 47.5 mm、深さ 3 mm の円形の窪みがあり、その底面の半径 19 mm から外側が時計の裏面外周を受ける座です。座の内側は 2 mm 下げてあり、裏面中央のセンサ部が当たりません。時計の荷重は head ではなく座にかかります。
- **head の pocket。** 座の内側に、裏面の充電端子位置に合わせて中心から 6 時側に 7 mm ずらした長円形の pocket があります。pocket の底は head の上面が座面と同じ高さになる深さです。spring pin は head の housing より上に出るので、時計が座に乗った状態で pin が押し込まれ、接触圧が確保されます。
- **ケーブル溝。** pocket から 3 時側の側面まで、幅 3.0 mm の上開きの溝がケーブルを座面より下に保持します。ケーブルを引いても head が pocket から持ち上がりません。
- **返し。** 溝の両壁から交互に 3 か所、長さ 2 mm の庇が溝幅の半分 (1.5 mm) まで張り出し、ケーブルがまっすぐ上に抜けるのを防ぎます。ケーブルは、返しのない側の隙間 (1.5 mm) から斜めに押し込み、返しの下へ横滑りさせて蛇行させます。返しは座の環の中に 1 か所、外周部に 2 か所あり、head 側の 1 か所は上面が座面と同じ高さです。
- **被覆の保護。** 返しの先端は 0.25 mm で丸め、溝の上縁は全長にわたり 0.5 mm で丸め、側面出口の床縁は 1 mm で丸めています。返しの下面は 45 度の斜面で、ケーブルが当たる角がありません。
- **band の逃げ。** 本体の奥行き 40 mm は時計の直径 47 mm より短く、12 時と 6 時の両端で lug が本体の外に出ます。band はそのまま両端から垂らします。
- **位置決め。** 座の壁は 3 時側と 9 時側に円弧として残り、時計の位置を決めます。壁の高さは 3 mm で、側面の竜頭やボタンには届きません。

## 仮の値と実測項目

次の値は実測前の placeholder です。実機で測った値に置き換えてください。

| Parameter | 仮の値 | 測る対象 |
| --- | --- | --- |
| `PUCK_LENGTH` | 18.0 | head のケーブル方向の長さ |
| `PUCK_WIDTH` | 8.0 | head の幅。円形なら長さと同じ値 |
| `PUCK_HEIGHT` | 5.0 | head の housing の高さ。spring pin を含めない |
| `PUCK_ANGLE` | 0 | pin の並びに対するケーブルの出方向。0 で 3 時側に出る |
| `CABLE_DIAMETER` | 2.6 | ケーブル外径。根元に補強部があればその幅 |
| `LIP_POSITIONS` | 20.8, 25.5, 30.0 | 返しの位置 (pocket 中心からの距離) と張り出す側。座の段差をまたがない位置にする |
| `LIP_REACH` | 1.5 | 返しの張り出し量。残る隙間でケーブルを斜めに通せる値にする |
| `PAD_OFFSET` | (0, -7) | 裏面の充電端子の中心の、本体中心からの offset |
| `SEAT_INNER_RADIUS` | 19.0 | 裏面外周の平らな部分の内側の半径 |
| `SENSOR_CLEARANCE` | 2.0 | センサ部の出っ張りの高さに余裕を加えた値 |
| `CASE_CLEARANCE` | 0.5 | 裏面側の面取りに応じて調整 |

公開値から取った値は `CASE_DIAMETER` 47.0、`CASE_THICKNESS` 14.4、`STRAP_WIDTH` 22.0 です。

## 実機到着後の手順

1. head、ケーブル、時計裏面を測り、`generate.py` の parameter を更新する。
2. リポジトリの README の手順で `generate.py` と `render.py` を実行する。`generate.py` は pocket の底の厚さ、pocket と座の干渉、サポートが必要な面の有無を検査し、問題があれば停止する。
3. `coupon.stl` を印刷し、head が pocket に入ること、ケーブルが溝に収まり返しの下へ通せること、head の上面が座面と同じ高さになることを確認する。head が低ければ `PUCK_PROUD` を正に、高ければ負にして再生成する。pocket が固ければ `PUCK_CLEARANCE` を増やす。ケーブルが返しの下へ通らなければ `LIP_REACH` を減らし、通した後に浮くようなら増やす。
4. `dock.stl` を印刷し、時計を置いて充電表示が出ることと、ケーブルを軽く引いても外れないことを確認する。

## 印刷

上面の窪みと溝はすべて上から切り込んだ形状で、底面は平面です。そのまま底面を bed に置いて印刷し、サポートは不要です。返しの下面は 45 度の斜面で、先端の厚さは 0.6 mm です。`generate.py` は 45 度より急な下向きの面がないことを検査します。材料は PLA または PETG で、中実換算で約 34 g です。座面の高さ精度が head との高さ関係に直接影響するため、最初の層の潰れ量を考慮して coupon で確認してください。

## 出典と前提

- [GSMArena: CMF Watch 3 Pro launches](https://www.gsmarena.com/cmf_watch_3_pro_launches_with_bigger_143_screen_longer_battery_life_and_higher_price_tag-news-68721.php): **47 × 47 × 14.4 mm**、**22 mm** の着脱式 strap。
- [Nothing Support: Is the charging cable for Watch 3 Pro compatible with that of Watch Pro 2?](https://support.nothing.tech/hc/en-us/articles/37210046739729-Is-the-charging-cable-for-Watch-3-Pro-compatible-with-that-of-Watch-Pro-2): Watch 3 Pro のケーブルは Watch Pro / Pro 2 と非互換。head の寸法は旧機種用の資料から転用せず、実測します。
- [TechRadar](https://www.techradar.com/health-fitness/smartwatches/cmf-watch-3-pro-review)、[Wareable](https://www.wareable.com/smartwatches/cmf-watch-3-pro-review)、[Android Police](https://www.androidpolice.com/i-tried-nothing-cmf-watch-pro-3-disappointed/) のレビュー: 充電 head の磁力が弱く、わずかな衝撃で外れる。

次の値は設計上の選択で、実機では確認していません。

- 充電端子は裏面のセンサ下側にあるという公式 manual の記述から、pocket を 6 時側に 7 mm ずらしています。
- head は 18 × 8 × 5 mm の長円形、ケーブル外径 2.6 mm と仮定しています。
- 座の内径 19 mm、センサ逃げ 2 mm は 47 mm の本体に対する推定値です。

STL は Python 3.12 と CadQuery 2.7.0 で生成し、画像は NumPy 2.3.5 と Pillow 12.3.0 で描画しています。再生成と検証は[リポジトリの README](../README.md) の Nix と container の手順に従ってください。

License: [CC BY-SA 4.0](../LICENSE.md)。本 design は独立した accessory であり、Nothing Technology の公式製品ではありません。CMF と Nothing は各権利者の商標であり、対応機種を示す目的でのみ使用しています。

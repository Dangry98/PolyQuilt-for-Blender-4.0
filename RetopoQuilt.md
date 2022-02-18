# Reropo Quilt

PolyQUiltとは操作形態が大きく異なるのでRetopQuiltというカテゴリーに分けました。
将来的にはBlenderにリトポロジーモードが搭載される計画があるのでそちらに統合する予定です。

## Quad Patch
PolyQuiltアイコンのアイコンから利用します。

---

### 基本操作

- マウス左ボタン＋ドラッグ
ストロークによるエッジパスを描画します。分割数はオプションの距離により算出されます。また左下の調整パネルから分割数の変更ができます。
 
- エッジ選択状態でマウス左ボタン＋ドラッグ
選択エッジとストロークの間をブリッジする面を貼ります。スライス分割数はオプションの距離により算出されます。
また左下の調整パネルから分割数の変更ができます。
また頂点からのストロークを描くと選択エッジとの接続辺を元にしたクアッドパッチが張られるます。


### 選択操作 
 
- 辺の上でクリックorドラッグ
辺の選択を行います。
 
- 選択された辺の端の隣でクリックorドラッグ
辺の追加選択を行います。
 
- 選択された辺の端でクリックorドラッグ
辺の部分選択解除を行います。
 
- 辺の上でホールド
エッジループの選択を行います。
 
- 選択された辺の端でホールド
エッジサーキットの選択を行います。
 
- 空エリアをクリック
選択解除

### Cooper

Cooperは「樽職人」と言う意味で樽のような輪切りの形状のトポロジーを作るのに使います。

- マウス左ボタンホールド＋ドラッグ
チューブ状のトポロジーをスライスします。スライス分割数はオプションの距離により算出されます。また左下の調整パネルから分割数とオフセットの変更ができます。

- エッジ選択状態でマウス左ボタンホールド＋ドラッグ
選択エッジとスライスされたエッジをブリッジします。また左下の調整パネルからオフセットの変更ができます。

### Fill Hole

エッジサーキットが選ばれた状態でホールドで穴をクアッドで埋めます。あまりいい結果にならないと思いますが取りあえずクアッドで塗りつぶしたいときにご利用ください。
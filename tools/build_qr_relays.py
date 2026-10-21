"""紙もののQR用の中継ページ q/<id>/index.html を台帳 tools/qr_targets.json から作る。

紙のQRを行き先（Instagram等）に直接向けると、読まれたかどうかが一切残らない。
中継ページを1枚挟み、解析（GA4 / Cloudflare Web Analytics）に記録してから行き先へ送る。
解析が未設定でも転送は動くので、先に紙を刷っておいて、数える仕組みは後から足せる。

使い方: python -X utf8 tools/build_qr_relays.py
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "tools" / "qr_targets.json"
OUT = ROOT / "q"
ID_RE = re.compile(r"^[a-z0-9-]{2,24}$")

PAGE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{label}へ移動しています｜館山サーフクラブ</title>
{analytics}<style>
  html,body{{height:100%;margin:0;background:#fff;color:#1F3A5F;font-family:"Noto Sans JP","Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif;}}
  .w{{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:24px;text-align:center;}}
  .t{{font-size:15px;font-weight:700;}}
  .s{{font-size:13px;color:#555;line-height:1.7;}}
  .a{{display:inline-block;background:#EF4B4B;color:#fff;text-decoration:none;font-weight:700;font-size:14px;padding:11px 22px;border-radius:999px;}}
  .sp{{width:26px;height:26px;border:3px solid #f6d0d0;border-top-color:#EF4B4B;border-radius:50%;animation:r .8s linear infinite;}}
  @keyframes r{{to{{transform:rotate(360deg)}}}}
</style>
</head>
<body>
<div class="w">
  <div class="sp"></div>
  <div class="t">{label}へ移動しています</div>
  <div class="s">自動で切り替わらないときは、下のボタンを押してください。</div>
  <a class="a" id="go" href="{to_attr}">{label}をひらく</a>
</div>
<script>
(function(){{
  var to = {to_js}, id = {id_js}, media = {media_js}, label = {label_js};
  var moved = false;
  function go(){{ if (moved) return; moved = true; location.replace(to); }}
  // 解析へ送ってから飛ぶ。遅くとも900msで移動する（ブロッカー等で足止めしない）
  var wait = {wait};
  if (typeof gtag === 'function') {{
    gtag('event', 'qr_scan', {{ qr_id: id, qr_media: media, qr_label: label, qr_to: to,
      event_callback: go, event_timeout: 900 }});
  }}
  setTimeout(go, wait);
  document.getElementById('go').addEventListener('click', function(){{ moved = true; }});
}})();
</script>
</body>
</html>
"""


def analytics_tags(cfg):
    tags = ""
    ga = cfg.get("ga4_id", "").strip()
    cf = cfg.get("cf_beacon_token", "").strip()
    if ga:
        if not re.fullmatch(r"G-[A-Z0-9]{4,16}", ga):
            raise SystemExit(f"ga4_id の形式が不正です: {ga}")
        tags += (f'<script async src="https://www.googletagmanager.com/gtag/js?id={ga}"></script>\n'
                 f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}"
                 f"gtag('js',new Date());gtag('config','{ga}');</script>\n")
    if cf:
        if not re.fullmatch(r"[0-9a-f]{32}", cf):
            raise SystemExit(f"cf_beacon_token の形式が不正です: {cf}")
        tags += (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
                 f'data-cf-beacon=\'{{"token": "{cf}"}}\'></script>\n')
    return tags, (900 if (ga or cf) else 200)


def main():
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    tags, wait = analytics_tags(data.get("analytics", {}))
    for qid, t in data["targets"].items():
        if not ID_RE.match(qid):
            raise SystemExit(f"id が不正です（英小文字・数字・ハイフンのみ）: {qid}")
        to = t["to"]
        if not to.startswith("https://"):
            raise SystemExit(f"行き先は https:// のみ: {qid} {to}")
        page = PAGE.format(
            label=html.escape(t["label"]), analytics=tags, to_attr=html.escape(to, quote=True),
            to_js=json.dumps(to), id_js=json.dumps(qid), media_js=json.dumps(t["media"], ensure_ascii=False),
            label_js=json.dumps(t["label"], ensure_ascii=False), wait=wait)
        d = OUT / qid
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page, encoding="utf-8")
        print(f"q/{qid}/ -> {to}")
    print("解析:", "あり" if tags else "なし（転送のみ）")


if __name__ == "__main__":
    main()

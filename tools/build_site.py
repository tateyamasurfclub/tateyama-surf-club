#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Googleスプレッドシート → サイト反映スクリプト（館山サーフクラブ）

事務局のメンバーはスプレッドシートを書き換えるだけでよく、
このスクリプトが該当箇所のHTMLを組み立て直します。

  python -X utf8 tools/build_site.py            # シートを取得して反映
  python -X utf8 tools/build_site.py --offline  # 取得せず手元のCSVだけで反映

シートIDは tools/sheet_config.json（または環境変数 SHEET_ID）で指定します。
取得したCSVは tools/data/ に保存され、Googleが落ちていても
最後に取得できた内容でサイトを再生成できます。
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
DATA = os.path.join(TOOLS, "data")
CONFIG_PATH = os.path.join(TOOLS, "sheet_config.json")

# 取得するシート。name=スプレッドシートのタブ名、file=保存先CSV
SHEETS = [
    {"key": "news", "name": "お知らせ", "file": "news.csv"},
    {"key": "annual", "name": "年間スケジュール", "file": "annual.csv"},
    {"key": "regular", "name": "定期活動", "file": "regular.csv"},
]

# 画像ファイル名として許可する形。CSSのurl()に差し込むため厳格に絞る
SAFE_IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.(jpg|jpeg|png|webp)$", re.I)

TRUTHY = {"はい", "○", "◯", "o", "yes", "true", "1", "★", "強調"}
DRAFT = {"下書き", "非公開", "draft", "no", "false", "0", "×", "x"}


# --------------------------------------------------------------------------
# 取得
# --------------------------------------------------------------------------
def load_config() -> dict:
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    env_id = os.environ.get("SHEET_ID", "").strip()
    if env_id:
        cfg["sheet_id"] = env_id
    return cfg


def sheet_url(sheet_id: str, tab_name: str) -> str:
    """「リンクを知っている全員が閲覧可」のシートをCSVで読み出すURL。APIキー不要。"""
    # headers=1 は必須。付けないとGoogle側が「何行目までが見出しか」を勝手に推測し、
    # 文字列だけの列が続くとデータ行まで見出しに巻き込んで1行に連結してしまう
    # （2026-08-25、お知らせが全消えする事故が起きた）。
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
        f"?tqx=out:csv&headers=1&sheet={urllib.parse.quote(tab_name)}"
    )


def fetch_sheets(sheet_id: str) -> list[str]:
    """シートを取得して tools/data/*.csv を更新する。更新できたキーを返す。"""
    updated = []
    for sheet in SHEETS:
        url = sheet_url(sheet_id, sheet["name"])
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "tsc-build/1.0"})
            with urllib.request.urlopen(req, timeout=30) as res:
                body = res.read().decode("utf-8")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"  [警告] 「{sheet['name']}」を取得できませんでした（{e}）。"
                  f"手元のCSVを使います。")
            continue

        if body.lstrip().startswith("<"):
            print(f"  [警告] 「{sheet['name']}」がCSVで返ってきませんでした。"
                  f"シートの共有設定（リンクを知っている全員が閲覧可）と"
                  f"タブ名をご確認ください。")
            continue

        rows = list(csv.reader(io.StringIO(body)))
        if not rows:
            print(f"  [警告] 「{sheet['name']}」が空でした。手元のCSVを使います。")
            continue

        os.makedirs(DATA, exist_ok=True)
        with open(os.path.join(DATA, sheet["file"]), "w", encoding="utf-8",
                  newline="") as f:
            csv.writer(f).writerows(rows)
        print(f"  取得: {sheet['name']}（{len(rows) - 1}行）")
        updated.append(sheet["key"])
    return updated


def read_rows(filename: str) -> list[dict]:
    """CSVを読み、1行目をヘッダーとして辞書のリストにする。空行は捨てる。"""
    path = os.path.join(DATA, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            header = [c.strip() for c in next(reader)]
        except StopIteration:
            return []
        out = []
        for raw in reader:
            if not any(c.strip() for c in raw):
                continue
            row = {}
            for i, col in enumerate(header):
                row[col] = raw[i].strip() if i < len(raw) else ""
            out.append(row)
        return out


# --------------------------------------------------------------------------
# 値の整形
# --------------------------------------------------------------------------
def get(row: dict, *names: str) -> str:
    """列名の表記ゆれを吸収して値を取り出す。"""
    for n in names:
        if n in row and row[n]:
            return row[n]
    return ""


def parse_date(value: str) -> tuple[str, str]:
    """日付を (表示用 '2026.04.12', 並べ替え用 '20260412') にする。"""
    v = value.strip()
    m = re.match(r"^(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})", v)
    if not m:
        return v, ""
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{y:04d}.{mo:02d}.{d:02d}", f"{y:04d}{mo:02d}{d:02d}"


def is_published(row: dict) -> bool:
    """「掲載」列が下書き系の値なら出さない。空欄は公開扱い。"""
    v = get(row, "掲載", "公開", "ステータス").strip().lower()
    return v not in DRAFT


def is_emphasized(row: dict) -> bool:
    return get(row, "強調", "ハイライト").strip().lower() in TRUTHY


def safe_image(value: str) -> str:
    """画像ファイル名を検証する。危険な値は「画像なし」として扱う。"""
    v = value.strip()
    if not v:
        return ""
    v = v.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if not SAFE_IMAGE.match(v):
        print(f"  [警告] 画像名「{value}」は使えないため画像なしで掲載します。"
              f"（半角英数字とハイフンのみ / .jpg .png .webp）")
        return ""
    return v


def esc(value: str) -> str:
    return html.escape(value, quote=True)


# --------------------------------------------------------------------------
# HTML生成
# --------------------------------------------------------------------------
def load_news() -> list[dict]:
    items = []
    for row in read_rows("news.csv"):
        title = get(row, "タイトル", "見出し", "件名")
        if not title or not is_published(row):
            continue
        shown, key = parse_date(get(row, "日付", "日時", "掲載日"))
        items.append({
            "date": shown,
            "sort": key,
            "tag": get(row, "部署", "カテゴリ", "タグ"),
            "title": title,
            "body": get(row, "本文", "内容", "概要"),
            "image": safe_image(get(row, "画像", "写真")),
        })
    items.sort(key=lambda x: x["sort"], reverse=True)
    return items


def render_news_cards(items: list[dict]) -> str:
    """news.html 用。写真つきカード（画像が無ければ文字だけのカード）。"""
    blocks = []
    for it in items:
        if it["image"]:
            img = (f'          <div class="news-card__img" '
                   f"style=\"background-image: url('images/news/{esc(it['image'])}');\">"
                   f"</div>\n")
            cls = "news-card"
        else:
            img = ""
            cls = "news-card news-card--noimg"
        body = (f'            <p class="news-card__excerpt">{esc(it["body"])}</p>\n'
                if it["body"] else "")
        tag = (f'              <span class="news-item__tag">{esc(it["tag"])}</span>\n'
               if it["tag"] else "")
        blocks.append(
            f'        <div class="{cls}" style="margin-bottom: 16px;">\n'
            f"{img}"
            f"          <div>\n"
            f'            <div class="news-card__meta">\n'
            f"{tag}"
            f'              <span class="news-card__date">{esc(it["date"])}</span>\n'
            f"            </div>\n"
            f'            <h3 class="news-card__title">{esc(it["title"])}</h3>\n'
            f"{body}"
            f"          </div>\n"
            f"        </div>"
        )
    return "\n\n".join(blocks)


def render_news_items(items: list[dict], limit: int = 5) -> str:
    """index.html 用。トップページの新着一覧（既定で上から5件）。"""
    blocks = []
    for it in items[:limit]:
        tag = (f'          <span class="news-item__tag">{esc(it["tag"])}</span>\n'
               if it["tag"] else "")
        blocks.append(
            f'        <div class="news-item">\n'
            f'          <span class="news-item__date">{esc(it["date"])}</span>\n'
            f"{tag}"
            f'          <span class="news-item__title">{esc(it["title"])}</span>\n'
            f"        </div>"
        )
    return "\n".join(blocks)


def render_annual() -> str:
    """schedule.html 年間スケジュール表。列は 月 / 主な活動・イベント の2つ。"""
    rows = []
    for row in read_rows("annual.csv"):
        month = get(row, "月")
        if not month:
            continue
        activity = get(row, "主な活動・イベント", "主な活動", "活動") or "-"
        if is_emphasized(row):
            rows.append(
                f'              <tr style="background: var(--primary-light);">\n'
                f'                <td><strong style="color: var(--primary);">'
                f"{esc(month)}</strong></td>\n"
                f"                <td><strong>{esc(activity)}</strong></td>\n"
                f"              </tr>"
            )
        else:
            rows.append(
                f"              <tr><td><strong>{esc(month)}</strong></td>"
                f"<td>{esc(activity)}</td></tr>"
            )
    return "\n".join(rows)


def render_regular() -> str:
    """schedule.html 定期活動表。列は 活動 / 頻度 / 時期 の3つ。"""
    rows = []
    for row in read_rows("regular.csv"):
        act = get(row, "活動", "活動名")
        if not act:
            continue
        rows.append(
            f"              <tr><td>{esc(act)}</td>"
            f'<td>{esc(get(row, "頻度"))}</td>'
            f'<td>{esc(get(row, "時期"))}</td></tr>'
        )
    return "\n".join(rows)


# --------------------------------------------------------------------------
# 差し込み
# --------------------------------------------------------------------------
def splice(path: str, start_marker: str, end_marker: str, content: str) -> bool:
    """2つの目印の間だけを差し替える。目印の外側のデザインには触れない。"""
    with open(path, encoding="utf-8", newline="") as f:
        original = f.read()

    si = original.find(start_marker)
    ei = original.find(end_marker)
    if si == -1 or ei == -1 or ei < si:
        print(f"  [エラー] {os.path.basename(path)} に目印が見つかりません。"
              f"（{start_marker.strip()}）")
        return False

    head = original[: si + len(start_marker)]
    tail = original[ei:]
    updated = f"{head}\n\n{content}\n\n        {tail}" if content else f"{head}\n\n        {tail}"

    if updated == original:
        print(f"  変更なし: {os.path.basename(path)}")
        return False

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(updated)
    print(f"  更新: {os.path.basename(path)}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="スプレッドシートの内容をサイトに反映します")
    ap.add_argument("--offline", action="store_true",
                    help="シートを取得せず、手元のCSVだけで反映する")
    args = ap.parse_args()

    cfg = load_config()
    sheet_id = (cfg.get("sheet_id") or "").strip()

    print("館山サーフクラブ サイト更新")
    print("-" * 46)

    if args.offline:
        print("手元のCSVだけで反映します（取得なし）")
    elif not sheet_id or sheet_id.startswith("ここに"):
        print("シートIDが未設定のため、手元のCSVだけで反映します。")
        print(f"  設定ファイル: {os.path.relpath(CONFIG_PATH, ROOT)}")
    else:
        print("スプレッドシートを取得中...")
        fetch_sheets(sheet_id)

    news = load_news()
    print(f"お知らせ {len(news)}件 を反映します")

    changed = False
    if news:
        changed |= splice(
            os.path.join(ROOT, "news.html"),
            "<!-- ===== 記事ここから（上に追加） ===== -->",
            "<!-- ===== 記事ここまで ===== -->",
            render_news_cards(news),
        )
        changed |= splice(
            os.path.join(ROOT, "index.html"),
            "<!-- ===== ニュースここから（上に追加） ===== -->",
            "<!-- ===== ニュースここまで ===== -->",
            render_news_items(news, int(cfg.get("top_page_news_count", 5))),
        )
    else:
        # 0件は「全部消す」ではなく「読めていない」と考える。取得失敗や列名の
        # 読み違いで、掲載中のお知らせを丸ごと消してしまう事故を防ぐ。
        print("  [警告] お知らせが0件でした。既存の掲載はそのまま残します。"
              "（シートのタブ名・列名・共有設定を確認してください）")
    changed |= splice(
        os.path.join(ROOT, "schedule.html"),
        "<!-- ===== 年間スケジュールここから ===== -->",
        "<!-- ===== 年間スケジュールここまで ===== -->",
        render_annual(),
    )
    changed |= splice(
        os.path.join(ROOT, "schedule.html"),
        "<!-- ===== 定期活動ここから ===== -->",
        "<!-- ===== 定期活動ここまで ===== -->",
        render_regular(),
    )

    print("-" * 46)
    print("サイトを更新しました" if changed else "内容に変更はありませんでした")
    return 0


if __name__ == "__main__":
    sys.exit(main())

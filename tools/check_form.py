#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
お問い合わせフォームの点検スクリプト

contact.html の入力欄と、送信先のGoogleフォームの質問が
食い違っていないかを確認する。食い違うと問い合わせが
「送ったのに届かない」状態になり、しかも送った人には分からない。

  python -X utf8 tools/check_form.py            # 点検のみ
  python -X utf8 tools/check_form.py --send-test # 実際にテスト送信もする

フォームの質問を増やしたり、選択肢の文言を変えたときは必ず実行する。
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTACT = os.path.join(ROOT, "contact.html")
UA = {"User-Agent": "Mozilla/5.0 (compatible; tsc-form-check/1.0)"}


def fetch(url: str, data: bytes | None = None) -> str:
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8", errors="replace")


def read_contact_html() -> tuple[str, dict, list]:
    """contact.html から 送信先URL・入力欄・種別の選択肢 を読み取る。"""
    src = open(CONTACT, encoding="utf-8").read()

    m = re.search(r'<form[^>]*id="contact-form"[^>]*action="([^"]+)"', src)
    if not m:
        m = re.search(r'action="(https://docs\.google\.com/forms/[^"]+)"', src)
    action = m.group(1) if m else ""

    fields = {}
    for tag in re.finditer(r'<(input|select|textarea)\b[^>]*>', src):
        t = tag.group(0)
        name = re.search(r'name="(entry\.\d+)"', t)
        if not name:
            continue
        label = re.search(r'id="([^"]+)"', t)
        fields[name.group(1)] = label.group(1) if label else "?"

    sel = re.search(r'<select[^>]*id="cf-category".*?</select>', src, re.S)
    choices = []
    if sel:
        for o in re.finditer(r'<option value="([^"]*)"', sel.group(0)):
            if o.group(1):
                choices.append(html_mod.unescape(o.group(1)))
    return action, fields, choices


def read_google_form(action: str):
    """Googleフォーム側の質問・entry ID・選択肢を読み取る。"""
    view = action.replace("/formResponse", "/viewform")
    page = fetch(view)
    m = re.search(r"FB_PUBLIC_LOAD_DATA_\s*=\s*(\[.*?\])\s*;\s*</script>", page, re.S)
    if not m:
        raise RuntimeError("Googleフォームの構造を読み取れません（公開設定を確認）")
    data = json.loads(m.group(1))
    title = data[3] if len(data) > 3 else ""
    out = {}
    choices = []
    for q in data[1][1]:
        qtitle = q[1]
        for f in (q[4] or []):
            key = f"entry.{f[0]}"
            required = bool(f[2])
            out[key] = {"title": qtitle, "required": required}
            if len(f) > 1 and f[1]:
                choices = [c[0] for c in f[1]]
    return title, out, choices


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send-test", action="store_true",
                    help="実際にテスト内容を送信して、受理されるか確かめる")
    args = ap.parse_args()

    action, fields, site_choices = read_contact_html()
    print("お問い合わせフォーム点検")
    print("=" * 60)
    if not action:
        print("✗ contact.html に送信先が見つかりません")
        return 1
    print(f"送信先: {action}")

    title, gfields, g_choices = read_google_form(action)
    print(f"フォーム名: {title}")
    print("-" * 60)

    ng = []

    # 入力欄の対応
    for entry, label in fields.items():
        g = gfields.get(entry)
        if not g:
            print(f"✗ {label}: {entry} がGoogleフォームに存在しません")
            ng.append(f"{label} の送信先が消えている")
        else:
            print(f"✓ {label:12s} → {entry}  「{g['title']}」"
                  f"{' [必須]' if g['required'] else ''}")

    # サイト側が任意なのにGoogle側が必須、を検出（送っても弾かれる）
    for entry, g in gfields.items():
        if entry not in fields:
            print(f"✗ Googleフォームの「{g['title']}」に対応する入力欄がサイトにありません"
                  f"{'（しかも必須）' if g['required'] else ''}")
            if g["required"]:
                ng.append(f"「{g['title']}」が必須だが送信されない＝全件拒否される")

    src = open(CONTACT, encoding="utf-8").read()
    for entry, g in gfields.items():
        if not g["required"]:
            continue
        m = re.search(r'<[^>]*name="' + re.escape(entry) + r'"[^>]*>', src)
        if m and "required" not in m.group(0):
            print(f"✗ 「{g['title']}」はGoogle側が必須だが、サイト側が任意になっています")
            ng.append(f"「{g['title']}」未入力の問い合わせが黙って消える")

    # 選択肢の一致
    print("-" * 60)
    if g_choices:
        only_site = [c for c in site_choices if c not in g_choices]
        only_g = [c for c in g_choices if c not in site_choices]
        if only_site:
            print("✗ サイトにしかない選択肢（送信すると拒否されます）:")
            for c in only_site:
                print(f"    「{c}」")
            ng.append("選択肢の文言が食い違っている")
        if only_g:
            print("△ Googleフォームにしかない選択肢（実害はありません）:")
            for c in only_g:
                print(f"    「{c}」")
        if not only_site:
            print(f"✓ 種別の選択肢 {len(site_choices)}件すべて一致")

    if args.send_test and not ng:
        print("-" * 60)
        print("テスト送信中…")
        payload = {}
        for entry in fields:
            g = gfields.get(entry, {})
            t = g.get("title", "")
            if "メール" in t:
                payload[entry] = "test@example.com"
            elif "種別" in t and site_choices:
                payload[entry] = site_choices[-1]
            elif "電話" in t:
                payload[entry] = "000-0000-0000"
            elif "名前" in t:
                payload[entry] = "【テスト送信】動作確認"
            else:
                payload[entry] = "これは動作確認のテスト送信です。確認後に削除してください。"
        body = urllib.parse.urlencode(payload, encoding="utf-8").encode()
        # 受理＝HTTP 200 かつ確認文言がある、の両方。片方だけでは判定しない
        # （拒否されるとHTTP 400 で戻り、確認文言は出ない）
        try:
            req = urllib.request.Request(action, data=body, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                code = r.status
                res = r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            code = e.code
            res = e.read().decode("utf-8", errors="replace")

        ok = code == 200 and ("回答を記録しました" in res
                              or "Your response has been recorded" in res)
        if ok:
            print(f"✓ Googleフォームが受理しました（HTTP {code}）")
        else:
            print(f"✗ 受理されませんでした（HTTP {code}）")
            ng.append("テスト送信が受理されなかった")

    print("=" * 60)
    if ng:
        print("要修正:")
        for x in ng:
            print("  -", x)
        return 1
    print("問題ありません")
    return 0


if __name__ == "__main__":
    sys.exit(main())

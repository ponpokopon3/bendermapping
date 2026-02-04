import re
from pathlib import Path
from typing import Dict, Tuple, Optional, List
import urllib.parse

import streamlit as st
import streamlit.components.v1 as components

# --- デフォルトのマスター定義 ---------------------------------
DEFAULT_MASTER_LIST = [
    "戦略・企画",
    "営業",
    "プロジェクトマネジメント",
    "コンサルティング",
    "エンジニア",
    "ソリューションサービス",
    "運用",
    "セキュリティ教育",
    "脆弱性診断",
    "フォレンジック対応",
    "バックオフィス業務",
]

DEFAULT_RELATION_MASTER = ["強化", "維持", "縮小", "終了"]


# ---- ユーティリティ -------------------------------------------------
def list_md_files(data_dir: Path) -> List[Path]:
    """指定ディレクトリ内の .md ファイルをソートして返す"""
    return sorted([p for p in data_dir.glob("*.md") if p.is_file()])


def load_text(path: Path) -> str:
    """UTF-8でファイルを読み込む"""
    return path.read_text(encoding="utf-8")


def parse_content(text: str) -> Tuple[Optional[str], Dict[str, str]]:
    """Markdown を解析し、パートナー名と '##' セクションを抽出して返す"""
    partner_name: Optional[str] = None
    m = re.search(r"(?m)^#\s*パートナー名\s*$", text)
    if m:
        rest = text[m.end():]
        for line in rest.splitlines():
            if line.strip():
                partner_name = line.strip()
                break

    sections: Dict[str, str] = {}
    matches = list(re.finditer(r"(?m)^##\s*(.+)\s*$", text))
    for idx, mm in enumerate(matches):
        title = mm.group(1).strip()
        start = mm.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()

    return partner_name, sections


def is_markdown_table(text: str) -> bool:
    """簡易判定: テキスト内にマークダウン表のヘッダ+区切り行があるかを返す"""
    return bool(re.search(r"(?m)^\s*\|.*\n\s*\|[-: \t|]+\n", text))


def md_table_to_records(text: str):
    """マークダウン表を辞書レコードのリストに変換する。変換できない場合は None を返す"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # ヘッダ行と区切り行を探す
    header_idx = None
    for i in range(len(lines) - 1):
        if '|' in lines[i] and re.match(r"^\s*\|?\s*[-: ]+\s*(\|\s*[-: ]+\s*)+\|?$", lines[i + 1]):
            header_idx = i
            break
    if header_idx is None:
        return None

    def split_row(r: str):
        r = r.strip()
        if r.startswith('|'):
            r = r[1:]
        if r.endswith('|'):
            r = r[:-1]
        return [c.strip() for c in r.split('|')]

    headers = split_row(lines[header_idx])
    data_lines = lines[header_idx + 2 :]
    records = []
    for dl in data_lines:
        if '|' not in dl:
            continue
        cols = split_row(dl)
        if len(cols) < len(headers):
            cols += [''] * (len(headers) - len(cols))
        records.append(dict(zip(headers, cols)))
    return records


# ----------------- ヘルパー関数 (トップレベル、初心者向けに分離) -----------------
def load_master_list(data_dir: Path) -> List[str]:
    """data フォルダ内の `domain-master.txt` を読み込み、存在しなければデフォルトを返す。

    引数:
      data_dir: `Path` オブジェクト (通常は `Path(__file__).parent / "data"`)
    戻り値:
      マスター名のリスト
    """
    master_path = data_dir / "domain-master.txt"
    if master_path.exists():
        lines = [ln.strip() for ln in master_path.read_text(encoding="utf-8").splitlines()]
        return [ln for ln in lines if ln]
    return DEFAULT_MASTER_LIST


def load_relation_master(data_dir: Path) -> List[str]:
    """`relation-master.txt` を読み込み、存在しなければデフォルトの関係性リストを返す。"""
    p = data_dir / "relation-master.txt"
    if p.exists():
        lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()]
        return [ln for ln in lines if ln]
    return DEFAULT_RELATION_MASTER


def extract_items(text: str) -> List[str]:
    """連係領域テキストをパースして項目リストを返すシンプルロジック。

    対象のテキストは箇条書き (`*`/`-`)、カンマ区切り、あるいは単一行を想定します。
    """
    if not text:
        return []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    items: List[str] = []
    for ln in lines:
        if ln.startswith("*") or ln.startswith("-"):
            items.append(ln.lstrip("*- ").strip())
        else:
            if "," in ln:
                items.extend([p.strip() for p in ln.split(",") if p.strip()])
            else:
                items.append(ln)
    return items


def is_mermaid(txt: str) -> bool:
    """Mermaid ソースっぽいかを簡易判定する。"""
    if not txt:
        return False
    if "```mermaid" in txt:
        return True
    first = txt.strip().splitlines()[0] if txt.strip().splitlines() else ""
    keywords = ("graph", "sequenceDiagram", "flowchart", "classDiagram", "stateDiagram")
    return any(first.startswith(k) for k in keywords)


def extract_mermaid_source(txt: str) -> str:
    """```mermaid``` ブロックがあれば中身を返す。なければ元テキストを返す。"""
    if "```mermaid" in txt:
        parts = txt.split("```mermaid")
        if len(parts) > 1:
            body = parts[1]
            if "```" in body:
                body = body.split("```")[0]
            return body.strip()
    return txt.strip()


def render_mermaid_html(mermaid_src: str, height: int = 400) -> None:
    """Mermaid CDN を使って HTML 埋め込みでレンダリングする（`components.html`）。"""
    safe_src = mermaid_src
    html = f"""
<div class="mermaid">{safe_src}</div>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad:true}});</script>
"""
    components.html(html, height=height)


def render_value(value: str, compact: bool = False) -> None:
    """値の描画: テーブル/リスト/文書/Mermaid を自動判定して適切に出力する。

    compact=True にすると見出しを大きくせず簡素に出力する（`製品サービス` 用）。
    """
    # Mermaid の優先判定
    if is_mermaid(value):
        src = extract_mermaid_source(value)
        try:
            render_mermaid_html(src, height=400)
            return
        except Exception:
            st.code(src)
            return

    if not value:
        if compact:
            st.write("-")
        else:
            st.subheader("-")
        return

    if is_markdown_table(value):
        records = md_table_to_records(value)
        if records:
            try:
                import pandas as pd

                df = pd.DataFrame(records)
                st.dataframe(df)
                return
            except Exception:
                st.table(records)
                return

    lines = [ln for ln in value.splitlines() if ln.strip()]
    if lines and all(ln.strip().startswith("*") or ln.strip().startswith("-") for ln in lines):
        items = [ln.lstrip("*- ").strip() for ln in lines]
        if compact:
            st.write("、".join(items))
        else:
            st.subheader("、".join(items))
        return

    first = lines[0] if lines else value
    rest = "\n".join(lines[1:])
    if compact:
        st.write(first)
        if rest:
            st.write(rest)
    else:
        st.subheader(first)
        if rest:
            st.write(rest)


def render_label_and_value(label: str, value: str) -> None:
    """ラベルを小さく表示して値を描画するラッパー。"""
    st.caption(label)
    render_value(value)


def render_master_grid(master_list: List[str], highlighted: set, cols_per_row: int = 4) -> None:
    """マスターリストをグリッド表示し、`highlighted` の要素を強調する。

    - master_list: 表示するマスター項目の順序リスト
    - highlighted: 強調表示する項目集合
    - cols_per_row: 1行あたりの列数
    """
    for i in range(0, len(master_list), cols_per_row):
        row = master_list[i : i + cols_per_row]
        cols = st.columns(len(row))
        for c, it in zip(cols, row):
            with c:
                if it in highlighted:
                    st.info(it)
                else:
                    st.code(it)
    extras = [it for it in highlighted if it not in master_list]
    if extras:
        st.write("その他: " + "、".join(extras))


def render_kv_row(label: str, value: str, master_list: List[str], renkei_items: set, compact_labels: Optional[set] = None) -> None:
    """ラベルを上に、値を下に表示する汎用ユーティリティ。

    `連係領域` の場合はマスター表示を行う。
    """
    st.caption(label)
    if label in ("連係領域", "今後の関係性"):
        render_master_grid(master_list, renkei_items, cols_per_row=4)
        return

    compact = False
    if compact_labels and label in compact_labels:
        compact = True
    render_value(value, compact=compact)


def show_mapping_page(data_dir: Path, files: List[Path], master_list: List[str]) -> None:
    """ドメイン（master_list）の枠を作り、各枠内に "パートナー名(リレーションレベル)" を配置する表示ページ。

    シンプル実装: 3列グリッドで master を並べ、各ボックス内は `st.info` を使って枠表示します。
    """
    st.title("ドメイン別マッピング")
    # すべてのファイルを走査して、パートナーとそのリレーション情報を収集
    mapping: Dict[str, List[Tuple[str, str]]] = {m: [] for m in master_list}
    others: List[str] = []
    for p in files:
        try:
            txt = load_text(p)
        except Exception:
            continue
        pname, secs = parse_content(txt)
        name = pname or "(名前不明)"
        rlevel = secs.get("リレーションレベル", "-")
        renkei_txt = secs.get("連係領域", "")
        items = extract_items(renkei_txt)
        label = f"{name}({rlevel})"
        matched = False
        for it in items:
            if it in master_list:
                mapping[it].append((label, p.name))
                matched = True
        if not matched:
            others.append((label, p.name))

    # 表示: 3列グリッドで master_list を表示
    cols_per_row = 3
    for i in range(0, len(master_list), cols_per_row):
        chunk = master_list[i : i + cols_per_row]
        cols = st.columns(len(chunk))
        for c, m in zip(cols, chunk):
            with c:
                content = mapping.get(m, [])
                if content:
                    md_lines = []
                    for label, fname in content:
                        q = urllib.parse.quote(fname, safe='')
                        md_lines.append(f"- [{label}](?mode=詳細&file={q})")
                    md = "\n".join(md_lines)
                    st.info(f"**{m}**\n\n" + md)
                else:
                    st.info(f"**{m}**\n\n(なし)")

    # その他は下部に表示
    if others:
        st.markdown("---")
        st.subheader("その他（マスターにない領域）")
        for label, fname in others:
            q = urllib.parse.quote(fname, safe='')
            st.write(f"- [{label}](?mode=詳細&file={q})")


# -------------------------------------------------------------------------


# ---- 表示ロジック（ダッシュボード風） -------------------------------
def main() -> None:
    st.set_page_config(page_title="パートナーダッシュボード", layout="wide")

    data_dir = Path(__file__).parent / "data"
    if not data_dir.exists():
        st.error(f"data ディレクトリが見つかりません: {data_dir}")
        return
    files = list_md_files(data_dir)
    # クエリパラメータを読んで直接マッピング／詳細表示に遷移できるようにする
    qp = st.query_params
    qp_mode = qp.get("mode", [None])[0]
    qp_file = qp.get("file", [None])[0]

    master_list_for_sidebar = load_master_list(data_dir)
    # クエリでマッピング指定なら直接表示
    if qp_mode == "マッピング":
        show_mapping_page(data_dir, files, master_list_for_sidebar)
        return
    # クエリで詳細指定ならそのファイルを開いて表示
    if qp_mode == "詳細" and qp_file:
        # URL デコード
        fname = urllib.parse.unquote(qp_file)
        if fname in [p.name for p in files]:
            selected_path = data_dir / fname
            try:
                text = load_text(selected_path)
            except Exception as e:
                st.error(f"ファイル読み込みエラー: {e}")
                return
            partner_name, sections = parse_content(text)
            # 続けて通常の詳細レンダリングに進むため、ファイルは選択済みとして処理する
        else:
            st.error("指定されたファイルが見つかりません。")
            return
    else:
        # サイドバー: 表示モード選択とファイル一覧
        mode = st.sidebar.radio("表示モード", ["詳細", "マッピング"], index=0, key="mode_radio")
        if mode == "マッピング":
            show_mapping_page(data_dir, files, master_list_for_sidebar)
            return
        st.sidebar.title("ファイル一覧")
        if not files:
            st.sidebar.info("data フォルダに .md ファイルがありません")
            return
        choice = st.sidebar.radio("表示するファイルを選択", [p.name for p in files], key="file_radio")
        selected_path = data_dir / choice
        try:
            text = load_text(selected_path)
        except Exception as e:
            st.error(f"ファイル読み込みエラー: {e}")
            return
        partner_name, sections = parse_content(text)

    # 必要なフィールドを取り出す
    relation_level = sections.get("リレーションレベル", "")
    renkei_iki = sections.get("連係領域", "")
    renkei_mokuteki = sections.get("連係目的", "")
    renkei_saki = sections.get("連携先", "")
    url = sections.get("URL", "")
    kankeisha = sections.get("関係者との接点", "")

    # マスターリストと選択項目を用意（トップレベルのヘルパーを利用）
    master_list = load_master_list(data_dir)
    relation_master = load_relation_master(data_dir)
    renkei_items = set(extract_items(renkei_iki))
    compact_labels = {"製品サービス", "連係目的"}

    # ---- メイン領域: トップのメトリクス行（連係領域を縦結合） ----
    # 左列にパートナー名とリレーションレベルを縦積み、右列を連係領域で縦に跨ぐ
    left_col, right_col = st.columns([3, 3], gap="large")
    with left_col:
        render_label_and_value("パートナー名", partner_name or "(パートナー名なし)")
        render_label_and_value("リレーションレベル", relation_level or "-")
    with right_col:
        render_kv_row("連係領域", renkei_iki, master_list, renkei_items, compact_labels)

    # その下に連係目的を全幅で表示
    st.markdown("---")
    render_kv_row("連係目的", renkei_mokuteki, master_list, renkei_items, compact_labels)

    st.markdown("---")
    # ---- 下部左右分割: 左=関係者との接点、右=詳細セクション ----
    left_col, right_col = st.columns([1, 3], gap="large")
    with left_col:
        render_label_and_value("関係者との接点", kankeisha)

    with right_col:
        # 右側に並べるセクション順
        right_order = ["製品サービス", "直近の実績", "パートナー評価", "今後の関係性"]
        for key in right_order:
            value = sections.get(key, "")
            if key == "今後の関係性":
                rel_items = set(extract_items(value))
                render_kv_row(key, value, relation_master, rel_items, compact_labels)
            else:
                render_kv_row(key, value, master_list, renkei_items, compact_labels)


if __name__ == "__main__":
    main()


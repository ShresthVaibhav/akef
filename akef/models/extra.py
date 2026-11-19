from __future__ import annotations

import html
import re

from pydantic import Field

from akef.models.base import Model, Timestamp


class Notice(Model):
    id: str = Field("", alias="cid")
    tab: str = ""
    title: str = ""
    header: str = ""
    start_at: Timestamp = None
    data: dict = {}

    @property
    def headline(self) -> str:
        return self.header or " ".join(self.title.replace("\\n", "\n").split())

    @property
    def html(self) -> str:
        return self.data.get("html") or ""

    @property
    def image(self) -> str:
        if self.data.get("url"):
            return self.data["url"]
        found = re.search(r'<img[^>]+src="([^"]+)"', self.html)
        return found.group(1) if found else ""

    @property
    def text(self) -> str:
        body = re.sub(r"<br\s*/?>|</p>|</li>", "\n", self.html)
        body = html.unescape(re.sub(r"<[^>]+>", "", body))
        return re.sub(r"\n{3,}", "\n\n", body).strip()


class Owned(Model):
    id: str
    name: str = ""
    count: int = 1


class Inventory(Model):
    operators: list[Owned] = []
    weapons: list[Owned] = []
    gear: list[Owned] = []
    tacticals: list[Owned] = []


class WikiItem(Model):
    id: str = Field("", alias="itemId")
    name: str = ""
    brief: dict = {}
    document: dict | None = None

    @property
    def cover(self) -> str:
        return self.brief.get("cover") or ""

    @property
    def illustration(self) -> str:
        return ((self.document or {}).get("extraInfo") or {}).get("illustration") or self.cover

    @property
    def description(self) -> str:
        return _blocks(self.brief.get("description"))

    def text(self, doc_id: str) -> str:
        return _blocks(((self.document or {}).get("documentMap") or {}).get(doc_id))

    def content(self, doc_id: str) -> list[WikiBlock]:
        document = ((self.document or {}).get("documentMap") or {}).get(doc_id)
        if not document:
            return []
        blocks = document.get("blockMap") or {}
        return [b for block_id in document.get("blockIds") or [] for b in _content(blocks, block_id)]

    @property
    def info(self) -> list[tuple[str, str]]:
        out = []
        for widget in ((self.document or {}).get("widgetCommonMap") or {}).values():
            out += [(row.get("label", ""), row.get("value", "")) for row in widget.get("tableList") or []]
        return out

    @property
    def sections(self) -> list[WikiSection]:
        doc = self.document or {}
        widgets = doc.get("widgetCommonMap") or {}
        out = []
        for chapter in doc.get("chapterGroup") or []:
            for ref in chapter.get("widgets") or []:
                widget = widgets.get(ref.get("id")) or {}
                icons = {tab.get("tabId"): tab.get("icon", "") for tab in widget.get("tabList") or []}
                entries = []
                for tab_id, tab in (widget.get("tabDataMap") or {}).items():
                    intro = tab.get("intro") or {}
                    entries.append(WikiEntry(
                        name=intro.get("name", ""),
                        kind=intro.get("type", ""),
                        icon=icons.get(tab_id, ""),
                        text=self.text(intro.get("description", "")) or self.text(tab.get("content", "")),
                        content=self.content(tab.get("content", "")),
                    ))
                out.append(WikiSection(chapter=chapter.get("title", ""), title=ref.get("title", "").lstrip("/"),
                                       entries=entries))
        return out

    @property
    def game_id(self) -> str:
        return ((self.brief.get("associate") or {}).get("id")) or ""


class WikiLink(Model):
    id: str
    count: int = 0


class WikiCell(Model):
    text: str = ""
    links: list[WikiLink] = []
    images: list[str] = []


class WikiBlock(Model):
    kind: str
    text: str = ""
    bold: bool = False
    image: str = ""
    rows: list[list[WikiCell]] = []


class WikiEntry(Model):
    name: str = ""
    kind: str = ""
    icon: str = ""
    text: str = ""
    content: list[WikiBlock] = []


class WikiSection(Model):
    chapter: str = ""
    title: str = ""
    entries: list[WikiEntry] = []


def _blocks(document) -> str:
    if not document:
        return ""
    blocks = document.get("blockMap") or {}
    lines = []

    def walk(block_id):
        block = blocks.get(block_id) or {}
        runs = (block.get("text") or {}).get("inlineElements") or []
        line = "".join((r.get("text") or {}).get("text", "") for r in runs).strip()
        if line:
            lines.append(line)
        for child in block.get("childIds") or []:
            walk(child)

    for block_id in document.get("blockIds") or []:
        walk(block_id)
    return "\n".join(lines)


def _cell(blocks, ids) -> WikiCell:
    texts, links, images = [], [], []
    stack = list(ids)
    while stack:
        block = blocks.get(stack.pop(0)) or {}
        if block.get("kind") == "image":
            images.append((block.get("image") or {}).get("url", ""))
        line = ""
        for run in (block.get("text") or {}).get("inlineElements") or []:
            if run.get("kind") == "entry":
                entry = run.get("entry") or {}
                links.append(WikiLink(id=str(entry.get("id", "")), count=int(entry.get("count") or 0)))
            else:
                line += (run.get("text") or {}).get("text", "")
        if line.strip():
            texts.append(line.strip())
        stack = list(block.get("childIds") or []) + list(((block.get(block.get("kind") or "") or {}).get("childIds")) or []) + stack
    return WikiCell(text="\n".join(texts), links=links, images=[i for i in images if i])


def _content(blocks, block_id) -> list[WikiBlock]:
    block = blocks.get(block_id) or {}
    kind = block.get("kind")
    if kind == "text":
        runs = (block.get("text") or {}).get("inlineElements") or []
        text = "".join((r.get("text") or {}).get("text", "") for r in runs).strip()
        return [WikiBlock(kind="text", text=text, bold=all(r.get("bold") for r in runs))] if text else []
    if kind == "image":
        return [WikiBlock(kind="image", image=(block.get("image") or {}).get("url", ""))]
    if kind == "table":
        table = block.get("table") or {}
        cells = table.get("cellMap") or {}
        rows = []
        for row in table.get("rowIds") or []:
            rows.append([_cell(blocks, (cells.get(f"{row}_{col}") or {}).get("childIds") or []) for col in table.get("columnIds") or []])
        return [WikiBlock(kind="table", rows=rows)]
    children = list(block.get("childIds") or []) + list(((block.get(kind or "") or {}).get("childIds")) or [])
    return [b for child in children for b in _content(blocks, child)]

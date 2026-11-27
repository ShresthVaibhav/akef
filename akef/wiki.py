from dataclasses import dataclass, field
from enum import Enum

# spaces, separators and zero-width spaces the wiki leaves in otherwise empty cells
BLANK = " ·​"


@dataclass
class WikiSkill:
    name: str
    kind: str
    icon: str
    text: str


@dataclass
class Cost:
    name: str
    icon: str
    count: int


@dataclass
class Tier:
    name: str
    effect: str
    requirement: str
    costs: list[Cost] = field(default_factory=list)


@dataclass
class Node:
    name: str
    kind: str
    icon: str
    tiers: list[Tier] = field(default_factory=list)


@dataclass
class Potential:
    name: str
    icon: str
    text: str


@dataclass
class Intel:
    label: str
    title: str
    text: str


@dataclass
class Story:
    title: str
    unlock: str
    text: str


class WikiPart(str, Enum):
    OVERVIEW = "overview"
    SKILLS = "skills"
    TALENTS = "talents"
    GROWTH = "growth"
    PROFILE = "profile"
    LORE = "lore"

    @property
    def needs_index(self) -> bool:
        return self in (WikiPart.TALENTS, WikiPart.GROWTH, WikiPart.PROFILE)


@dataclass
class WikiPage:
    name: str
    art: str
    quote: str
    bio: str
    info: list[tuple[str, str]] = field(default_factory=list)
    skills: list[WikiSkill] = field(default_factory=list)
    talents: list[Node] = field(default_factory=list)
    promotions: list[Node] = field(default_factory=list)
    potentials: list[Potential] = field(default_factory=list)
    weapons: list[tuple[str, list[Cost]]] = field(default_factory=list)
    intel: list[Intel] = field(default_factory=list)
    stories: list[Story] = field(default_factory=list)

    @property
    def parts(self) -> list[WikiPart]:
        has = {
            WikiPart.TALENTS: self.talents,
            WikiPart.GROWTH: self.promotions or self.potentials,
            WikiPart.LORE: self.stories,
        }
        return [part for part in WikiPart if has.get(part, True)]

    def urls(self) -> list[str]:
        out = [self.art] + [s.icon for s in self.skills] + [p.icon for p in self.potentials]
        for node in self.talents + self.promotions:
            out.append(node.icon)
            out += [c.icon for tier in node.tiers for c in tier.costs]
        out += [c.icon for _, costs in self.weapons for c in costs]
        return [u for u in out if u]


def _costs(cell, index) -> list[Cost]:
    out = []
    for link in cell.links:
        target = index.get(link.id)
        if target is not None:
            out.append(Cost(target.name, target.cover, link.count))
    return out


def _tables(entry):
    return [block for block in entry.content if block.kind == "table"]


def _node(entry, index) -> Node:
    titles = [block.text for block in entry.content if block.kind == "text"]
    tiers = []
    for table in _tables(entry):
        for row in table.rows:
            # header rows start with an empty cell, explanation rows have no cost column
            if len(row) < 3 or not row[0].text or (not row[-1].links and row[-1].text == "Cost"):
                continue
            middle = [text for text in (cell.text.strip(BLANK) for cell in row[2:-1]) if text]
            tiers.append(Tier(row[0].text, row[1].text, " · ".join(middle), _costs(row[-1], index)))
    return Node(titles[0] if titles else "", titles[1] if len(titles) > 1 else "", entry.icon, tiers)


def wiki_page(item, index: dict | None = None) -> WikiPage:
    index = index or {}
    lines = [line for line in item.description.splitlines() if line.strip()]
    quote = lines[0].strip('"“” ') if lines and lines[0].startswith(('"', "“")) else ""
    page = WikiPage(
        name=item.name,
        art=item.illustration,
        quote=quote,
        bio=" ".join(lines[1:] if quote else lines),
        info=[(k, v) for k, v in item.info if k and v and "CV" not in k and v != item.name],
    )
    kinds = set()
    for section in item.sections:
        if section.title == "Combat Skills":
            for entry in section.entries:
                if entry.kind not in kinds:
                    kinds.add(entry.kind)
                    page.skills.append(WikiSkill(entry.name.split(" (")[0], entry.kind, entry.icon, entry.text))
        elif section.title == "Talent Nodes":
            page.talents = [_node(entry, index) for entry in section.entries]
        elif section.title == "Elite":
            page.promotions = [_node(entry, index) for entry in section.entries]
        elif section.title == "Potential Phases":
            for entry in section.entries:
                for table in _tables(entry):
                    for row in table.rows:
                        if len(row) >= 3 and "POTENTIAL" in row[1].text:
                            name = row[1].text.split("\n")[0]
                            icon = row[0].images[0] if row[0].images else ""
                            page.potentials.append(Potential(name, icon, row[2].text))
        elif section.title == "Game Recommendation":
            for entry in section.entries:
                for table in _tables(entry):
                    if len(table.rows) >= 2:
                        for head, cell in zip(table.rows[0], table.rows[1]):
                            page.weapons.append((head.text, _costs(cell, index)))
        elif section.title == "Profile":
            for entry in section.entries:
                texts = [b for b in entry.content if b.kind == "text"]
                if len(texts) < 2:
                    continue
                unlock = texts[1].text if texts[1].bold and texts[1].text.startswith("Reach") else ""
                body = texts[2:] if unlock else texts[1:]
                page.stories.append(Story(texts[0].text.title(), unlock, "\n".join(b.text for b in body)))
        elif section.title == "Operator Intel":
            for entry in section.entries:
                texts = [b for b in entry.content if b.kind == "text"]
                i = 0
                while i < len(texts):
                    label = texts[i].text
                    if i + 1 < len(texts) and texts[i + 1].bold:
                        body = texts[i + 2].text if i + 2 < len(texts) else ""
                        page.intel.append(Intel(label.split(":")[0], texts[i + 1].text, body))
                        i += 3
                    elif i + 1 < len(texts):
                        page.intel.append(Intel(label, texts[i + 1].text, ""))
                        i += 2
                    else:
                        i += 1
    return page

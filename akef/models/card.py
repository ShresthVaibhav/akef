import re
from datetime import datetime, timezone

from pydantic import Field

from akef.models.base import Model, Progress, Tag, Timestamp


def tier_unlocked(node: str, latest: list[str]) -> bool:
    # passive/base lines only report their highest tier, everything below it is unlocked too
    line, _, tier = node.rpartition("_")
    for top_node in latest:
        head, _, top = top_node.rpartition("_")
        if head == line and tier.isdigit() and top.isdigit() and int(tier) <= int(top):
            return True
    return False


class Skill(Model):
    id: str
    name: str = ""
    type: Tag = Field(default_factory=Tag)
    element: Tag = Field(default_factory=Tag, alias="property")
    icon_url: str = ""
    desc: str = ""
    desc_params: dict[str, str] = {}


class Talent(Model):
    id: str
    name: str = ""
    icon_url: str = ""
    locked_icon_url: str = ""
    desc: str = ""
    desc_params: dict[str, str] = {}


class CharacterData(Model):
    id: str
    name: str = ""
    avatar_sq_url: str = ""
    avatar_rt_url: str = ""
    illustration_url: str = ""
    rarity: Tag = Field(default_factory=Tag)
    profession: Tag = Field(default_factory=Tag)
    element: Tag = Field(default_factory=Tag, alias="property")
    weapon_type: Tag = Field(default_factory=Tag)
    skills: list[Skill] = []
    tags: list[str] = []
    ability_talents: list[Talent] = []
    combat_talents: list[Talent] = []
    cultivation_talents: list[Talent] = []


class SkillLevel(Model):
    skill_id: str
    level: int = 0
    max_level: int = 0
    skill_form_type: str = ""


class Suit(Model):
    id: str
    name: str = ""
    skill_id: str = ""
    skill_desc: str = ""
    skill_desc_params: dict[str, str] = {}


class EquipData(Model):
    id: str
    name: str = ""
    icon_url: str = ""
    rarity: Tag = Field(default_factory=Tag)
    type: Tag = Field(default_factory=Tag)
    level: Tag = Field(default_factory=Tag)
    properties: list[str] = []
    is_accessory: bool = False
    suit: Suit | None = None
    function: str = ""
    pkg: str = ""
    base_attr_value: int = 0


class Equip(Model):
    equip_id: str
    equip_data: EquipData
    enhance: dict[str, int] = {}
    can_enhance: bool = False

    @property
    def name(self) -> str:
        return self.equip_data.name


class TacticalItemData(Model):
    id: str
    name: str = ""
    icon_url: str = ""
    rarity: Tag = Field(default_factory=Tag)
    active_effect_type: Tag = Field(default_factory=Tag)
    active_effect: str = ""
    passive_effect: str = ""
    active_effect_params: dict[str, str] = {}
    passive_effect_params: dict[str, str] = {}


class TacticalItem(Model):
    tactical_item_id: str
    tactical_item_data: TacticalItemData

    @property
    def name(self) -> str:
        return self.tactical_item_data.name


class WeaponSkillInfo(Model):
    skill: Tag = Field(default_factory=Tag)
    max_level: int = 0
    gem_tag_id: str = ""


class WeaponData(Model):
    id: str
    name: str = ""
    icon_url: str = ""
    rarity: Tag = Field(default_factory=Tag)
    type: Tag = Field(default_factory=Tag)
    function: str = ""
    description: str = ""
    skills: list[Tag] = []
    skill_infos: list[WeaponSkillInfo] = []


class WeaponSkill(Model):
    key: str
    name: str = ""
    level: int = 0
    current_max_level: int = 0
    current_base_level: int = 0
    gem_term_id: str = ""


class GemData(Model):
    term_id: str = ""
    name: str = ""
    icon: str = ""
    template_id: str = ""


class GemTerm(Model):
    id: str
    name: str = ""
    cost: int = 0


class Gem(Model):
    id: str
    icon: str = ""
    gem_data: GemData | None = None
    terms: list[GemTerm] = []

    @property
    def name(self) -> str:
        return self.gem_data.name if self.gem_data else ""


class Weapon(Model):
    weapon_data: WeaponData
    level: int = 0
    refine_level: int = 0
    breakthrough_level: int = 0
    gem: Gem | None = None
    skills: list[WeaponSkill] = []
    wiki_item_id: str = ""

    @property
    def name(self) -> str:
        return self.weapon_data.name

    @property
    def rarity(self) -> int:
        return int(self.weapon_data.rarity.value or 0)


class TalentNodes(Model):
    latest_break_node: str = ""
    attr_nodes: list[str] = []
    latest_passive_skill_nodes: list[str] = []
    latest_factory_skill_nodes: list[str] = []
    latest_spaceship_skill_nodes: list[str] = []


class Character(Model):
    id: str
    char_data: CharacterData
    level: int = 0
    evolve_phase: int = 0
    potential_level: int = 0
    user_skills: dict[str, SkillLevel] = {}
    body_equip: Equip | None = None
    arm_equip: Equip | None = None
    first_accessory: Equip | None = None
    second_accessory: Equip | None = None
    tactical_item: TacticalItem | None = None
    weapon: Weapon | None = None
    talent: TalentNodes | None = None
    gender: str = ""
    own_ts: Timestamp = None
    wiki_item_id: str = ""

    @property
    def name(self) -> str:
        return self.char_data.name

    @property
    def rarity(self) -> int:
        return int(self.char_data.rarity.value or 0)

    @property
    def element(self) -> str:
        return self.char_data.element.value

    @property
    def profession(self) -> str:
        return self.char_data.profession.value

    @property
    def equips(self) -> list[Equip]:
        slots = (self.body_equip, self.arm_equip, self.first_accessory, self.second_accessory)
        return [e for e in slots if e is not None]

    def skill_level(self, skill_id: str) -> int:
        found = self.user_skills.get(skill_id)
        return found.level if found else 0

    @property
    def talents(self) -> list[Talent]:
        d = self.char_data
        return [
            *sorted(d.ability_talents, key=lambda t: t.id),
            *sorted(d.combat_talents, key=lambda t: t.id),
            *sorted(d.cultivation_talents, key=lambda t: t.id),
        ]

    def talent_unlocked(self, talent_id: str) -> bool:
        nodes = self.talent
        if nodes is None:
            return False
        if talent_id in nodes.attr_nodes:
            return True
        latest = nodes.latest_passive_skill_nodes + nodes.latest_spaceship_skill_nodes + nodes.latest_factory_skill_nodes
        return tier_unlocked(talent_id, latest)

    @property
    def unlocked_talents(self) -> list[Talent]:
        return [t for t in self.talents if self.talent_unlocked(t.id)]


class Mission(Model):
    id: str = ""
    description: str = ""


class Base(Model):
    uid: str = Field(alias="roleId")
    name: str = ""
    server_name: str = ""
    level: int = 0
    world_level: int = 0
    exp: int = 0
    gender: int = 0
    avatar_url: str = ""
    main_mission: Mission = Field(default_factory=Mission)
    char_num: int = 0
    weapon_num: int = 0
    doc_num: int = 0
    create_time: Timestamp = None
    save_time: Timestamp = None
    last_login_time: Timestamp = None

    @property
    def awakening_days(self) -> int:
        if self.create_time is None:
            return 0
        return (datetime.now(timezone.utc) - self.create_time).days + 1


class Stamina(Model):
    current: int = Field(0, alias="curStamina")
    max: int = Field(0, alias="maxStamina")
    full_at: Timestamp = Field(None, alias="maxTs")

    @property
    def is_full(self) -> bool:
        return self.current >= self.max

    @property
    def seconds_left(self) -> int:
        if self.full_at is None or self.is_full:
            return 0
        return max(0, int((self.full_at - datetime.now(timezone.utc)).total_seconds()))


class BattlePass(Model):
    cur_level: int = 0
    max_level: int = 0


class DailyMission(Model):
    current: int = Field(0, alias="dailyActivation")
    max: int = Field(0, alias="maxDailyActivation")


class WeeklyMission(Model):
    score: int = 0
    total: int = 0


class Credit(Model):
    count: int = 0
    total: int = 0
    has_today: bool = False
    next_refresh_ts: Timestamp = None


class AchievementData(Model):
    id: str
    name: str = ""
    init_icon: str = ""
    plated_icon: str = ""
    cate: str = ""
    cate_name: str = ""
    init_level: int = 0


class Medal(Model):
    achievement_data: AchievementData
    level: int = 0
    is_plated: bool = False
    obtain_ts: Timestamp = None

    @property
    def name(self) -> str:
        return self.achievement_data.name.strip('"')

    @property
    def icon(self) -> str:
        data = self.achievement_data
        return data.plated_icon if self.is_plated and data.plated_icon else data.init_icon


class Achievements(Model):
    count: int = 0
    medals: list[Medal] = Field([], alias="achieveMedals")
    display: dict[str, str] = {}

    @property
    def showcased(self) -> list[Medal]:
        by_id = {m.achievement_data.id: m for m in self.medals}
        return [by_id[i] for _, i in sorted(self.display.items(), key=lambda kv: int(kv[0])) if i in by_id]


class RoomChar(Model):
    char_id: str
    physical_strength: float = 0
    favorability: int = 0
    avatar_url: str = ""


class Room(Model):
    id: str = ""
    type: int = 0
    level: int = 0
    chars: list[RoomChar] = []


class SpaceShip(Model):
    rooms: list[Room] = []


class Settlement(Model):
    id: str
    name: str = ""
    level: int = 0
    exp: int = 0
    exp_to_level_up: int = 0
    remain_money: int = 0
    money_max: int = 0
    officer_char_ids: str = ""
    officer_char_avatar: str = ""
    is_final_max_level: bool = False
    last_tick_time: Timestamp = None


class Area(Model):
    level_id: str
    name: str = ""
    puzzle_count: Progress = Field(default_factory=Progress)
    trchest_count: Progress = Field(default_factory=Progress)
    equip_trchest_count: Progress = Field(default_factory=Progress)
    piece_count: Progress = Field(default_factory=Progress)
    blackbox_count: Progress = Field(default_factory=Progress)
    trstar_count: Progress = Field(default_factory=Progress)


class Domain(Model):
    domain_id: str
    name: str = ""
    level: int = 0
    settlements: list[Settlement] = []
    money: Progress = Field(default_factory=Progress, alias="moneyMgr")
    areas: list[Area] = Field([], alias="levels")


class CrisisContract(Model):
    id: str
    name: str = ""
    highest: int = 0
    challenge_count: int = 0
    achieve: Medal | None = None
    weekly_mission: Progress = Field(default_factory=Progress)
    indicator_mission: Progress = Field(default_factory=Progress)
    stage_mission: Progress = Field(default_factory=Progress)
    kv_image: str = ""
    header_image: str = ""
    start_at_ts: Timestamp = None
    end_at_ts: Timestamp = None
    gameplay_end_at_ts: Timestamp = None


class EchoStage(Model):
    name: str = ""
    star: int = 0
    plus_task: bool = False


class EchoWeek(Model):
    id: str
    name: str = ""
    stars: int = 0
    all_plus_tasks: bool = False
    start_ts: Timestamp = None
    end_ts: Timestamp = None
    dungeon_groups: list[EchoStage] = []


class EchoSeason(Model):
    id: str
    name: str = ""
    stars: int = 0
    all_plus_tasks: bool = False
    kv_image: str = ""
    header_image: str = ""
    start_ts: Timestamp = None
    end_ts: Timestamp = None
    weeks: list[EchoWeek] = []


class WarEchoes(Model):
    seasons: list[EchoSeason] = []


class Enemy(Model):
    id: str
    name: str = ""
    desc: str = ""
    level: int = 0
    image_url: str = ""
    ability: str = ""


class RecordChar(Model):
    char_id: str
    level: int = 0
    evolve_phase: int = 0
    potential_level: int = 0
    avatar_url: str = ""
    element: Tag = Field(default_factory=Tag, alias="property")
    rarity: Tag = Field(default_factory=Tag)


class BestRecord(Model):
    chars: list[RecordChar] = []
    cleared_at: Timestamp = Field(None, alias="ts")
    # despite the name this is how long the clear took, in seconds
    seconds: int = Field(0, alias="passTs")


class Dungeon(Model):
    id: str
    name: str = ""
    is_pass: bool = False
    desc: str = ""
    feature: str = ""
    recommend_level: int = 0
    enemies: list[Enemy] = []
    best_record: BestRecord | None = None

    @property
    def rules(self) -> list[str]:
        text = re.sub(r"<@[^>]*>|</>", "", self.feature)
        return [line.strip(" -") for line in text.splitlines() if line.strip(" -")]


class DungeonPair(Model):
    normal_dungeon: Dungeon | None = None
    hard_dungeon: Dungeon | None = None


class IndieHardGroup(Model):
    id: str
    name: str = ""
    pic: str = ""
    dungeon_groups: list[DungeonPair] = []
    activity_name: str = ""
    is_in_activity: bool = False
    activity_start_ts: Timestamp = None
    activity_end_ts: Timestamp = None
    achieve: Medal | None = None

    @property
    def cleared(self) -> tuple[int, int]:
        normal = sum(1 for p in self.dungeon_groups if p.normal_dungeon and p.normal_dungeon.is_pass)
        hard = sum(1 for p in self.dungeon_groups if p.hard_dungeon and p.hard_dungeon.is_pass)
        return normal, hard


class IndieHard(Model):
    groups: list[IndieHardGroup] = Field([], alias="indieHardGroups")


class QuickAccess(Model):
    name: str = ""
    icon: str = ""
    link: str = ""


class CardConfig(Model):
    char_ids: list[str] = []


class Card(Model):
    base: Base
    chars: list[Character] = []
    achieve: Achievements = Field(default_factory=Achievements)
    space_ship: SpaceShip = Field(default_factory=SpaceShip)
    domain: list[Domain] = []
    stamina: Stamina = Field(default_factory=Stamina, alias="dungeon")
    battle_pass: BattlePass = Field(default_factory=BattlePass, alias="bpSystem")
    daily: DailyMission = Field(default_factory=DailyMission, alias="dailyMission")
    weekly: WeeklyMission = Field(default_factory=WeeklyMission, alias="weeklyMission")
    credit: Credit = Field(default_factory=Credit)
    crisis_contract: list[CrisisContract] = []
    war_echoes: WarEchoes = Field(default_factory=WarEchoes)
    indie_hard: IndieHard = Field(default_factory=IndieHard)
    config: CardConfig = Field(default_factory=CardConfig)
    seek_suspicion: Progress = Field(default_factory=Progress)
    quickaccess: list[QuickAccess] = []
    current_ts: Timestamp = None

    @property
    def uid(self) -> str:
        return self.base.uid

    def sanity_at(self, value: int) -> datetime | None:
        # recovery speed comes from how long the rest takes, so no regen rate is hard coded
        s = self.stamina
        if value <= s.current:
            return self.current_ts or datetime.now(timezone.utc)
        if value > s.max or s.full_at is None or self.current_ts is None:
            return None
        per_point = (s.full_at - self.current_ts) / (s.max - s.current)
        return self.current_ts + per_point * (value - s.current)

    @property
    def showcased(self) -> list[Character]:
        by_id = {c.id: c for c in self.chars}
        return [by_id[i] for i in self.config.char_ids if i in by_id]

    @property
    def name(self) -> str:
        return self.base.name

    def character(self, name_or_id: str) -> Character | None:
        wanted = name_or_id.lower()
        return next((c for c in self.chars if c.id == name_or_id or c.name.lower() == wanted), None)


PARAM = re.compile(r"\{(?:@[^@}]*@)?(-?)(\w+):(0(?:\.0+)?)(%?)\}")
TAG = re.compile(r"</?(?:color[^>]*|[@#][^>]*)?>")


def fill(desc: str, params: dict[str, str]) -> str:
    # game text keeps numbers as {name:0%} with the values sent apart, and colours as <color=...> tags
    def value(m):
        raw = params.get(m.group(2))
        if raw is None:
            return m.group(0)
        number = float(raw) * (-1 if m.group(1) else 1) * (100 if m.group(4) else 1)
        places = len(m.group(3)) - 2 if "." in m.group(3) else 0
        return f"{number:.{places}f}{m.group(4)}"
    return TAG.sub("", PARAM.sub(value, desc or "")).strip()


class ContractChar(Model):
    char_id: str
    level: int = 0
    potential_level: int = 0
    avatar_url: str = ""


class ContractRun(Model):
    id: str = ""
    chars: list[ContractChar] = []
    played_at: Timestamp = Field(None, alias="ts")
    seconds: int = Field(0, alias="passTs")
    cleared: bool = Field(False, alias="isPass")
    score: int = Field(0, alias="indicatorCount")
    waves: int = Field(0, alias="passWave")
    is_best: bool = False


class ContractHistory(Model):
    records: list[ContractRun] = []
    best_record: ContractRun | None = None


class Indicator(Model):
    id: str
    icon: str = ""
    name: str = ""
    desc: str = ""
    desc_params: dict[str, str] = {}
    has_award: bool = False
    type: int = 0
    depends: list[str] = []
    score: int = 0
    is_unlock: bool = False

    @property
    def text(self) -> str:
        return fill(self.desc, self.desc_params)


class ContractStage(Model):
    id: str = ""
    name: str = ""
    desc: str = ""
    enemies: list[Enemy] = []
    recommend_level: int = 0


class ContractDetail(Model):
    status: CrisisContract
    history: ContractHistory = Field(default_factory=ContractHistory)
    indicators: list[Indicator] = []
    stage: ContractStage = Field(default_factory=ContractStage, alias="dungeon")

    @property
    def best(self) -> ContractRun | None:
        return self.history.best_record or next((r for r in self.history.records if r.is_best), None)

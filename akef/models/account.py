from __future__ import annotations

from pydantic import ConfigDict, Field

from akef.models.base import Model, Timestamp


class AgeGate(Model):
    region_code: str = ""


class Account(Model):
    model_config = ConfigDict(extra="ignore")

    hg_id: str
    email: str = ""
    nick_name: str = ""
    age_gate: AgeGate = Field(default_factory=AgeGate)

    @property
    def region(self) -> str:
        return self.age_gate.region_code


class Role(Model):
    uid: str = Field(alias="roleId")
    server_id: str
    nickname: str = ""
    level: int = 0
    is_default: bool = False
    is_banned: bool = False
    server_type: str = ""
    server_name: str = ""

    @property
    def game_role(self) -> str:
        return f"3_{self.uid}_{self.server_id}"


class Pendant(Model):
    id: int = 0
    icon_url: str = ""
    title: str = ""
    description: str = ""


class BasicUser(Model):
    id: str
    nickname: str = ""
    profile: str = ""
    avatar: str = ""
    gender: int = 0
    created_at: Timestamp = None
    latest_login_at: Timestamp = None


class UserInfo(Model):
    basic_user: BasicUser
    pendant: Pendant | None = None


class Social(Model):
    follow: int = 0
    fans: int = 0
    liked: int = 0


class Profile(Model):
    user: UserInfo
    user_rts: Social = Field(default_factory=Social)

    @property
    def id(self) -> str:
        return self.user.basic_user.id

    @property
    def nickname(self) -> str:
        return self.user.basic_user.nickname

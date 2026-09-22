"""Shared data model for a 591 賣屋 listing."""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Listing:
    """One property to be posted to 591 賣屋 (sale) listings.

    `extra` holds any additional fields you need that aren't modeled
    explicitly — house591_poster.py can read from it via FIELD_MAP.
    """

    title: str
    city: str
    district: str
    address: str
    house_type: str  # 電梯大樓 / 公寓 / 透天厝 / 華廈 / 套房 / 店面 ...
    total_price_wan: float  # 總價(萬元)
    main_building_ping: float  # 主建物坪數
    total_ping: float  # 權狀總坪數
    rooms: int
    living_rooms: int
    bathrooms: int
    floor: int
    total_floors: int
    age_years: float
    parking: str  # 有/無，或車位類型描述
    facing: str  # 座向
    description: str
    contact_name: str
    contact_phone: str
    photos: list[str] = field(default_factory=list)  # local file paths
    land_ping: float | None = None
    extra: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Return a list of problems (empty list = OK to submit)."""
        problems = []
        if not self.title:
            problems.append("缺少標題 title")
        if not self.address:
            problems.append("缺少地址 address")
        if self.total_price_wan <= 0:
            problems.append("總價必須大於 0")
        if self.main_building_ping <= 0:
            problems.append("主建物坪數必須大於 0")
        for p in self.photos:
            if not Path(p).is_file():
                problems.append(f"照片檔案不存在: {p}")
        if not self.contact_phone:
            problems.append("缺少聯絡電話 contact_phone")
        return problems

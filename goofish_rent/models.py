from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class Listing:
    item_id: str
    title: str
    price: str
    area: str
    url: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> "Listing":
        return cls(
            item_id=payload["item_id"],
            title=payload["title"],
            price=payload["price"],
            area=payload["area"],
            url=payload["url"],
        )

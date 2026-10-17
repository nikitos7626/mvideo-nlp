from typing import Protocol, TypedDict

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired


class Prediction(TypedDict):
	attribute: str
	value: str
	confidence: float
	source: str
	raw: NotRequired[str]

class BaseExtractor(Protocol):
	name: str
	version: str
	def health(self) -> bool: ...
	def extract(self, card: dict) -> list[Prediction]: ...
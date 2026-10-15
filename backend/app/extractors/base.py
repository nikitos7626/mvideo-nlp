from typing import NotRequired, Protocol, TypedDict


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
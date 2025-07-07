from dataclasses import dataclass

from dataclasses_jsonschema import JsonSchemaMixin


@dataclass
class Point(JsonSchemaMixin):
    "A 2D point"
    x: float
    y: float

print(Point.json_schema())
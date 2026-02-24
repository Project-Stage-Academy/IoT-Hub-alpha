import json
from pathlib import Path
from typing import Any
from dateutil import parser
from datetime import timezone
from django.utils import timezone as tz
from .data_structure import ExternalEventMessage
from pydantic import ValidationError
from functools import lru_cache


class TransformationError(Exception):
    pass


class TransformEngine:
    def __init__(self):
        pass

    def transform(self, inbound_id: int, body: dict[str, Any]) -> ExternalEventMessage:
        """
        Transform entry point
        """
        self.mappings = self._get_map_or_die(inbound_id)
        self.body = body
        result = {}

        try:
            result = self._init_transform(self.mappings, result, self.body)
            validate_final = ExternalEventMessage.model_validate(result)
        except ValidationError as e:
            raise TransformationError(f"Validation error: {e}") from e
        except (KeyError, ValueError, AttributeError) as e:
            raise TransformationError(f"Parsing error: {e}") from e
        except RecursionError as e:
            raise TransformationError(f"Recursion error: {e}") from e

        return validate_final

    def _init_transform(
        self, mapping: dict, result: dict, body: dict
    ) -> dict[str, Any]:
        """
        Main transform parser, responsible for logic.
        returns a dict for ExternalEventMessage model validate or raises
        an TransformationError
        """
        if not isinstance(mapping, dict):
            raise TransformationError("rules.mappings must be an object")
        for target_key, spec in mapping.items():
            if not isinstance(spec, dict):
                raise TransformationError(f"{target_key} spec must be an object")

            if "list" in spec:
                data_list = body[spec["from"]]
                new_list = []
                self._check_list(spec, data_list, target_key)
                for elem in data_list:
                    transformed = self._init_transform(spec["list"], {}, elem)
                    new_list.append(transformed)
                result[target_key] = new_list
                continue

            if "inner_dict" in spec:
                inner_source = self._get_inner_dict(spec, body, target_key)
                child = {}
                result[target_key] = child
                self._init_transform(spec["inner_dict"], child, inner_source)
                continue

            if "from" in spec:
                value = body.get(spec["from"])
                if "literal" in spec:
                    value = self._handle_literal(spec, value, target_key)
                if value is None and "default" in spec:
                    value = spec["default"]
                if value is None and "default" not in spec:
                    continue
                if "cast" in spec:
                    value = self._cast_value(value, spec["cast"])
                result[target_key] = value
                continue

            if "default" in spec:
                value = spec["default"]
                if "cast" in spec:
                    value = self._cast_value(value, spec["cast"])
                result[target_key] = value
                continue

        return result

    def _check_list(self, spec, data_list, target_key):
        if not isinstance(spec["list"], dict):
            raise TransformationError("spec.list must be an object")
        if not isinstance(data_list, list):
            raise TransformationError(
                f"{target_key}: expected list at '{spec['from']}'"
            )

    def _get_inner_dict(self, spec, body, target_key):
        inner_source = body
        if "from" in spec:
            inner_source = body.get(spec["from"])
        if inner_source is None:
            inner_source = spec.get("default", {})
        if not isinstance(inner_source, dict):
            raise TransformationError(f"{target_key}: inner source must be a dict")
        return inner_source

    def _handle_literal(self, spec, value, target_key):
        literal = [x.lower() if type(x) is str else x for x in spec["literal"]]
        value = value.lower() if type(value) is str else value
        if value is None:
            value = spec["default"]
        if value not in literal:
            raise TransformationError(
                f"{target_key} got ({value}) can only accept {literal}"
            )
        return value

    def _cast_value(self, value: Any, cast: str) -> Any:
        """
        Method for type casting
        """
        match cast:
            case "str":
                return str(value)
            case "int":
                return int(value)
            case "float":
                return float(value)
            case "bool":
                if isinstance(value, str):
                    if value.lower() in ["yes", "true", "1", "ok"]:
                        return True
                    else:
                        return False
                else:
                    return bool(value)
            case "timezone":
                return self._convert_time(value)
            
            case _:
                raise TransformationError(f"{value} case value {cast} not found")

    def _convert_time(self, value: str | None = None) -> str:
        try:
            value = str(value)
            dt = parser.parse(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

        except (
            TypeError,
            ValueError,
            OverflowError,
            AttributeError,
            parser.ParserError,
        ):
            return tz.now().isoformat()

        return dt.astimezone(timezone.utc).isoformat()

    @lru_cache(maxsize=1)
    def _get_map_or_die(self, id: int) -> dict[str, Any]:
        """
        Get transformation map from json or raise TransformationError
        """
        path = Path(__file__).parent / "inbound_map.json"
        with path.open("r") as f:
            raw_transform_rules = json.load(f)

        for rule in raw_transform_rules:
            if rule.get("id") == id:
                return rule.get("map")

        raise TransformationError(f"{id} ID not found")

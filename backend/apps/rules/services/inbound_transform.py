import json
from typing import Any
from pathlib import Path
from dateutil import parser
from datetime import timezone
from django.utils import timezone as tz
from .data_structure import ExternalEventMessage
from pydantic import ValidationError

class TransformationError(Exception):
    pass

class TransformEngine:
    def __init__(self):
        self.result = {}
    
    def transform(self, id, body):
        self.mappings = self._get_map_or_die(id)
        self.body = body
        
        try:
            result = self._init_transfrom(self.mappings, self.result, self.body)   
            validate_final = ExternalEventMessage.model_validate(result)
        except ValidationError as e:
            raise TransformationError(f"Validation error: {e}")
        except (KeyError, ValueError, AttributeError) as e:
            raise TransformationError(f"Parsing error: {e}")
        except RecursionError as e:
            raise TransformationError(f"Recursion error: {e}")
        
        return validate_final.model_dump()
    
    def _init_transfrom(self, mapping: dict, result: dict, body: dict):
        if not isinstance(mapping, dict):
            raise TransformationError("rules.mappings must be an object")
        for target_key, spec in mapping.items():
            if not isinstance(spec, dict):
                raise TransformationError(f"{target_key} spec must be an object")

            if "list" in spec:
                data_list = self.body[spec.get('from')]
                new_list = []
                if not isinstance(spec.get('list'), dict):
                    raise TransformationError("spec.list must be an object")
                if not isinstance(data_list, list):
                    raise TransformationError(f"{target_key}: expected list at '{spec['from']}'")
                for elem in data_list:
                    transformed = self._init_transfrom(spec.get('list'), {}, elem)
                    new_list.append(transformed)
                result[target_key] = new_list
                continue
                
            if "inner_dict" in spec:
                inner_source = body
                if "from" in spec:
                    inner_source = body.get(spec["from"])
                    if inner_source is None:
                        inner_source = spec.get("default", {})
                    if not isinstance(inner_source, dict):
                        raise TransformationError(f"{target_key}: inner source must be a dict")

                child = {}
                result[target_key] = child
                self._init_transfrom(spec["inner_dict"], child, inner_source)
                continue

            if "from" in spec:
                value = body.get(spec["from"])
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
        
    
    def _cast_value(self, value, cast):
        match cast:
            case "str":
                return str(value)
            case "int":
                return int(value)
            case "float":
                return float(value)
            case "bool":
                if isinstance(value, str):
                    if value.lower() in ['yes', 'true', '1', 'ok']:
                        return True
                    else:
                        return False
                else:
                    return bool(value)
            case "timezone":
                return self._convert_time(value)
    
    def _convert_time(self, value = None):
        try:
            dt = parser.parse(value)
        except Exception:
            return tz.now().isoformat()

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    
    def _get_map_or_die(self, id):
        
        path = Path(__file__).parent / "inbound_map.json"
        with path.open("r") as f:
            raw_transform_rules = json.load(f)
            
        for rule in raw_transform_rules:
            if rule.get('id') == id:
                return rule.get('map')
            
        raise TransformationError(f"{id} ID not found")
import json
from typing import Any
from pathlib import Path
from dateutil import parser
from datetime import timezone
from django.utils import timezone as tz

class TransformationError(Exception):
    pass

class TransformEngine:
    def __init__(self):
        self.result = {}
    
    def transform(self, id, body):
        self.mappings = self._get_map_or_die(id)
        self.body = body
        
        data = self._init_transfrom(self.mappings, self.result, self.body)
        
        return self.result
    
    def _init_transfrom(self, mapping, result, body):
        if not isinstance(mapping, dict):
            raise TransformationError("rules.mappings must be an object")
        
        try:
            
            for target_key, spec in mapping.items():
                
                if "from" in spec:
                    value = self.body.get(spec.get("from"))
                    if value is None and "default" in spec:
                        value = spec.get('default')
                    if "cast" in spec:
                        value = self._cast_value(value, spec['cast'])
                        
                    result[target_key] = value
                    
                elif "from" not in spec and "default" in spec:
                    default = spec.get('default')
                    result[target_key] = default
                    
                elif "inner_dict" in spec:
                    result[target_key] = {}
                    self._init_transfrom(spec['inner'], result[target_key], self.body)
                
                    
                
                    
        except(KeyError, ValueError) as e:
            raise TransformationError(e)
        
        return result   
        
    
    def _cast_value(self, value, cast):
        match cast:
            case "str":
                return str(value)
            case "int":
                return int(value)
            case "float":
                return bool(value)
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
            # assume UTC if naive
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
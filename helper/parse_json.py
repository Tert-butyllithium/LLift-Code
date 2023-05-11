import json
import regex


def parse_json(json_str):
    pattern = regex.compile('\{(?:[^{}]|(?R))*\}')
    json_res = pattern.findall(json_str)
    
    if len(json_res) == 0:
        return None

    json_objs = []
    for json_str in json_res:
        try:
            json_objs.append(json.loads(json_str))
        except json.JSONDecodeError:
            pass
    
    if len(json_objs) == 0:
        return None
    
    return json_objs[0]

import json
import regex


def parse_json(json_str):
    pattern = regex.compile('\{(?:[^{}]|(?R))*\}')
    json_res = pattern.findall(json_str)
    
    if len(json_res) == 0:
        return None

    json_objs = []
    for json_str in json_res:
        json_str = json_str.replace('”','"')
        try:
            json_objs.append(json.loads(json_str))
        except json.JSONDecodeError:
            t_res = workaround_illegal_json(json_str)
            if t_res is not None:
                json_objs.append(t_res)
    
    if len(json_objs) == 0:
        return None
    
    return json_objs[-1]


def workaround_illegal_json(json_str:str):
    json_str = json_str.replace(',\n}','\n}')

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None
import rich.pretty
import json
import os

def dumpy(obj, depth=4, key=None):
    if key in ("author", "channel", "guild", "members"):
        depth = min(depth, 1) # 100k lines to less than 1k

    if depth <= 0:
        return str(obj)

    if isinstance(obj, list):
        return [dumpy(v, depth - 1) for v in obj]

    if isinstance(obj, dict):
        return {str(k): dumpy(v, depth - 1) for k, v in obj.items()}

    if hasattr(obj, "__dict__"):
        return {
            "__type__": type(obj).__name__,
            **{k: dumpy(v, depth - 1) for k, v in vars(obj).items()}
        }

    if hasattr(obj, "__slots__"):
        result = {}

        for attr in dir(obj):
            if attr.startswith("_"):
                continue
            try:
                value = getattr(obj, attr)
                if not callable(value):
                    result[attr] = dumpy(value, depth - 1, key=attr)
            except:
                continue
        return result

    if hasattr(obj, "to_dict"):
        return dumpy(obj.to_dict(), depth - 1)

    try:
        json.dumps(obj)
        return obj
    except:
        return str(obj)

def savey(obj, depth=4, filename="dump.json"):
    data = dumpy(obj, depth)

    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except:
                existing = []
    else:
        existing = []

    existing.append(data)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=4, ensure_ascii=False)

def printy(obj, depth=4):
    rich.pretty.pprint(dumpy(obj, depth))
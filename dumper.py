import json
import os
import rich.pretty

def dump(obj, depth, key=None, seen=None):
    if seen is None:
        seen = set()

    if id(obj) in seen:
        return f"<Circular Ref: {type(obj).__name__}>"

    if depth <= 0:
        return str(obj)

    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj

    if hasattr(obj, "to_dict"):
        return dump(obj.to_dict(), depth - 1, seen=seen)

    if isinstance(obj, list):
        return [dump(v, depth - 1, seen=seen) for v in obj]

    if isinstance(obj, dict):
        return {str(k): dump(v, depth - 1, key=str(k), seen=seen) for k, v in obj.items()}

    has_dict = hasattr(obj, "__dict__")
    has_slots = hasattr(obj, "__slots__")

    if has_dict or has_slots:
        seen.add(id(obj))
        result = {"__type__": type(obj).__name__}

        if has_dict:
            for k, v in vars(obj).items():
                result[k] = dump(v, depth - 1, key=k, seen=seen)

        if has_slots:
            for attr in dir(obj):
                if attr.startswith("_") or attr in result:
                    continue
                try:
                    v = getattr(obj, attr)
                    if not callable(v):
                        result[attr] = dump(v, depth - 1, key=attr, seen=seen)
                except:
                    continue

        seen.remove(id(obj))
        return result

    try:
        json.dumps(obj)
        return obj
    except:
        return str(obj)

def save(obj, depth=4, filename="dump.json"):
    data = dump(obj, depth)
    existing = []

    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
                if not isinstance(existing, list):
                    existing = [existing]
            except Exception:
                existing = []

    existing.append(data)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=4, ensure_ascii=False)

def print(obj, depth=4):
    rich.pretty.pprint(dump(obj, depth))
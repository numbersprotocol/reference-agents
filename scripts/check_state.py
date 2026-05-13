import json, os, glob

for f in sorted(glob.glob("state/*.json")):
    agent = os.path.basename(f).replace(".json", "")
    try:
        with open(f) as fh:
            d = json.load(fh)
        if isinstance(d, dict):
            for key in ["seen_ids", "seen", "registered"]:
                if key in d and isinstance(d[key], (list, set)):
                    print(f"{agent}: {len(d[key])} seen IDs (key={key})")
                    break
            else:
                print(f"{agent}: keys={list(d.keys())[:5]}, top-level items={len(d)}")
        elif isinstance(d, list):
            print(f"{agent}: {len(d)} entries (list)")
    except Exception as e:
        print(f"{agent}: error reading — {e}")

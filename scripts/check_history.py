"""Check asset history and asset tree for the provenance commit."""
import json
import sys
from common import get_capture

NID = "bafkreidhiozj27eobyyfwunrphn5wytqabqnft6gyundg2hxq2pz76pypy"

capture = get_capture()

print("── Commit history ───────────────────────────────────────────────────")
try:
    history = capture.get_history(NID)
    for i, commit in enumerate(history):
        print(f"  [{i}] action={commit.action}  ts={commit.timestamp}")
        print(f"       tx_hash={commit.tx_hash}")
        print(f"       asset_tree_cid={commit.asset_tree_cid}")
except Exception as e:
    print(f"  get_history failed: {e}")

print("\n── Asset tree (merged) ──────────────────────────────────────────────")
try:
    tree = capture.get_asset_tree(NID)
    print(f"  caption={tree.caption}")
    print(f"  mime_type={tree.mime_type}")
    print(f"  extra fields: {json.dumps(tree.extra, indent=2)}")
except Exception as e:
    print(f"  get_asset_tree failed: {e}")

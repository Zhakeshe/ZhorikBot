from datetime import datetime
from typing import Dict

from .db import append_log


def build_log(moderator_id: int, target_id: int, old_status: str, new_status: str, proof: str, comment: str) -> Dict[str, object]:
    return {
        "time": datetime.utcnow().isoformat(),
        "moderator_id": moderator_id,
        "target_id": target_id,
        "old_status": old_status,
        "new_status": new_status,
        "proof": proof,
        "comment": comment,
    }


def save_log(entry: Dict[str, object]) -> None:
    append_log(entry)

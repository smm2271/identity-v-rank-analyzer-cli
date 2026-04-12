import uuid
from datetime import datetime
from typing import Dict, Any

class AbstractReplayParser:
    def parse(self, raw_data: Any) -> Dict[str, Any]:
        raise NotImplementedError

class IdentityVReplayParser(AbstractReplayParser):
    @staticmethod
    def _as_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_cipher_progress(value: Any) -> Dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        # 後端 schema 要求 object，若來源是陣列則包成 object
        return {"generator_status": value}

    @staticmethod
    def _normalize_room_guuid(value: Any) -> str | None:
        if value is None:
            return None

        raw = str(value).strip()
        if not raw:
            return None

        # 已是合法 UUID：直接回傳標準格式
        try:
            return str(uuid.UUID(raw))
        except (ValueError, TypeError, AttributeError):
            pass

        # 非 UUID（例如 24 位十六進位）時，轉成可重現 UUID
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"idv-room:{raw}"))

    @staticmethod
    def _normalize_game_save_time(value: Any) -> str | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            return value.isoformat(timespec="seconds")

        raw = str(value).strip()
        if not raw:
            return None

        formats = (
            "%Y_%m_%d_%H_%M_%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        )

        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt).isoformat(timespec="seconds")
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat(timespec="seconds")
        except ValueError:
            return None

    def parse(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        self_res = raw_data.get("self_result", {})
        spec_info = self_res.get("spec_info", {})
        all_players = raw_data.get("all_player_result", [])
        base_info = self_res.get("base_info", {})
        us_warm_info = base_info.get("us_warm_info", {})

        parsed_players = []
        for player in all_players:
            player_id = self._as_int(player.get("unique_id"))
            character_id = self._as_int(player.get("pid"))
            if player_id is None or character_id is None:
                continue

            parsed_players.append(
                {
                    "player_id": player_id,
                    "player_name": player.get("player_name"),
                    "character_id": character_id,
                    "res_type": self._as_int(player.get("res_type")),
                }
            )

        ladder_score_info = []
        self_pid = self._as_int(base_info.get("pid"))
        ladder_score = self._as_int(us_warm_info.get("character_ladder_score"))
        if self_pid is not None and ladder_score is not None:
            ladder_score_info.append({"pid": self_pid, "score": ladder_score})

        return {
            "room_guuid": self._normalize_room_guuid(raw_data.get("room_guuid")),
            "scene_id": self._as_int(raw_data.get("scene_id_copy")),
            "match_type": self._as_int(raw_data.get("match_type")),
            "rank_level": self._as_int(base_info.get("rank_level")),
            "kill_num": self._as_int(base_info.get("kill_num")),
            "utype": self._as_int(base_info.get("utype")),
            "pid": self_pid,
            "game_save_time": self._normalize_game_save_time(raw_data.get("game_save_time")),
            "cipher_progress": self._normalize_cipher_progress(spec_info.get("generator_status")),
            "players": parsed_players,
            "ladder_score_info": ladder_score_info,
        }
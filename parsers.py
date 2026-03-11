from typing import Dict, Any

class AbstractReplayParser:
    def parse(self, raw_data: Any) -> Dict[str, Any]:
        raise NotImplementedError

class IdentityVReplayParser(AbstractReplayParser):
    def parse(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        self_res = raw_data.get("self_result", {})
        spec_info = self_res.get("spec_info", {})
        all_players = raw_data.get("all_player_result", [])
        base_info = self_res.get("base_info", {})
        return {
            "game_info": {
                "scene_id": raw_data.get("scene_id_copy"),
                "match_type": raw_data.get("match_type"),
                "kill_num": base_info.get("kill_num"),
                "is_mvp": raw_data.get("is_mvp"),
                "game_save_time": raw_data.get("game_save_time"),
                "cipher_progress": spec_info.get("generator_status", []),
                "room_guuid": raw_data.get("room_guuid")
            },
            "players": [
                {
                    "uid": p.get("unique_id"), "player_name": p.get("player_name"), 
                    "pid": p.get("pid"), "utype": p.get("utype"), 
                    "res_type": p.get("res_type"), "is_self": p.get("is_self"), 
                    "result": p.get("result"), "spec_info": p.get("spec_info", {})
                } 
                for p in all_players
            ]
        }

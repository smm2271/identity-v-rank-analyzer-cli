import uuid
from datetime import datetime, timezone

import pytest

from parsers import IdentityVReplayParser


class TestIdentityVReplayParser:
    def setup_method(self):
        self.parser = IdentityVReplayParser()

    def test_as_int(self):
        assert self.parser._as_int(42) == 42
        assert self.parser._as_int("42") == 42
        assert self.parser._as_int(None) is None
        assert self.parser._as_int("abc") is None
        assert self.parser._as_int(3.14) == 3
        assert self.parser._as_int("3.14") is None

    def test_normalize_cipher_progress(self):
        assert self.parser._normalize_cipher_progress(None) is None
        assert self.parser._normalize_cipher_progress({"1": 100}) == {"1": 100}
        assert self.parser._normalize_cipher_progress([1, 2, 3]) == {"generator_status": [1, 2, 3]}
        assert self.parser._normalize_cipher_progress("not-a-dict") == {"generator_status": "not-a-dict"}

    def test_normalize_room_guuid(self):
        assert self.parser._normalize_room_guuid(None) is None
        assert self.parser._normalize_room_guuid("") is None
        assert self.parser._normalize_room_guuid("   ") is None
        
        # Valid UUID
        valid_uuid = str(uuid.uuid4())
        assert self.parser._normalize_room_guuid(valid_uuid) == valid_uuid
        
        # Non-UUID string
        non_uuid_str = "1a2b3c4d5e6f7a8b9c0d1e2f"
        normalized = self.parser._normalize_room_guuid(non_uuid_str)
        assert normalized is not None
        assert normalized != non_uuid_str
        # Should be deterministic
        assert self.parser._normalize_room_guuid(non_uuid_str) == normalized
        # Should be a valid UUID format
        assert str(uuid.UUID(normalized)) == normalized

    def test_normalize_game_save_time(self):
        assert self.parser._normalize_game_save_time(None) is None
        assert self.parser._normalize_game_save_time("") is None
        
        # Datetime object
        dt = datetime(2024, 1, 15, 10, 30, 0)
        assert self.parser._normalize_game_save_time(dt) == "2024-01-15T10:30:00"
        
        # Valid string formats
        assert self.parser._normalize_game_save_time("2024_01_15_10_30_00") == "2024-01-15T10:30:00"
        assert self.parser._normalize_game_save_time("2024-01-15 10:30:00") == "2024-01-15T10:30:00"
        assert self.parser._normalize_game_save_time("2024-01-15T10:30:00") == "2024-01-15T10:30:00"
        assert self.parser._normalize_game_save_time("2024-01-15T10:30:00.123456") == "2024-01-15T10:30:00"
        assert self.parser._normalize_game_save_time("2024-01-15T10:30:00Z") == "2024-01-15T10:30:00+00:00"
        
        # Invalid format
        assert self.parser._normalize_game_save_time("not-a-date") is None

    def test_parse_full_data(self):
        raw_data = {
            "room_guuid": "test_room",
            "scene_id_copy": "1",
            "match_type": "2",
            "game_save_time": "2024-01-01 12:00:00",
            "self_result": {
                "base_info": {
                    "rank_level": "5",
                    "kill_num": "4",
                    "utype": "1",
                    "pid": "1001",
                    "us_warm_info": {
                        "character_ladder_score": "5000"
                    }
                },
                "spec_info": {
                    "generator_status": [0, 0, 0, 0, 0]
                }
            },
            "all_player_result": [
                {"unique_id": "111", "pid": "1001", "player_name": "Hunter", "res_type": "1"},
                {"unique_id": "222", "pid": "2001", "player_name": "Surv1", "res_type": "3"},
                {"unique_id": "333", "pid": "2002", "player_name": "Surv2", "res_type": "3"},
                {"unique_id": "invalid", "pid": "2003", "player_name": "Surv3", "res_type": "3"},  # Invalid id
                {"unique_id": "444", "pid": None, "player_name": "Surv4", "res_type": "3"},       # Missing character
            ]
        }

        parsed = self.parser.parse(raw_data)
        
        assert parsed["scene_id"] == 1
        assert parsed["match_type"] == 2
        assert parsed["rank_level"] == 5
        assert parsed["kill_num"] == 4
        assert parsed["utype"] == 1
        assert parsed["pid"] == 1001
        assert parsed["game_save_time"] == "2024-01-01T12:00:00"
        assert parsed["cipher_progress"] == {"generator_status": [0, 0, 0, 0, 0]}
        
        assert len(parsed["players"]) == 3
        assert parsed["players"][0]["player_id"] == 111
        assert parsed["players"][0]["player_name"] == "Hunter"
        
        assert len(parsed["ladder_score_info"]) == 1
        assert parsed["ladder_score_info"][0]["pid"] == 1001
        assert parsed["ladder_score_info"][0]["score"] == 5000

    def test_parse_missing_data(self):
        # Empty raw data should not crash and return defaults (None/empty)
        parsed = self.parser.parse({})
        
        assert parsed["room_guuid"] is None
        assert parsed["scene_id"] is None
        assert parsed["match_type"] is None
        assert parsed["rank_level"] is None
        assert parsed["kill_num"] is None
        assert parsed["utype"] is None
        assert parsed["pid"] is None
        assert parsed["game_save_time"] is None
        assert parsed["cipher_progress"] is None
        assert parsed["players"] == []
        assert parsed["ladder_score_info"] == []

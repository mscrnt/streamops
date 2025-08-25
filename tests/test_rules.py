import pytest
import json
from unittest.mock import Mock, AsyncMock, patch

from app.worker.rules.engine import RulesEngine, Rule


class TestRule:
    
    @pytest.mark.unit
    async def test_rule_matches_event(self):
        """Test rule matching against events."""
        rule = Rule(
            id="test_rule",
            name="Test Rule",
            priority=100,
            when_conditions={
                "event": "file.closed",
                "path_glob": "*.mkv"
            },
            do_actions=[]
        )
        
        # Should match
        assert await rule.matches("file.closed", {"path": "/test/video.mkv"}) is True
        
        # Should not match - wrong event
        assert await rule.matches("file.opened", {"path": "/test/video.mkv"}) is False
        
        # Should not match - wrong extension
        assert await rule.matches("file.closed", {"path": "/test/video.mp4"}) is False
    
    @pytest.mark.unit
    async def test_rule_any_conditions(self):
        """Test rule with 'any' conditions (OR logic)."""
        rule = Rule(
            id="test_rule",
            name="Test Rule",
            priority=100,
            when_conditions={
                "any": [
                    {"event": "file.closed", "path_glob": "*.mkv"},
                    {"event": "manual.trigger", "conditions": {"type": "preview"}}
                ]
            },
            do_actions=[]
        )
        
        # Should match first condition
        assert await rule.matches("file.closed", {"path": "/test/video.mkv"}) is True
        
        # Should match second condition
        assert await rule.matches("manual.trigger", {"type": "preview"}) is True
        
        # Should not match
        assert await rule.matches("file.closed", {"path": "/test/video.mp4"}) is False
    
    @pytest.mark.unit
    def test_rule_complex_conditions(self):
        """Test rule with complex conditions."""
        rule = Rule(
            id="test_rule",
            name="Test Rule",
            priority=100,
            when_conditions={
                "event": "asset.aged",
                "conditions": {
                    "age_days": {"$gte": 90},
                    "status": "indexed"
                }
            },
            do_actions=[]
        )
        
        # Test $gte operator
        assert rule._check_condition("age_days", {"$gte": 90}, {"age_days": 100}) is True
        assert rule._check_condition("age_days", {"$gte": 90}, {"age_days": 50}) is False
        
        # Test equality
        assert rule._check_condition("status", "indexed", {"status": "indexed"}) is True
        assert rule._check_condition("status", "indexed", {"status": "pending"}) is False


class TestRulesEngine:
    
    @pytest.mark.rules
    async def test_load_rules(self, test_db):
        """Test loading rules from database."""
        # Insert test rule
        await test_db.execute(
            """
            INSERT INTO so_rules (id, name, enabled, priority, when_json, do_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "rule_1",
                "Test Rule",
                1,
                100,
                json.dumps({"event": "file.closed", "path_glob": "*.mkv"}),
                json.dumps([{"type": "index_asset", "params": {}}])
            )
        )
        await test_db.commit()
        
        engine = RulesEngine()
        await engine.load_rules()
        
        assert len(engine.rules) == 1
        assert engine.rules[0].name == "Test Rule"
    
    @pytest.mark.rules
    async def test_evaluate_event(self, mock_nats):
        """Test evaluating events against rules."""
        engine = RulesEngine(mock_nats)
        
        # Add test rule
        rule = Rule(
            id="test_rule",
            name="Test Rule",
            priority=100,
            when_conditions={
                "event": "file.closed",
                "path_glob": "*.mkv"
            },
            do_actions=[
                {"type": "index_asset", "params": {}}
            ]
        )
        engine.rules = [rule]
        
        # Mock execute_rule
        engine.execute_rule = AsyncMock()
        
        # Evaluate matching event
        await engine.evaluate_event("file.closed", {"path": "/test/video.mkv"})
        
        engine.execute_rule.assert_called_once_with(rule, {"path": "/test/video.mkv"})
    
    @pytest.mark.rules
    async def test_execute_action_remux(self, mock_nats):
        """Test executing remux action."""
        engine = RulesEngine(mock_nats)
        
        action = {
            "type": "ffmpeg_remux",
            "params": {
                "container": "mov",
                "faststart": True
            }
        }
        
        context = {"path": "/test/video.mkv"}
        
        await engine.execute_action(action, context)
        
        # Verify job was published
        mock_nats.publish_job.assert_called_once()
        call_args = mock_nats.publish_job.call_args
        assert call_args[0][0] == "remux"
        assert call_args[0][1]["input_path"] == "/test/video.mkv"
        assert call_args[0][1]["output_format"] == "mov"
    
    @pytest.mark.rules
    @patch("shutil.move")
    async def test_execute_action_move(self, mock_move, mock_nats, temp_media_dir):
        """Test executing move action."""
        engine = RulesEngine(mock_nats)
        
        # Create test file
        test_file = temp_media_dir / "video.mkv"
        test_file.write_text("content")
        
        action = {
            "type": "move",
            "params": {
                "dest": "/dest/{YYYY}/{MM}/{DD}/"
            }
        }
        
        context = {"path": str(test_file)}
        
        await engine.execute_action(action, context)
        
        # Verify move was called
        mock_move.assert_called_once()
        call_args = mock_move.call_args[0]
        assert str(test_file) in call_args[0]
        assert "/dest/" in call_args[1]
    
    @pytest.mark.rules
    async def test_variable_substitution(self):
        """Test variable substitution in parameters."""
        engine = RulesEngine()
        
        params = {
            "dest": "/path/{Game}/{YYYY}/{MM}/{DD}/",
            "name": "{asset_id}_processed"
        }
        
        context = {
            "Game": "Valorant",
            "asset_id": "asset_123"
        }
        
        result = engine._substitute_variables(params, context)
        
        assert "Valorant" in result["dest"]
        assert result["name"] == "asset_123_processed"
        
        # Date variables should be substituted
        from datetime import datetime
        now = datetime.now()
        assert now.strftime("%Y") in result["dest"]
        assert now.strftime("%m") in result["dest"]
        assert now.strftime("%d") in result["dest"]
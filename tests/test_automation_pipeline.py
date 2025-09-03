"""
Tests for the context-driven automation pipeline.
Ensures correct file extension handling and action sequencing.
"""
import os
import json
import pytest
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

# Add app to path
import sys
sys.path.insert(0, '/mnt/d/Projects/streamops')

from app.worker.rules.models import Artifact, RuleContext, ActionResult
from app.worker.rules.template import expand_template, build_target_path
from app.worker.rules.engine import RulesEngine


class TestTemplateExpansion:
    """Test template expansion with active artifact."""
    
    def test_expand_template_with_mov_extension(self):
        """Test that {filename} and {ext} reflect the current active artifact."""
        # Setup context with .mov file (post-remux)
        mov_path = Path("/tmp/recordings/2025-09-01 11-47-07.mov")
        artifact = Artifact(path=mov_path, ext=".mov")
        ctx = RuleContext(
            original=Artifact(path=Path("/tmp/recordings/2025-09-01 11-47-07.mkv")),
            active=artifact
        )
        
        # Test filename expansion
        pattern = "/mnt/drive_d/Editing/{year}/{month}/{filename}"
        result = expand_template(pattern, ctx)
        
        # Should use the active artifact's filename (with .mov)
        assert result.endswith("2025-09-01 11-47-07.mov")
        assert "/Editing/" in result
        
    def test_expand_template_preserves_extension(self):
        """Test that extension is preserved from active artifact."""
        # Original was .mkv, but active is now .mov
        original = Artifact(path=Path("/recordings/clip.mkv"))
        active = Artifact(path=Path("/tmp/clip.mov"))
        ctx = RuleContext(original=original, active=active)
        
        # Expand with {stem} and {ext}
        pattern = "/output/{stem}_processed{ext}"
        result = expand_template(pattern, ctx)
        
        assert result == "/output/clip_processed.mov"
        assert not result.endswith(".mkv")
    
    def test_build_target_path(self):
        """Test building complete target paths."""
        active = Artifact(path=Path("/tmp/video.mov"))
        ctx = RuleContext(original=active, active=active)
        
        template = "/archive/{year}/{month}/{day}/{filename}"
        target = build_target_path(template, ctx)
        
        assert isinstance(target, Path)
        assert target.name == "video.mov"
        assert target.suffix == ".mov"


class TestArtifactModel:
    """Test the Artifact dataclass."""
    
    def test_artifact_auto_extension(self):
        """Test that Artifact derives extension from path if not provided."""
        artifact = Artifact(path=Path("/tmp/video.mov"))
        assert artifact.ext == ".mov"
        
        artifact2 = Artifact(path="/tmp/audio.mp3")  # String path
        assert artifact2.ext == ".mp3"
        assert isinstance(artifact2.path, Path)
    
    def test_artifact_with_metadata(self):
        """Test artifact with metadata."""
        artifact = Artifact(
            path=Path("/tmp/video.mov"),
            mime="video/quicktime",
            meta={"duration_sec": 120, "codec": "h264"}
        )
        assert artifact.mime == "video/quicktime"
        assert artifact.meta["duration_sec"] == 120


class TestRuleContext:
    """Test the RuleContext model."""
    
    def test_context_update_active(self):
        """Test updating active artifact adds to history."""
        original = Artifact(path=Path("/tmp/original.mkv"))
        ctx = RuleContext(original=original, active=original)
        
        # Update to remuxed file
        remuxed = Artifact(path=Path("/tmp/original.mov"))
        ctx.update_active(remuxed)
        
        assert ctx.active == remuxed
        assert len(ctx.history) == 1
        assert ctx.history[0] == original
        
        # Update to moved file
        moved = Artifact(path=Path("/archive/original.mov"))
        ctx.update_active(moved)
        
        assert ctx.active == moved
        assert len(ctx.history) == 2
        assert ctx.history[1] == remuxed


@pytest.mark.asyncio
class TestRulesEngineActions:
    """Test rule engine action implementations."""
    
    async def test_remux_then_move_preserves_extension(self, tmp_path):
        """Integration test: remux MKV to MOV, then move preserves .mov extension."""
        # Create source file
        src = tmp_path / "recordings" / "clip.mkv"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"fake mkv content")
        
        # Create expected remux output
        remux_out = src.with_suffix(".mov")
        
        # Setup context
        original = Artifact(path=src)
        ctx = RuleContext(original=original, active=original)
        
        # Mock NATS and database for remux action
        engine = RulesEngine()
        engine.nats = AsyncMock()
        
        with patch('app.worker.rules.engine.aiosqlite.connect') as mock_connect:
            # Mock database operations
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            mock_conn.row_factory = None
            
            # First poll: queued
            # Second poll: completed with output_path
            mock_cursor = AsyncMock()
            mock_cursor.fetchone = AsyncMock(side_effect=[
                {"state": "queued", "result_json": None},
                {"state": "completed", "result_json": json.dumps({
                    "output_path": str(remux_out)
                })}
            ])
            mock_conn.execute.return_value = mock_cursor
            
            # Create the remuxed file (simulating job completion)
            remux_out.write_bytes(b"fake mov content")
            
            # Execute remux action
            result = await engine._action_remux_v2(
                {"container": "mov", "faststart": True},
                ctx
            )
            
            assert result.success
            assert result.primary_output_path == remux_out
            assert ctx.active.path == remux_out
            assert ctx.active.ext == ".mov"
        
        # Now execute move action
        editing_dir = tmp_path / "Editing" / "2025" / "01"
        move_params = {
            "target": str(tmp_path / "Editing" / "{year}" / "{month}" / "{filename}")
        }
        
        move_result = await engine._action_move_v2(move_params, ctx)
        
        assert move_result.success
        moved_path = move_result.primary_output_path
        
        # Critical assertion: moved file keeps .mov extension
        assert moved_path.suffix == ".mov"
        assert moved_path.name == "clip.mov"
        assert not moved_path.name.endswith(".mkv")
        
        # Verify context updated
        assert ctx.active.path == moved_path
        assert ctx.active.ext == ".mov"
    
    async def test_move_action_cross_device(self, tmp_path):
        """Test move action handles cross-device moves."""
        src = tmp_path / "source.mov"
        src.write_bytes(b"content")
        
        ctx = RuleContext(
            original=Artifact(path=src),
            active=Artifact(path=src)
        )
        
        engine = RulesEngine()
        
        # Mock os.replace to raise OSError (cross-device)
        with patch('os.replace', side_effect=OSError("Cross-device link")):
            with patch('shutil.move') as mock_move:
                mock_move.return_value = None
                
                result = await engine._action_move_v2(
                    {"target": str(tmp_path / "dest" / "{filename}")},
                    ctx
                )
                
                # Should fall back to shutil.move
                mock_move.assert_called_once()
                assert result.success
    
    async def test_copy_action_preserves_active(self, tmp_path):
        """Test copy action doesn't change active artifact."""
        src = tmp_path / "source.mov"
        src.write_bytes(b"content")
        
        original_artifact = Artifact(path=src)
        ctx = RuleContext(
            original=original_artifact,
            active=original_artifact
        )
        
        engine = RulesEngine()
        
        result = await engine._action_copy_v2(
            {"target": str(tmp_path / "backup" / "{filename}")},
            ctx
        )
        
        assert result.success
        # Active should still be the original
        assert ctx.active.path == src
        # But we should have the copy in outputs
        assert "copy" in result.outputs
    
    async def test_full_pipeline_with_multiple_actions(self, tmp_path):
        """Test complete pipeline: remux → move → proxy → thumbnail."""
        src = tmp_path / "recordings" / "stream_2025-01-15.mkv"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"mkv data")
        
        # Setup rule with multiple actions
        rule_data = {
            "id": "test_rule",
            "name": "Test Pipeline",
            "actions": [
                {"type": "ffmpeg_remux", "params": {"container": "mov"}},
                {"type": "move", "params": {
                    "target": str(tmp_path / "Editing" / "{year}" / "{filename}")
                }},
                {"type": "proxy", "params": {"codec": "dnxhr_lb"}},
                {"type": "thumbnail", "params": {}}
            ]
        }
        
        engine = RulesEngine()
        engine.nats = AsyncMock()
        
        # Execute rule - this tests the full context pipeline
        with patch('app.worker.rules.engine.aiosqlite.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            # Simulate remux creating .mov file
            remuxed = src.with_suffix(".mov")
            remuxed.write_bytes(b"mov data")
            
            # Mock job completion
            mock_cursor = AsyncMock()
            mock_cursor.fetchone = AsyncMock(return_value={
                "state": "completed",
                "result_json": json.dumps({"output_path": str(remuxed)})
            })
            mock_conn.execute.return_value = mock_cursor
            
            await engine.execute_rule(
                rule_data,
                {"path": str(src), "asset_id": "test_asset"}
            )
            
            # Verify NATS jobs were published
            calls = engine.nats.publish_job.call_args_list
            
            # Should have remux, proxy, and thumbnail jobs
            job_types = [call[0][0] for call in calls]
            assert "remux" in job_types
            assert "proxy" in job_types
            assert "thumbnail" in job_types
            
            # Verify final file location has .mov extension
            editing_files = list((tmp_path / "Editing").rglob("*.mov"))
            assert len(editing_files) == 1
            assert editing_files[0].name == "stream_2025-01-15.mov"


class TestEndToEndScenarios:
    """End-to-end tests for common scenarios."""
    
    def test_remux_then_move_preserves_new_extension(self, tmp_path):
        """Test the exact scenario from requirements."""
        src = tmp_path / "clip.mkv"
        src.write_bytes(b"dummy mkv")
        
        # Fake remux result
        remux_out = tmp_path / "clip.mov"
        remux_out.write_bytes(b"dummy mov")
        
        ctx = RuleContext(
            original=Artifact(path=src, ext=".mkv"),
            active=Artifact(path=src, ext=".mkv"),
        )
        
        # Simulate remux completion
        ctx.active = Artifact(path=remux_out, ext=".mov")
        
        # Move action
        tpl = str(tmp_path / "Editing" / "{year}" / "{month}" / "{filename}")
        dest = Path(expand_template(tpl, ctx))
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(ctx.active.path), str(dest))
        ctx.active = Artifact(path=dest, ext=dest.suffix)
        
        # Critical assertions from requirements
        assert dest.suffix == ".mov"
        assert dest.name.endswith(".mov")
        assert not dest.name.endswith(".mkv")
    
    def test_template_tokens_from_active_artifact(self):
        """Test all tokens derive from ctx.active.path."""
        # Start with MKV
        original = Artifact(path=Path("/rec/2025-01-15 10-30-45.mkv"))
        ctx = RuleContext(original=original, active=original)
        
        # After remux, active is MOV
        remuxed = Artifact(path=Path("/tmp/2025-01-15 10-30-45.mov"))
        ctx.update_active(remuxed)
        
        # Template should use active artifact
        pattern = "/archive/{year}/{month}/{day}/{stem}{ext}"
        result = expand_template(pattern, ctx)
        
        # Should have .mov from active, not .mkv from original
        assert result.endswith("2025-01-15 10-30-45.mov")
        assert ".mkv" not in result
        
        # Verify date tokens work
        assert "/2025/01/" in result  # From file mtime


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
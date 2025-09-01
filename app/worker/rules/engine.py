import os
import re
import yaml
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from fnmatch import fnmatch

logger = logging.getLogger(__name__)

class RulesEngine:
    """Rules engine for automating media processing workflows"""
    
    def __init__(self, nats_service=None):
        self.nats = nats_service
        self.rules: List[Rule] = []
        self.enabled = True
        
    async def load_rules(self):
        """Load rules from database"""
        import sqlite3
        
        try:
            # Use direct SQLite connection instead of async
            conn = sqlite3.connect("/data/db/streamops.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, name, priority, trigger_json, conditions_json, 
                       actions_json, guardrails_json, quiet_period_sec
                FROM so_rules 
                WHERE enabled = 1 
                ORDER BY priority DESC, created_at ASC
            """)
            
            rows = cursor.fetchall()
            conn.close()
                
            self.rules = []
            for row in rows:
                # Convert new format to old format for compatibility
                trigger = json.loads(row['trigger_json']) if row['trigger_json'] else {}
                conditions = json.loads(row['conditions_json']) if row['conditions_json'] else []
                actions = json.loads(row['actions_json']) if row['actions_json'] else []
                guardrails = json.loads(row['guardrails_json']) if row['guardrails_json'] else {}
                
                # Build when_conditions in expected format
                when_conditions = {
                    'event': trigger.get('type', 'file_closed'),
                    'conditions': {}
                }
                
                # Convert conditions to old format
                for condition in conditions:
                    field = condition.get('field', '')
                    op = condition.get('op', '')
                    value = condition.get('value', '')
                    
                    # Map to expected format
                    if field and op and value:
                        when_conditions['conditions'][field] = value
                
                # Convert actions to expected format  
                do_actions = []
                for action in actions:
                    if isinstance(action, dict):
                        for action_type, params in action.items():
                            do_actions.append({
                                'type': action_type,
                                'params': params if isinstance(params, dict) else {}
                            })
                
                rule = Rule(
                    id=row['id'],
                    name=row['name'],
                    priority=row['priority'],
                    when_conditions=when_conditions,
                    do_actions=do_actions
                )
                self.rules.append(rule)
            
            logger.info(f"Loaded {len(self.rules)} active rules")
            
        except Exception as e:
            logger.error(f"Failed to load rules: {e}")
    
    async def evaluate_event(self, event_type: str, event_data: Dict[str, Any]):
        """Evaluate an event against all rules"""
        if not self.enabled:
            return
        
        logger.debug(f"Evaluating event {event_type}: {event_data}")
        
        for rule in self.rules:
            try:
                if await rule.matches(event_type, event_data):
                    logger.info(f"Rule '{rule.name}' matched for event {event_type}")
                    await self.execute_rule(rule, event_data)
            except Exception as e:
                logger.error(f"Error evaluating rule '{rule.name}': {e}")
    
    async def execute_rule(self, rule: 'Rule', context: Dict[str, Any]):
        """Execute a rule's actions"""
        for action in rule.do_actions:
            try:
                await self.execute_action(action, context)
            except Exception as e:
                logger.error(f"Error executing action {action.get('type')}: {e}")
    
    async def execute_action(self, action: Dict[str, Any], context: Dict[str, Any]):
        """Execute a single action"""
        action_type = action.get("type")
        params = action.get("params", {})
        
        # Substitute variables in params
        params = self._substitute_variables(params, context)
        
        if action_type == "ffmpeg_remux":
            await self._action_remux(params, context)
        elif action_type == "move":
            await self._action_move(params, context)
        elif action_type == "copy":
            await self._action_copy(params, context)
        elif action_type == "index_asset":
            await self._action_index(params, context)
        elif action_type in ["make_proxies_if", "proxy"]:  # Support both names
            await self._action_proxy(params, context)
        elif action_type == "thumbs":
            await self._action_thumbnail(params, context)
        elif action_type == "transcode_preset":
            await self._action_transcode(params, context)
        elif action_type == "tag":
            await self._action_tag(params, context)
        elif action_type == "overlay_update":
            await self._action_overlay(params, context)
        elif action_type == "custom_hook":
            await self._action_custom_hook(params, context)
        else:
            logger.warning(f"Unknown action type: {action_type}")
    
    async def _action_remux(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute remux action"""
        if not self.nats:
            return
        
        job_id = self._generate_job_id("remux")
        asset_id = context.get("asset_id", "")
        
        # Save job to database first
        try:
            import aiosqlite
            import json
            from datetime import datetime
            
            conn = await aiosqlite.connect("/data/db/streamops.db")
            
            # Insert job into database
            await conn.execute("""
                INSERT INTO so_jobs (id, type, asset_id, payload_json, state, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'queued', ?, ?)
            """, (
                job_id,
                "ffmpeg_remux",  # Use full type name for database
                asset_id,
                json.dumps({
                    "output_format": params.get("container", "mov"),
                    "faststart": params.get("faststart", True)
                }),
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat()
            ))
            await conn.commit()
            await conn.close()
            
            logger.info(f"Created job {job_id} in database")
        except Exception as e:
            logger.error(f"Failed to save job to database: {e}")
        
        # Publish to NATS
        job_data = {
            "id": job_id,
            "input_path": context.get("path"),
            "output_format": params.get("container", "mov"),
            "faststart": params.get("faststart", True)
        }
        
        await self.nats.publish_job("remux", job_data)
        logger.info(f"Queued remux job: {job_id}")
    
    async def _action_move(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute move action"""
        import shutil
        
        source = Path(context.get("path"))
        dest_pattern = params.get("dest") or params.get("target")  # Support both dest and target
        
        if not source.exists() or not dest_pattern:
            return
        
        # Expand destination pattern
        dest = self._expand_path_pattern(dest_pattern, context)
        dest_path = Path(dest)
        
        # Create destination directory
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move file
        shutil.move(str(source), str(dest_path))
        logger.info(f"Moved {source} to {dest_path}")
        
        # Update context with new path
        context["path"] = str(dest_path)
    
    async def _action_copy(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute copy action"""
        import shutil
        
        source = Path(context.get("path"))
        dest_pattern = params.get("dest") or params.get("target")  # Support both dest and target
        
        if not source.exists() or not dest_pattern:
            return
        
        # Expand destination pattern
        dest = self._expand_path_pattern(dest_pattern, context)
        dest_path = Path(dest)
        
        # Create destination directory
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy file
        shutil.copy2(str(source), str(dest_path))
        logger.info(f"Copied {source} to {dest_path}")
    
    async def _action_index(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute index action"""
        if not self.nats:
            return
        
        job_data = {
            "id": self._generate_job_id("index"),
            "input_path": context.get("path")
        }
        
        await self.nats.publish_job("index", job_data)
        logger.info(f"Queued index job: {job_data['id']}")
    
    async def _action_proxy(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute proxy creation action"""
        if not self.nats:
            return
        
        # Check duration condition
        min_duration = params.get("min_duration_sec", 900)
        duration = context.get("duration_sec", 0)
        
        if duration < min_duration:
            logger.debug(f"Skipping proxy - duration {duration}s < {min_duration}s")
            return
        
        job_id = self._generate_job_id("proxy")
        asset_id = context.get("asset_id", "")
        
        # Save job to database first
        try:
            import aiosqlite
            import json
            from datetime import datetime
            
            conn = await aiosqlite.connect("/data/db/streamops.db")
            
            # Insert job into database
            await conn.execute("""
                INSERT INTO so_jobs (id, type, asset_id, payload_json, state, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'queued', ?, ?)
            """, (
                job_id,
                "proxy_create",  # Use correct type name for database
                asset_id,
                json.dumps({
                    "codec": params.get("codec", "dnxhr_lb")
                }),
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat()
            ))
            await conn.commit()
            await conn.close()
            
            logger.info(f"Created proxy job {job_id} in database")
        except Exception as e:
            logger.error(f"Failed to save proxy job to database: {e}")
        
        # Publish to NATS
        job_data = {
            "id": job_id,
            "input_path": context.get("path"),
            "codec": params.get("codec", "dnxhr_lb")
        }
        
        await self.nats.publish_job("proxy", job_data)
        logger.info(f"Queued proxy job: {job_id}")
    
    async def _action_thumbnail(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute thumbnail generation action"""
        if not self.nats:
            return
        
        job_data = {
            "id": self._generate_job_id("thumbnail"),
            "input_path": context.get("path"),
            "asset_id": context.get("asset_id")
        }
        
        await self.nats.publish_job("thumbnail", job_data)
        logger.info(f"Queued thumbnail job: {job_data['id']}")
    
    async def _action_transcode(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute transcode action"""
        if not self.nats:
            return
        
        job_data = {
            "id": self._generate_job_id("transcode"),
            "input_path": context.get("path"),
            "preset": params.get("preset", "web_1080p")
        }
        
        await self.nats.publish_job("transcode", job_data)
        logger.info(f"Queued transcode job: {job_data['id']}")
    
    async def _action_tag(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute tag action"""
        from app.api.db.database import get_db
        
        asset_id = context.get("asset_id")
        tags = params.get("tags", [])
        
        if not asset_id or not tags:
            return
        
        try:
            db = await get_db()
            
            # Get existing tags
            async with db.execute(
                "SELECT tags_json FROM so_assets WHERE id = ?",
                (asset_id,)
            ) as cursor:
                row = await cursor.fetchone()
                existing_tags = json.loads(row[0]) if row and row[0] else []
            
            # Add new tags
            all_tags = list(set(existing_tags + tags))
            
            # Update asset
            await db.execute(
                "UPDATE so_assets SET tags_json = ? WHERE id = ?",
                (json.dumps(all_tags), asset_id)
            )
            await db.commit()
            
            logger.info(f"Added tags {tags} to asset {asset_id}")
            
        except Exception as e:
            logger.error(f"Failed to add tags: {e}")
    
    async def _action_overlay(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute overlay update action"""
        # Implement overlay updates
        overlay_id = params.get('overlay_id')
        if overlay_id:
            try:
                from app.api.services.overlay_service import update_overlay
                await update_overlay(overlay_id, params.get('content', {}))
                logger.info(f"Updated overlay {overlay_id}")
            except ImportError:
                logger.warning("Overlay service not available")
            except Exception as e:
                logger.error(f"Failed to update overlay: {e}")
    
    async def _action_custom_hook(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute custom hook action"""
        command = params.get("command")
        if not command:
            return
        
        # Substitute variables
        command = self._substitute_variables(command, context)
        
        # Execute command
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Custom hook failed: {stderr.decode()}")
        else:
            logger.info(f"Custom hook executed: {command}")
    
    def _substitute_variables(self, value: Any, context: Dict[str, Any]) -> Any:
        """Substitute variables in a value"""
        if isinstance(value, str):
            # Replace variables like {Game}, {YYYY}, etc.
            for key, val in context.items():
                value = value.replace(f"{{{key}}}", str(val))
            
            # Replace date variables
            now = datetime.now()
            value = value.replace("{YYYY}", now.strftime("%Y"))
            value = value.replace("{year}", now.strftime("%Y"))
            value = value.replace("{MM}", now.strftime("%m"))
            value = value.replace("{month}", now.strftime("%m"))
            value = value.replace("{DD}", now.strftime("%d"))
            value = value.replace("{day}", now.strftime("%d"))
            
            # Replace filename variable
            if "{filename}" in value:
                source_path = Path(context.get("path", context.get("file_path", "")))
                if source_path:
                    value = value.replace("{filename}", source_path.name)
            
            return value
        elif isinstance(value, dict):
            return {k: self._substitute_variables(v, context) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._substitute_variables(v, context) for v in value]
        else:
            return value
    
    def _expand_path_pattern(self, pattern: str, context: Dict[str, Any]) -> str:
        """Expand a path pattern with variables"""
        path = self._substitute_variables(pattern, context)
        
        # Add filename if path ends with /
        if path.endswith("/"):
            source_path = Path(context.get("path", ""))
            path += source_path.name
        
        return path
    
    def _generate_job_id(self, job_type: str) -> str:
        """Generate unique job ID"""
        import hashlib
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        return f"{job_type}_{timestamp[:15]}"


class Rule:
    """Represents a single automation rule"""
    
    def __init__(self, id: str, name: str, priority: int, 
                 when_conditions: Dict[str, Any], do_actions: List[Dict[str, Any]]):
        self.id = id
        self.name = name
        self.priority = priority
        self.when_conditions = when_conditions
        self.do_actions = do_actions
    
    async def matches(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Check if rule matches the event"""
        # Check event type
        if self.when_conditions.get("event") != event_type:
            if not self._check_any_conditions(event_type, event_data):
                return False
        
        # Check path glob
        path_glob = self.when_conditions.get("path_glob")
        if path_glob:
            path = event_data.get("path", "")
            if not fnmatch(path, path_glob):
                return False
        
        # Check minimum quiet seconds
        min_quiet = self.when_conditions.get("min_quiet_seconds")
        if min_quiet:
            # This is typically already handled by the watcher
            pass
        
        # Check custom conditions
        conditions = self.when_conditions.get("conditions", {})
        for key, value in conditions.items():
            if not self._check_condition(key, value, event_data):
                return False
        
        return True
    
    def _check_any_conditions(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Check 'any' conditions (OR logic)"""
        any_conditions = self.when_conditions.get("any", [])
        
        for condition in any_conditions:
            if condition.get("event") == event_type:
                # Check additional conditions in this branch
                path_glob = condition.get("path_glob")
                if path_glob:
                    path = event_data.get("path", "")
                    if fnmatch(path, path_glob):
                        return True
                else:
                    return True
        
        return False
    
    def _check_condition(self, key: str, expected: Any, data: Dict[str, Any]) -> bool:
        """Check a single condition"""
        # Handle nested keys like 'file.extension'
        if '.' in key:
            parts = key.split('.')
            actual = data
            for part in parts:
                if isinstance(actual, dict):
                    actual = actual.get(part)
                else:
                    actual = None
                    break
        else:
            actual = data.get(key)
        
        if isinstance(expected, dict):
            # Complex condition (e.g., {"$gte": 100})
            operator = list(expected.keys())[0]
            value = expected[operator]
            
            if operator == "$gte":
                return actual >= value
            elif operator == "$lte":
                return actual <= value
            elif operator == "$gt":
                return actual > value
            elif operator == "$lt":
                return actual < value
            elif operator == "$ne":
                return actual != value
            elif operator == "$in":
                return actual in value
            elif operator == "$regex":
                return bool(re.match(value, str(actual)))
        else:
            # Simple equality check - handle case-insensitive for strings
            if isinstance(actual, str) and isinstance(expected, str):
                return actual.lower() == expected.lower()
            return actual == expected
        
        return False
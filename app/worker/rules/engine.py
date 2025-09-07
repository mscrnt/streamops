"""
Strictly sequential rule engine - unversioned canonical implementation
"""
import os
import re
import yaml
import json
import logging
import asyncio
import aiosqlite
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timedelta
from fnmatch import fnmatch

from .models import Artifact, RuleContext, ActionResult
from .template import expand_template, build_target_path

logger = logging.getLogger(__name__)


class RulesEngine:
    """Rules engine for automating media processing workflows - strictly sequential"""
    
    def __init__(self, nats_service=None):
        self.nats = nats_service
        self.rules: List[Rule] = []
        self.enabled = True
        self.pending_executions = {}  # Track pending rule executions by file path
        self.execution_queue = []  # Queue of (rule, event_data) tuples waiting for quiet period
        self.quiet_period_task = None  # Track the quiet period waiting task
        
    async def load_rules(self):
        """Load rules from database"""
        import sqlite3
        
        try:
            conn = sqlite3.connect("/data/db/streamops.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, name, priority, trigger_json, conditions_json, 
                       actions_json, guardrails_json, quiet_period_sec
                FROM so_rules 
                WHERE is_active = 1 
                ORDER BY priority DESC, created_at ASC
            """)
            
            rows = cursor.fetchall()
            conn.close()
                
            self.rules = []
            for row in rows:
                trigger = json.loads(row['trigger_json']) if row['trigger_json'] else {}
                conditions = json.loads(row['conditions_json']) if row['conditions_json'] else []
                actions = json.loads(row['actions_json']) if row['actions_json'] else []
                
                when_conditions = {
                    'event': trigger.get('type', 'file_closed'),
                    'conditions': {}
                }
                
                for condition in conditions:
                    field = condition.get('field', '')
                    op = condition.get('op', '')
                    value = condition.get('value', '')
                    
                    if field and op and value:
                        when_conditions['conditions'][field] = value
                
                do_actions = []
                for action in actions:
                    if isinstance(action, dict):
                        for action_type, params in action.items():
                            do_actions.append({
                                'type': action_type,
                                'params': params if isinstance(params, dict) else {}
                            })
                
                # Parse guardrails
                guardrails = {}
                try:
                    guardrails_json = row['guardrails_json']
                    if guardrails_json:
                        guardrails = json.loads(guardrails_json)
                except (json.JSONDecodeError, TypeError, KeyError):
                    pass
                
                rule = Rule(
                    id=row['id'],
                    name=row['name'],
                    priority=row['priority'],
                    when_conditions=when_conditions,
                    do_actions=do_actions,
                    quiet_period_sec=row['quiet_period_sec'] if row['quiet_period_sec'] else 0,
                    guardrails=guardrails
                )
                self.rules.append(rule)
            
            logger.info(f"Loaded {len(self.rules)} active rules")
            
        except Exception as e:
            logger.error(f"Failed to load rules: {e}")
    
    async def evaluate_event(self, event_type: str, event_data: Dict[str, Any]):
        """Single entrypoint for rule evaluation"""
        if not self.enabled:
            return
        
        logger.debug(f"Evaluating event {event_type}: {event_data}")
        
        for rule in self.rules:
            try:
                if await rule.matches(event_type, event_data):
                    logger.info(f"Rule '{rule.name}' matched for event {event_type}")
                    # ONLY path to execute rules - no other execution allowed
                    await self.execute_rule(rule, event_data)
            except Exception as e:
                logger.error(f"Error evaluating rule '{rule.name}': {e}")
    
    async def execute_rule(self, rule: 'Rule', event_data: Dict[str, Any]):
        """Execute a rule either immediately or after quiet period"""
        # Generate run ID for tracing and deduplication
        run_id = f"{rule.id}:{event_data.get('asset_id', '')}:{event_data.get('event_id', '')}"
        file_path = event_data.get('path', '')
        
        # Check if we're already processing this file with this rule
        execution_key = f"{rule.id}:{file_path}"
        if execution_key in self.pending_executions:
            logger.info(f"[{run_id}] Rule already pending for {file_path}, skipping duplicate")
            return
        
        # If there's a quiet period, queue it and create deferred jobs
        if rule.quiet_period_sec > 0:
            # Mark as pending and add to queue
            self.pending_executions[execution_key] = True
            self.execution_queue.append((rule, event_data, execution_key))
            logger.info(f"[{run_id}] Queued rule '{rule.name}' for {file_path} with {rule.quiet_period_sec}s quiet period (queue size: {len(self.execution_queue)})")
            
            # Create deferred jobs immediately so they're visible in UI
            logger.info(f"Creating deferred jobs for rule {rule.name}")
            await self._create_deferred_jobs_for_rule(rule, event_data)
            
            # Start or restart the quiet period manager if not already running
            if self.quiet_period_task is None or self.quiet_period_task.done():
                self.quiet_period_task = asyncio.create_task(self._manage_quiet_period())
        else:
            # No quiet period - execute immediately
            logger.info(f"[{run_id}] No quiet period for rule '{rule.name}', executing immediately")
            await self._execute_rule_actions(rule, event_data)
    
    async def _manage_quiet_period(self):
        """Manage the quiet period and batch process all queued rules"""
        logger.info("Starting quiet period manager")
        
        # Wait for all recordings to stop and quiet period to pass
        max_wait_time = 3600  # Maximum 1 hour
        total_waited = 0
        
        while total_waited < max_wait_time:
            # Check if any recording/streaming is active
            obs_status = await self._check_obs_status()
            if obs_status.get('recording') or obs_status.get('streaming'):
                logger.info(f"Recording/streaming active, waiting... (queue: {len(self.execution_queue)} items)")
                await asyncio.sleep(10)
                total_waited += 10
                continue
            
            # No recording, now wait for quiet period
            # Use the maximum quiet period from all queued rules
            max_quiet_period = 0
            for rule, _, _ in self.execution_queue:
                if rule.quiet_period_sec > max_quiet_period:
                    max_quiet_period = rule.quiet_period_sec
            
            if max_quiet_period > 0:
                logger.info(f"Starting {max_quiet_period}s quiet period for {len(self.execution_queue)} queued items")
                
                # Monitor for new recordings during quiet period
                quiet_elapsed = 0
                while quiet_elapsed < max_quiet_period:
                    await asyncio.sleep(1)
                    quiet_elapsed += 1
                    total_waited += 1
                    
                    # Check if recording started again
                    obs_status = await self._check_obs_status()
                    if obs_status.get('recording') or obs_status.get('streaming'):
                        logger.info(f"Recording started during quiet period (elapsed: {quiet_elapsed}s), resetting...")
                        break  # Go back to waiting for recording to stop
                    
                    if quiet_elapsed % 10 == 0:
                        logger.debug(f"Quiet period: {quiet_elapsed}/{max_quiet_period}s (queue: {len(self.execution_queue)} items)")
                else:
                    # Quiet period completed - activate deferred jobs and clear queue
                    logger.info(f"Quiet period completed, activating deferred jobs for {len(self.execution_queue)} queued rules")
                    activated_count = await self._activate_deferred_jobs()
                    logger.info(f"Activated {activated_count} deferred jobs after quiet period")
                    
                    # Clear the execution queue since jobs were already created as deferred
                    queue_copy = self.execution_queue.copy()
                    self.execution_queue.clear()
                    for _, _, execution_key in queue_copy:
                        self.pending_executions.pop(execution_key, None)
                    return
            else:
                # No quiet period needed, process immediately
                await self._process_execution_queue()
                return
        
        logger.warning("Quiet period manager timed out after 1 hour")
        # Clear the queue without processing
        self.execution_queue.clear()
        self.pending_executions.clear()
    
    async def _execute_rule_actions(self, rule: 'Rule', event_data: Dict[str, Any]):
        """Execute a rule's actions immediately (no quiet period)"""
        run_id = f"{rule.id}:{event_data.get('asset_id', '')}:{event_data.get('event_id', '')}"
        
        try:
            logger.info(f"[{run_id}] Executing rule '{rule.name}'")
            
            # Initialize context with active artifact
            initial_path = Path(event_data.get("path", ""))
            if not initial_path.exists():
                logger.warning(f"[{run_id}] Initial path does not exist: {initial_path}")
                return
                
            initial_artifact = Artifact(path=initial_path)
            ctx = RuleContext(
                original=initial_artifact,
                active=initial_artifact,
                vars=event_data.copy()
            )
            
            # Execute actions strictly in sequence
            for idx, action in enumerate(rule.do_actions):
                action_type = action.get("type")
                logger.info(f"[{run_id}] Step {idx+1}/{len(rule.do_actions)}: {action_type} on {ctx.active.path}")
                
                try:
                    result = await self.execute_action(action, ctx)
                    
                    if result and result.updated_vars:
                        ctx.vars.update(result.updated_vars)
                        
                    logger.info(f"[{run_id}] Step {idx+1} completed: {action_type}")
                        
                except Exception as e:
                    logger.error(f"[{run_id}] Step {idx+1} failed: {action_type} - {e}", exc_info=True)
                    break
        except Exception as e:
            logger.error(f"[{run_id}] Rule execution failed: {e}", exc_info=True)
    
    async def _process_execution_queue(self):
        """Process all queued rule executions sequentially"""
        queue_copy = self.execution_queue.copy()
        self.execution_queue.clear()
        
        for rule, event_data, execution_key in queue_copy:
            try:
                await self._execute_rule_actions(rule, event_data)
            finally:
                # Remove from pending executions
                self.pending_executions.pop(execution_key, None)
    
    
    async def _check_resource_limits(self, rule: 'Rule', run_id: str) -> bool:
        """Check if CPU/GPU usage is within limits"""
        guardrails = rule.guardrails
        
        # Check CPU usage
        cpu_limit = guardrails.get('pause_if_cpu_pct_above')
        if cpu_limit:
            cpu_usage = await self._get_cpu_usage()
            if cpu_usage > cpu_limit:
                logger.debug(f"[{run_id}] CPU usage {cpu_usage}% > {cpu_limit}%")
                return False
        
        # Check GPU usage
        gpu_limit = guardrails.get('pause_if_gpu_pct_above')
        if gpu_limit:
            gpu_usage = await self._get_gpu_usage()
            if gpu_usage > gpu_limit:
                logger.debug(f"[{run_id}] GPU usage {gpu_usage}% > {gpu_limit}%")
                return False
        
        return True
    
    
    async def _check_obs_status(self) -> Dict[str, Any]:
        """Check OBS recording/streaming status via API"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:7767/api/obs/status') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Check if any recording/streaming is active
                        if data.get('recording', 0) > 0 or data.get('streaming', 0) > 0:
                            logger.debug(f"OBS active: recording={data.get('recording', 0)}, streaming={data.get('streaming', 0)}")
                            return {'recording': True, 'streaming': True}
                        # Also check individual connections
                        for conn in data.get('connections', []):
                            if conn.get('recording') or conn.get('streaming'):
                                logger.debug(f"OBS connection {conn.get('name')} is active")
                                return {'recording': True, 'streaming': True}
                        return {'recording': False, 'streaming': False}
        except Exception as e:
            logger.debug(f"Could not check OBS status: {e}")
            # If we can't check, assume not recording
            return {'recording': False, 'streaming': False}
    
    async def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        try:
            import psutil
            return psutil.cpu_percent(interval=1)
        except Exception:
            return 0.0
    
    async def _get_gpu_usage(self) -> float:
        """Get current GPU usage percentage"""
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
        except Exception:
            pass
        return 0.0
    
    async def execute_action(self, action: Dict[str, Any], ctx: RuleContext) -> ActionResult:
        """Execute a single action - canonical unversioned implementation"""
        action_type = action.get("type")
        params = action.get("params", {})
        
        if not action_type:
            if action:
                action_type = list(action.keys())[0]
                params = action[action_type]
        
        # Dispatch table - unversioned canonical functions
        dispatch = {
            "ffmpeg_remux": self._action_remux,
            "move": self._action_move,
            "copy": self._action_copy,
            "index_asset": self._action_index,
            "proxy": self._action_proxy,
            "make_proxies_if": self._action_proxy,
            "transcode_preset": self._action_transcode,
            "tag": self._action_tag,
        }
        
        handler = dispatch.get(action_type)
        if not handler:
            logger.warning(f"Unknown action type: {action_type}")
            return ActionResult(success=False, error=f"Unknown action: {action_type}")
            
        return await handler(params, ctx)
    
    async def _action_remux(self, params: Dict[str, Any], ctx: RuleContext) -> ActionResult:
        """Remux action - awaits job completion and updates ctx.active"""
        source = ctx.active.path
        if not source.exists():
            return ActionResult(success=False, error=f"Source not found: {source}")
        
        job_id = self._generate_job_id("remux")
        asset_id = ctx.vars.get("asset_id", "")
        container = params.get("container", "mov")
        
        # Enqueue job
        await self._enqueue_job(job_id, "ffmpeg_remux", asset_id, {
            "input_path": str(source),
            "output_format": container,
            "faststart": params.get("faststart", True)
        })
        
        # Publish to NATS
        if self.nats:
            await self.nats.publish_job("remux", {
                "id": job_id,
                "input_path": str(source),
                "output_format": container,
                "faststart": params.get("faststart", True)
            })
        
        logger.info(f"Awaiting remux job {job_id}")
        
        # CRITICAL: Await job completion
        result = await self._await_job_completion(job_id, timeout=600)
        
        if not result.get("success"):
            return ActionResult(success=False, error=f"Remux job {job_id} failed")
            
        output_path = result.get("output_path")
        if not output_path:
            output_path = str(source.with_suffix(f".{container}"))
            
        out_path = Path(output_path)
        if not out_path.exists():
            logger.error(f"Remux output not found: {out_path}")
            return ActionResult(success=False, error=f"Output not found: {out_path}")
        
        # Update context with new artifact
        new_artifact = Artifact(path=out_path, ext=out_path.suffix)
        ctx.update_active(new_artifact)
        
        logger.info(f"Remux completed: {source} → {out_path}")
        return ActionResult(primary_output_path=out_path)
    
    async def _action_move(self, params: Dict[str, Any], ctx: RuleContext) -> ActionResult:
        """Move action - uses ctx.active and updates it after atomic move"""
        source = ctx.active.path
        if not source.exists():
            return ActionResult(success=False, error=f"Source not found: {source}")
        
        target_template = params.get("target") or params.get("dest")
        if not target_template:
            return ActionResult(success=False, error="No target specified")
        
        # Build target using template expansion from ACTIVE artifact
        target_path = build_target_path(target_template, ctx)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Atomic move
            os.replace(str(source), str(target_path))
            
            # Update context with moved artifact
            moved = Artifact(path=target_path, ext=target_path.suffix, mime=ctx.active.mime)
            ctx.update_active(moved)
            
            # Emit move event if we have an asset_id
            asset_id = ctx.vars.get("asset_id")
            if asset_id:
                try:
                    from app.api.services.asset_events import AssetEventService
                    await AssetEventService.emit_move_completed(
                        asset_id, str(source), str(target_path)
                    )
                except Exception as e:
                    logger.debug(f"Could not emit move event: {e}")
            
            logger.info(f"Moved: {source} → {target_path}")
            return ActionResult(primary_output_path=target_path)
            
        except Exception as e:
            logger.error(f"Failed to move file: {e}")
            return ActionResult(success=False, error=str(e))
    
    async def _action_copy(self, params: Dict[str, Any], ctx: RuleContext) -> ActionResult:
        """Copy action - uses ctx.active"""
        import shutil
        source = ctx.active.path
        
        if not source.exists():
            return ActionResult(success=False, error=f"Source not found: {source}")
        
        target_template = params.get("target") or params.get("dest")
        if not target_template:
            return ActionResult(success=False, error="No target specified")
        
        target_path = build_target_path(target_template, ctx)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.copy2(str(source), str(target_path))
            logger.info(f"Copied: {source} → {target_path}")
            # Note: Copy doesn't update ctx.active - original remains active
            return ActionResult(primary_output_path=target_path)
        except Exception as e:
            logger.error(f"Failed to copy file: {e}")
            return ActionResult(success=False, error=str(e))
    
    async def _action_index(self, params: Dict[str, Any], ctx: RuleContext) -> ActionResult:
        """Index asset in database"""
        if self.nats:
            job_id = self._generate_job_id("index")
            await self.nats.publish_job("index", {
                "id": job_id,
                "input_path": str(ctx.active.path)
            })
            logger.info(f"Queued index job {job_id}")
        return ActionResult(success=True)
    
    async def _action_proxy(self, params: Dict[str, Any], ctx: RuleContext) -> ActionResult:
        """Proxy action - awaits completion and returns output path"""
        source = ctx.active.path
        if not source.exists():
            return ActionResult(success=False, error=f"Source not found: {source}")
        
        # Check duration condition if specified
        if_duration_gt = params.get("if_duration_gt", 0)
        min_duration_sec = params.get("min_duration_sec", if_duration_gt)  # Support both param names
        
        if min_duration_sec > 0:
            # Get duration from context metadata
            duration = ctx.active.meta.get("duration_sec", 0)
            if duration == 0:
                # Try to get duration from asset data if available
                duration = ctx.vars.get("duration_sec", 0)
            
            # If we still don't have duration, try to get from database
            if duration == 0:
                asset_id = ctx.vars.get("asset_id", "")
                if asset_id:
                    conn = await aiosqlite.connect("/data/db/streamops.db")
                    cursor = await conn.execute(
                        "SELECT duration_s FROM so_assets WHERE id = ?",
                        (asset_id,)
                    )
                    row = await cursor.fetchone()
                    if row:
                        duration = row[0] or 0
                    await conn.close()
            
            # Skip if duration is known and less than threshold
            if duration > 0 and duration <= min_duration_sec:
                logger.info(f"Skipping proxy - duration {duration}s <= {min_duration_sec}s")
                return ActionResult(success=True)
            
            # Also skip if we couldn't determine duration at all (safety check)
            if duration == 0:
                logger.warning(f"Could not determine duration for proxy check, skipping proxy creation")
                return ActionResult(success=True)
        
        # Check extension conditions
        conditions = params.get("if", {})
        if "ext_in" in conditions:
            allowed_exts = conditions["ext_in"]
            if not isinstance(allowed_exts, list):
                allowed_exts = [allowed_exts]
            
            source_ext = source.suffix.lower().lstrip('.')
            if source_ext not in allowed_exts:
                logger.info(f"Skipping proxy - extension {source_ext} not in {allowed_exts}")
                return ActionResult(success=True)
        
        job_id = self._generate_job_id("proxy")
        
        # Pass all proxy parameters from the rule to the job
        job_params = {
            "input_path": str(source),
            "profile": params.get("codec"),  # No default - let proxy job decide
            "resolution": params.get("resolution"),  # No default - let proxy job decide
        }
        
        # Add optional parameters if specified in rule
        if "bitrate" in params:
            job_params["bitrate"] = params["bitrate"]
        if "use_gpu" in params:
            job_params["use_gpu"] = params["use_gpu"]
        if "timecode_start" in params:
            job_params["timecode_start"] = params["timecode_start"]
        if "audio_channels" in params:
            job_params["audio_channels"] = params["audio_channels"]
        
        # Enqueue job
        await self._enqueue_job(job_id, "proxy", ctx.vars.get("asset_id", ""), job_params)
        
        if self.nats:
            await self.nats.publish_job("proxy", {
                "id": job_id,
                **job_params
            })
        
        logger.info(f"Awaiting proxy job {job_id}")
        
        # CRITICAL: Await job completion
        result = await self._await_job_completion(job_id, timeout=3600)
        
        if not result.get("success"):
            return ActionResult(success=False, error=f"Proxy job {job_id} failed")
        
        output_path = result.get("output_path")
        if output_path:
            out_path = Path(output_path)
            logger.info(f"Proxy completed: {source} → {out_path}")
            # Note: Proxy doesn't update ctx.active unless explicitly configured
            return ActionResult(primary_output_path=out_path)
        
        return ActionResult(success=True)
    
    async def _action_transcode(self, params: Dict[str, Any], ctx: RuleContext) -> ActionResult:
        """Transcode with preset"""
        if self.nats:
            job_id = self._generate_job_id("transcode")
            await self.nats.publish_job("transcode", {
                "id": job_id,
                "input_path": str(ctx.active.path),
                "preset": params.get("preset", "web_1080p")
            })
            logger.info(f"Queued transcode job {job_id}")
        return ActionResult(success=True)
    
    async def _action_tag(self, params: Dict[str, Any], ctx: RuleContext) -> ActionResult:
        """Add tags to asset"""
        tags = params.get("tags", [])
        if not tags:
            return ActionResult(success=True)
        
        asset_id = ctx.vars.get("asset_id")
        if not asset_id:
            logger.warning("No asset_id in context, cannot tag")
            return ActionResult(success=False, error="No asset_id")
        
        try:
            conn = await aiosqlite.connect("/data/db/streamops.db")
            existing = await conn.execute_fetchone(
                "SELECT tags FROM so_assets WHERE id = ?", (asset_id,)
            )
            
            if existing:
                current_tags = json.loads(existing[0]) if existing[0] else []
                new_tags = list(set(current_tags + tags))
                
                await conn.execute(
                    "UPDATE so_assets SET tags = ? WHERE id = ?",
                    (json.dumps(new_tags), asset_id)
                )
                await conn.commit()
                logger.info(f"Added tags {tags} to asset {asset_id}")
            
            await conn.close()
            return ActionResult(success=True)
            
        except Exception as e:
            logger.error(f"Failed to add tags: {e}")
            return ActionResult(success=False, error=str(e))
    
    # Helper methods
    
    async def _enqueue_job(self, job_id: str, job_type: str, asset_id: str, payload: Dict[str, Any], 
                          deferred: bool = False, blocked_reason: str = None):
        """Enqueue job in database, optionally as deferred"""
        conn = await aiosqlite.connect("/data/db/streamops.db")
        
        # Determine initial state and next_run_at
        if deferred:
            state = 'deferred'
            # Set next_run_at based on quiet period from payload
            quiet_period = payload.get('quiet_period_sec', 45)
            next_run_at = (datetime.utcnow() + timedelta(seconds=quiet_period)).isoformat()
        else:
            state = 'queued'
            next_run_at = None
        
        await conn.execute("""
            INSERT INTO so_jobs (id, type, asset_id, payload_json, state, 
                               blocked_reason, next_run_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            job_type,
            asset_id,
            json.dumps(payload),
            state,
            blocked_reason,
            next_run_at,
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat()
        ))
        await conn.commit()
        await conn.close()
    
    async def _create_deferred_jobs_for_rule(self, rule: 'Rule', event_data: Dict[str, Any]):
        """Create deferred jobs in database for a rule's actions"""
        logger.info(f"Starting _create_deferred_jobs_for_rule for rule {rule.name}")
        asset_id = event_data.get('asset_id', '')
        
        # Get asset duration for proxy condition checking
        duration_sec = event_data.get('duration_sec', 0)
        logger.info(f"Asset ID: {asset_id}, Duration from event: {duration_sec}s")
        if duration_sec == 0 and asset_id:
            # Try to get duration from database
            conn = await aiosqlite.connect("/data/db/streamops.db")
            cursor = await conn.execute(
                "SELECT duration_s FROM so_assets WHERE id = ?",
                (asset_id,)
            )
            row = await cursor.fetchone()
            if row:
                duration_sec = row[0] or 0
            await conn.close()
        
        # Create a deferred job for each action in the rule
        logger.info(f"Processing {len(rule.do_actions)} actions for deferred job creation")
        jobs_created = 0
        for action in rule.do_actions:
            action_type = action.get("type")
            params = action.get("params", {})
            logger.info(f"Processing action: {action_type}")
            
            # Skip non-job actions
            if action_type not in ['ffmpeg_remux', 'proxy', 'transcode_preset']:
                logger.info(f"Skipping non-job action: {action_type}")
                continue
            
            # Check proxy duration condition
            if action_type == 'proxy':
                if_duration_gt = params.get('if_duration_gt', 0)
                min_duration_sec = params.get('min_duration_sec', if_duration_gt)
                if min_duration_sec > 0:
                    # Duration check - if we don't know duration or it's too short, skip
                    if duration_sec <= 0:
                        logger.info(f"Skipping proxy job creation - duration unknown or 0")
                        continue
                    elif duration_sec <= min_duration_sec:
                        logger.info(f"Skipping proxy job creation - duration {duration_sec}s <= {min_duration_sec}s")
                        continue
            
            # Map action type to job type
            job_type_map = {
                'ffmpeg_remux': 'remux',
                'proxy': 'proxy', 
                'transcode_preset': 'transcode'
            }
            job_type = job_type_map.get(action_type, action_type)
            
            # Create the deferred job
            job_id = self._generate_job_id(job_type)
            payload = params.copy()
            payload['input_path'] = event_data.get('path', '')
            payload['quiet_period_sec'] = rule.quiet_period_sec
            payload['duration_sec'] = duration_sec  # Pass duration to job
            
            # Add extra params for remux
            if action_type == 'ffmpeg_remux':
                payload['output_format'] = params.get('container', 'mov')
                payload['faststart'] = params.get('faststart', True)
            
            # Create deferred job with next_run_at set
            await self._enqueue_job(
                job_id, 
                job_type,  # Use mapped job type
                asset_id, 
                payload,
                deferred=True,
                blocked_reason=f"Waiting for {rule.quiet_period_sec}s quiet period"
            )
            jobs_created += 1
            logger.info(f"Created deferred job {job_id} for {action_type} (job type: {job_type}), will run after quiet period")
        
        logger.info(f"Created {jobs_created} deferred jobs for rule {rule.name}")
    
    async def _activate_deferred_jobs(self):
        """Activate all deferred jobs that are ready to run"""
        conn = await aiosqlite.connect("/data/db/streamops.db")
        conn.row_factory = aiosqlite.Row
        
        # Get all deferred jobs that are ready
        cursor = await conn.execute("""
            SELECT id, type, asset_id, payload_json
            FROM so_jobs 
            WHERE state = 'deferred' 
            AND (next_run_at IS NULL OR next_run_at <= ?)
        """, (datetime.utcnow().isoformat(),))
        
        jobs = await cursor.fetchall()
        
        # Update all deferred jobs to queued state
        await conn.execute("""
            UPDATE so_jobs 
            SET state = 'queued', 
                blocked_reason = NULL,
                updated_at = ?
            WHERE state = 'deferred' 
            AND (next_run_at IS NULL OR next_run_at <= ?)
        """, (
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat()
        ))
        
        await conn.commit()
        await conn.close()
        
        # Publish each job to NATS for processing
        if self.nats and jobs:
            for job in jobs:
                payload = json.loads(job['payload_json']) if job['payload_json'] else {}
                payload['id'] = job['id']
                payload['asset_id'] = job['asset_id']
                
                await self.nats.publish_job(job['type'], payload)
                logger.info(f"Published deferred job {job['id']} of type {job['type']} to NATS")
        
        return len(jobs)
    
    async def _await_job_completion(self, job_id: str, timeout: int = 600) -> Dict[str, Any]:
        """Await job completion by polling database"""
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            conn = await aiosqlite.connect("/data/db/streamops.db")
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT state, result_json, error FROM so_jobs WHERE id = ?",
                (job_id,)
            )
            row = await cursor.fetchone()
            await conn.close()
            
            if row:
                if row["state"] == "completed":
                    result = json.loads(row["result_json"]) if row["result_json"] else {}
                    result["success"] = True
                    logger.info(f"Job {job_id} completed with result: {result}")
                    return result
                elif row["state"] == "failed":
                    logger.error(f"Job {job_id} failed: {row['error']}")
                    return {"success": False, "error": row["error"]}
            
            await asyncio.sleep(2)
        
        logger.error(f"Job {job_id} timed out after {timeout}s")
        return {"success": False, "error": f"Timeout after {timeout}s"}
    
    def _generate_job_id(self, prefix: str) -> str:
        """Generate unique job ID"""
        from datetime import datetime
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:-3]
        return f"{prefix}_{timestamp}"
    
    # Legacy guards - prevent accidental usage
    def execute_action_v1(self, *args, **kwargs):
        raise RuntimeError("execute_action_v1 is removed. Use execute_action.")
    
    def execute_action_v2(self, *args, **kwargs):
        raise RuntimeError("execute_action_v2 is removed. Use execute_action.")
    
    def _action_remux_v1(self, *args, **kwargs):
        raise RuntimeError("_action_remux_v1 is removed. Use _action_remux.")
    
    def _action_remux_v2(self, *args, **kwargs):
        raise RuntimeError("_action_remux_v2 is removed. Use _action_remux.")


class Rule:
    """Rule definition"""
    
    def __init__(self, id: str, name: str, priority: int, 
                 when_conditions: Dict[str, Any], do_actions: List[Dict[str, Any]],
                 quiet_period_sec: int = 0, guardrails: Dict[str, Any] = None):
        self.id = id
        self.name = name
        self.priority = priority
        self.when_conditions = when_conditions
        self.do_actions = do_actions
        self.quiet_period_sec = quiet_period_sec
        self.guardrails = guardrails or {}
        
    async def matches(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Check if rule matches event"""
        if self.when_conditions.get("event") != event_type:
            return False
            
        conditions = self.when_conditions.get("conditions", {})
        for field, expected_value in conditions.items():
            # Handle nested field access with dot notation
            actual_value = self._get_nested_value(event_data, field)
            
            if field == "path":
                if not self._path_matches(actual_value, expected_value):
                    return False
            elif actual_value != expected_value:
                return False
                
        return True
    
    def _get_nested_value(self, data: Dict[str, Any], field: str) -> Any:
        """Get value from nested dict using dot notation"""
        parts = field.split('.')
        value = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value
    
    def _path_matches(self, path: str, pattern: str) -> bool:
        """Check if path matches pattern"""
        if not path:
            return False
        return fnmatch(path, pattern)
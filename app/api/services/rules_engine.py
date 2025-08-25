import os
import re
import json
import asyncio
import logging
import psutil
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
from fnmatch import fnmatch
from pydantic import ValidationError

from app.api.schemas.rules import (
    RuleCondition, RuleAction, RuleGuardrail, RuleResponse, 
    RuleExecution, RuleConditionOperator, RuleStatus
)
from app.api.db.database import get_db
from app.api.services.nats_service import NATSService
from app.api.services.obs_service import OBSService
from app.api.services.config_service import ConfigService

logger = logging.getLogger(__name__)


class RulesExecutionError(Exception):
    """Custom exception for rules execution errors"""
    pass


class GuardrailViolationError(Exception):
    """Custom exception for guardrail violations"""
    pass


class RulesEngine:
    """
    Production-ready rules evaluation engine for StreamOps.
    
    Handles rule evaluation against asset metadata and system state,
    executes configured actions through job queue integration,
    enforces guardrails, and maintains comprehensive audit logging.
    """
    
    def __init__(self, nats_service: Optional[NATSService] = None, 
                 obs_service: Optional[OBSService] = None,
                 config_service: Optional[ConfigService] = None):
        self.nats = nats_service
        self.obs = obs_service
        self.config = config_service
        self.enabled = True
        self._lock = asyncio.Lock()
        
        # Cache for frequently accessed data
        self._system_state_cache = {}
        self._cache_ttl = 30  # seconds
        self._last_cache_update = 0
        
        # Execution statistics
        self.stats = {
            'total_evaluations': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'guardrail_violations': 0
        }
    
    async def evaluate_rules_for_event(self, event_type: str, event_data: Dict[str, Any]) -> List[RuleExecution]:
        """
        Evaluate all active rules against an event and execute matching ones.
        
        Args:
            event_type: Type of event (e.g., 'file.closed', 'asset.created')
            event_data: Event data including asset metadata, file paths, etc.
            
        Returns:
            List of rule executions with results
        """
        if not self.enabled:
            logger.debug("Rules engine is disabled, skipping evaluation")
            return []
        
        self.stats['total_evaluations'] += 1
        executions = []
        
        try:
            # Load active rules from database
            rules = await self._load_active_rules()
            logger.debug(f"Evaluating {len(rules)} active rules for event {event_type}")
            
            # Enrich event data with system context
            enriched_data = await self._enrich_event_data(event_data)
            
            # Sort rules by priority (higher priority first)
            rules.sort(key=lambda r: r.priority, reverse=True)
            
            for rule in rules:
                try:
                    execution = await self._evaluate_and_execute_rule(
                        rule, event_type, enriched_data
                    )
                    if execution:
                        executions.append(execution)
                        
                        # Log execution for audit trail
                        await self._log_rule_execution(rule, execution)
                        
                except Exception as e:
                    logger.error(f"Error processing rule '{rule.name}': {e}")
                    self.stats['failed_executions'] += 1
                    
                    # Create failed execution record
                    failed_execution = RuleExecution(
                        rule_id=rule.id,
                        asset_id=event_data.get('asset_id'),
                        session_id=event_data.get('session_id'),
                        success=False,
                        actions_performed=[],
                        error_message=str(e),
                        execution_time=0.0,
                        executed_at=datetime.utcnow()
                    )
                    executions.append(failed_execution)
                    await self._log_rule_execution(rule, failed_execution)
            
        except Exception as e:
            logger.error(f"Critical error in rules evaluation: {e}")
        
        logger.info(f"Completed rule evaluation for {event_type}: "
                   f"{len(executions)} executions")
        return executions
    
    async def test_rule(self, rule: RuleResponse, test_data: Dict[str, Any], 
                       dry_run: bool = True) -> RuleExecution:
        """
        Test a rule against provided data without executing actions.
        
        Args:
            rule: Rule to test
            test_data: Mock data for testing
            dry_run: Whether to perform a dry run (default: True)
            
        Returns:
            Rule execution result
        """
        start_time = datetime.utcnow()
        
        try:
            # Enrich test data
            enriched_data = await self._enrich_event_data(test_data)
            
            # Check if rule matches
            matches = await self._evaluate_rule_conditions(rule, enriched_data)
            
            if not matches:
                return RuleExecution(
                    rule_id=rule.id,
                    asset_id=test_data.get('asset_id'),
                    session_id=test_data.get('session_id'),
                    success=False,
                    actions_performed=[],
                    error_message="Rule conditions not met",
                    execution_time=0.0,
                    executed_at=start_time
                )
            
            # Check guardrails
            guardrail_violations = await self._check_guardrails(rule.guardrails)
            if guardrail_violations:
                return RuleExecution(
                    rule_id=rule.id,
                    asset_id=test_data.get('asset_id'),
                    session_id=test_data.get('session_id'),
                    success=False,
                    actions_performed=[],
                    error_message=f"Guardrail violations: {', '.join(guardrail_violations)}",
                    execution_time=0.0,
                    executed_at=start_time
                )
            
            if dry_run:
                # Simulate action execution
                simulated_actions = [action.action_type for action in rule.actions]
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                return RuleExecution(
                    rule_id=rule.id,
                    asset_id=test_data.get('asset_id'),
                    session_id=test_data.get('session_id'),
                    success=True,
                    actions_performed=simulated_actions,
                    error_message=None,
                    execution_time=execution_time,
                    executed_at=start_time
                )
            else:
                # Execute actions for real
                return await self._execute_rule_actions(rule, enriched_data, start_time)
            
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Error testing rule '{rule.name}': {e}")
            
            return RuleExecution(
                rule_id=rule.id,
                asset_id=test_data.get('asset_id'),
                session_id=test_data.get('session_id'),
                success=False,
                actions_performed=[],
                error_message=str(e),
                execution_time=execution_time,
                executed_at=start_time
            )
    
    async def _evaluate_and_execute_rule(self, rule: RuleResponse, event_type: str, 
                                       event_data: Dict[str, Any]) -> Optional[RuleExecution]:
        """Evaluate a single rule and execute if it matches"""
        start_time = datetime.utcnow()
        
        try:
            # Check if rule matches the event
            if not await self._evaluate_rule_conditions(rule, event_data):
                logger.debug(f"Rule '{rule.name}' conditions not met")
                return None
            
            logger.info(f"Rule '{rule.name}' matched for event {event_type}")
            
            # Check guardrails before execution
            guardrail_violations = await self._check_guardrails(rule.guardrails)
            if guardrail_violations:
                self.stats['guardrail_violations'] += 1
                raise GuardrailViolationError(
                    f"Guardrail violations prevented execution: {', '.join(guardrail_violations)}"
                )
            
            # Execute rule actions
            return await self._execute_rule_actions(rule, event_data, start_time)
            
        except GuardrailViolationError as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            logger.warning(f"Rule '{rule.name}' blocked by guardrails: {e}")
            
            return RuleExecution(
                rule_id=rule.id,
                asset_id=event_data.get('asset_id'),
                session_id=event_data.get('session_id'),
                success=False,
                actions_performed=[],
                error_message=str(e),
                execution_time=execution_time,
                executed_at=start_time
            )
    
    async def _evaluate_rule_conditions(self, rule: RuleResponse, 
                                      event_data: Dict[str, Any]) -> bool:
        """
        Evaluate rule conditions with support for complex AND/OR logic.
        
        The conditions are stored in the database as JSON and can contain:
        - Simple field comparisons
        - Complex conditions with operators ($gte, $lte, etc.)
        - Nested AND/OR logic
        """
        try:
            # Handle different condition formats
            for condition in rule.conditions:
                if not await self._evaluate_single_condition(condition, event_data):
                    return False  # AND logic: all conditions must match
            
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating conditions for rule '{rule.name}': {e}")
            return False
    
    async def _evaluate_single_condition(self, condition: RuleCondition, 
                                       event_data: Dict[str, Any]) -> bool:
        """Evaluate a single condition against event data"""
        field_value = self._get_nested_value(event_data, condition.field)
        expected_value = condition.value
        operator = condition.operator
        
        try:
            if operator == RuleConditionOperator.equals:
                return field_value == expected_value
            
            elif operator == RuleConditionOperator.not_equals:
                return field_value != expected_value
            
            elif operator == RuleConditionOperator.contains:
                return str(expected_value) in str(field_value) if field_value else False
            
            elif operator == RuleConditionOperator.not_contains:
                return str(expected_value) not in str(field_value) if field_value else True
            
            elif operator == RuleConditionOperator.starts_with:
                return str(field_value).startswith(str(expected_value)) if field_value else False
            
            elif operator == RuleConditionOperator.ends_with:
                return str(field_value).endswith(str(expected_value)) if field_value else False
            
            elif operator == RuleConditionOperator.greater_than:
                return (field_value or 0) > expected_value
            
            elif operator == RuleConditionOperator.less_than:
                return (field_value or 0) < expected_value
            
            elif operator == RuleConditionOperator.regex_match:
                return bool(re.match(str(expected_value), str(field_value))) if field_value else False
            
            elif operator == RuleConditionOperator.file_exists:
                file_path = self._substitute_variables(str(expected_value), event_data)
                return Path(file_path).exists()
            
            elif operator == RuleConditionOperator.has_tag:
                tags = event_data.get('tags', [])
                return str(expected_value) in tags
            
            else:
                logger.warning(f"Unknown condition operator: {operator}")
                return False
                
        except Exception as e:
            logger.error(f"Error evaluating condition {condition.field} {operator} {expected_value}: {e}")
            return False
    
    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Any:
        """Get value from nested dictionary using dot notation"""
        keys = key.split('.')
        value = data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value
    
    async def _check_guardrails(self, guardrails: List[RuleGuardrail]) -> List[str]:
        """
        Check all guardrails and return list of violations.
        
        Returns:
            List of guardrail violation messages (empty if all pass)
        """
        violations = []
        
        for guardrail in guardrails:
            try:
                if guardrail.guardrail_type == "pause_if_recording":
                    if await self._is_recording_active():
                        violations.append("Recording is active")
                
                elif guardrail.guardrail_type == "pause_if_gpu_pct_above":
                    gpu_usage = await self._get_gpu_usage()
                    if gpu_usage > guardrail.threshold:
                        violations.append(f"GPU usage {gpu_usage}% above threshold {guardrail.threshold}%")
                
                elif guardrail.guardrail_type == "pause_if_cpu_pct_above":
                    cpu_usage = await self._get_cpu_usage()
                    if cpu_usage > guardrail.threshold:
                        violations.append(f"CPU usage {cpu_usage}% above threshold {guardrail.threshold}%")
                
            except Exception as e:
                logger.error(f"Error checking guardrail {guardrail.guardrail_type}: {e}")
                violations.append(f"Guardrail check failed: {e}")
        
        return violations
    
    async def _execute_rule_actions(self, rule: RuleResponse, event_data: Dict[str, Any],
                                  start_time: datetime) -> RuleExecution:
        """Execute all actions for a rule"""
        executed_actions = []
        
        try:
            for action in rule.actions:
                await self._execute_single_action(action, event_data)
                executed_actions.append(action.action_type)
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            self.stats['successful_executions'] += 1
            
            return RuleExecution(
                rule_id=rule.id,
                asset_id=event_data.get('asset_id'),
                session_id=event_data.get('session_id'),
                success=True,
                actions_performed=executed_actions,
                error_message=None,
                execution_time=execution_time,
                executed_at=start_time
            )
            
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Error executing actions for rule '{rule.name}': {e}")
            self.stats['failed_executions'] += 1
            
            return RuleExecution(
                rule_id=rule.id,
                asset_id=event_data.get('asset_id'),
                session_id=event_data.get('session_id'),
                success=False,
                actions_performed=executed_actions,
                error_message=str(e),
                execution_time=execution_time,
                executed_at=start_time
            )
    
    async def _execute_single_action(self, action: RuleAction, context: Dict[str, Any]):
        """Execute a single action with proper error handling and logging"""
        action_type = action.action_type
        params = self._substitute_variables(action.params, context)
        
        logger.info(f"Executing action: {action_type}")
        
        try:
            if action_type == "ffmpeg_remux":
                await self._action_remux(params, context)
            
            elif action_type == "move":
                await self._action_move(params, context)
            
            elif action_type == "copy":
                await self._action_copy(params, context)
            
            elif action_type == "index_asset":
                await self._action_index_asset(params, context)
            
            elif action_type == "thumbs":
                await self._action_generate_thumbnails(params, context)
            
            elif action_type == "proxy":
                await self._action_create_proxy(params, context)
            
            elif action_type == "transcode_preset":
                await self._action_transcode(params, context)
            
            elif action_type == "tag":
                await self._action_add_tags(params, context)
            
            elif action_type == "overlay_update":
                await self._action_update_overlay(params, context)
            
            else:
                raise RulesExecutionError(f"Unknown action type: {action_type}")
                
        except Exception as e:
            logger.error(f"Failed to execute action {action_type}: {e}")
            raise RulesExecutionError(f"Action {action_type} failed: {e}")
    
    # Action implementations
    
    async def _action_remux(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute FFmpeg remux job"""
        if not self.nats:
            raise RulesExecutionError("NATS service not available for job queuing")
        
        input_path = context.get('filepath', context.get('path'))
        if not input_path:
            raise RulesExecutionError("No input file path provided")
        
        job_data = {
            "id": self._generate_job_id("remux"),
            "input_path": input_path,
            "output_format": params.get("container", "mov"),
            "faststart": params.get("faststart", True),
            "asset_id": context.get("asset_id")
        }
        
        await self.nats.publish_job("remux", job_data)
        logger.info(f"Queued remux job: {job_data['id']}")
    
    async def _action_move(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute file move operation"""
        import shutil
        
        source_path = Path(context.get('filepath', context.get('path')))
        dest_pattern = params.get("dest")
        
        if not source_path or not source_path.exists():
            raise RulesExecutionError(f"Source file not found: {source_path}")
        
        if not dest_pattern:
            raise RulesExecutionError("Destination pattern not provided")
        
        # Expand destination pattern with variables
        dest_path = Path(self._expand_path_pattern(dest_pattern, context))
        
        # Create destination directory
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure we don't overwrite existing files
        if dest_path.exists():
            counter = 1
            base_name = dest_path.stem
            extension = dest_path.suffix
            while dest_path.exists():
                dest_path = dest_path.parent / f"{base_name}_{counter}{extension}"
                counter += 1
        
        # Perform the move
        shutil.move(str(source_path), str(dest_path))
        logger.info(f"Moved file: {source_path} -> {dest_path}")
        
        # Update context for subsequent actions
        context["filepath"] = str(dest_path)
        context["path"] = str(dest_path)
    
    async def _action_copy(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Execute file copy operation"""
        import shutil
        
        source_path = Path(context.get('filepath', context.get('path')))
        dest_pattern = params.get("dest")
        
        if not source_path or not source_path.exists():
            raise RulesExecutionError(f"Source file not found: {source_path}")
        
        if not dest_pattern:
            raise RulesExecutionError("Destination pattern not provided")
        
        # Expand destination pattern
        dest_path = Path(self._expand_path_pattern(dest_pattern, context))
        
        # Create destination directory
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Perform the copy
        shutil.copy2(str(source_path), str(dest_path))
        logger.info(f"Copied file: {source_path} -> {dest_path}")
    
    async def _action_index_asset(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Queue asset indexing job"""
        if not self.nats:
            raise RulesExecutionError("NATS service not available for job queuing")
        
        input_path = context.get('filepath', context.get('path'))
        if not input_path:
            raise RulesExecutionError("No input file path provided")
        
        job_data = {
            "id": self._generate_job_id("index"),
            "input_path": input_path,
            "asset_id": context.get("asset_id")
        }
        
        await self.nats.publish_job("index", job_data)
        logger.info(f"Queued index job: {job_data['id']}")
    
    async def _action_generate_thumbnails(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Queue thumbnail generation job"""
        if not self.nats:
            raise RulesExecutionError("NATS service not available for job queuing")
        
        job_data = {
            "id": self._generate_job_id("thumbnail"),
            "input_path": context.get('filepath', context.get('path')),
            "asset_id": context.get("asset_id"),
            "sprite_columns": params.get("sprite_columns", 5),
            "interval_sec": params.get("interval_sec", 20)
        }
        
        await self.nats.publish_job("thumbnail", job_data)
        logger.info(f"Queued thumbnail job: {job_data['id']}")
    
    async def _action_create_proxy(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Queue proxy creation job with conditional logic"""
        if not self.nats:
            raise RulesExecutionError("NATS service not available for job queuing")
        
        # Check minimum duration condition
        min_duration = params.get("min_duration_sec", 900)
        duration = context.get("duration_sec", 0)
        
        if duration and duration < min_duration:
            logger.info(f"Skipping proxy creation - duration {duration}s < {min_duration}s")
            return
        
        job_data = {
            "id": self._generate_job_id("proxy"),
            "input_path": context.get('filepath', context.get('path')),
            "codec": params.get("codec", "dnxhr_lb"),
            "asset_id": context.get("asset_id")
        }
        
        await self.nats.publish_job("proxy", job_data)
        logger.info(f"Queued proxy job: {job_data['id']}")
    
    async def _action_transcode(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Queue transcode job with preset"""
        if not self.nats:
            raise RulesExecutionError("NATS service not available for job queuing")
        
        job_data = {
            "id": self._generate_job_id("transcode"),
            "input_path": context.get('filepath', context.get('path')),
            "preset": params.get("preset", "web_1080p"),
            "asset_id": context.get("asset_id")
        }
        
        await self.nats.publish_job("transcode", job_data)
        logger.info(f"Queued transcode job: {job_data['id']}")
    
    async def _action_add_tags(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Add tags to asset in database"""
        asset_id = context.get("asset_id")
        tags = params.get("tags", [])
        
        if not asset_id:
            raise RulesExecutionError("Asset ID not provided for tagging")
        
        if not tags:
            logger.warning("No tags provided for tagging action")
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
            
            # Merge tags and remove duplicates
            all_tags = list(set(existing_tags + tags))
            
            # Update asset
            await db.execute(
                "UPDATE so_assets SET tags_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(all_tags), asset_id)
            )
            await db.commit()
            
            logger.info(f"Added tags {tags} to asset {asset_id}")
            
        except Exception as e:
            raise RulesExecutionError(f"Failed to add tags: {e}")
    
    async def _action_update_overlay(self, params: Dict[str, Any], context: Dict[str, Any]):
        """Update overlay content"""
        overlay_id = params.get("overlay_id")
        content = params.get("content", {})
        
        if not overlay_id:
            raise RulesExecutionError("Overlay ID not provided")
        
        try:
            db = await get_db()
            
            # Update overlay manifest
            await db.execute(
                "UPDATE so_overlays SET manifest_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(content), overlay_id)
            )
            await db.commit()
            
            logger.info(f"Updated overlay {overlay_id}")
            
        except Exception as e:
            raise RulesExecutionError(f"Failed to update overlay: {e}")
    
    # Helper methods
    
    async def _load_active_rules(self) -> List[RuleResponse]:
        """Load all active rules from database"""
        try:
            db = await get_db()
            async with db.execute(
                """
                SELECT id, name, enabled, priority, when_json, do_json, 
                       created_at, updated_at
                FROM so_rules 
                WHERE enabled = 1 
                ORDER BY priority DESC, created_at ASC
                """
            ) as cursor:
                rows = await cursor.fetchall()
            
            rules = []
            for row in rows:
                try:
                    when_data = json.loads(row[4])
                    do_data = json.loads(row[5])
                    
                    # Convert to Pydantic models
                    conditions = [RuleCondition(**cond) for cond in when_data.get('conditions', [])]
                    actions = [RuleAction(**action) for action in do_data.get('actions', [])]
                    guardrails = [RuleGuardrail(**guard) for guard in do_data.get('guardrails', [])]
                    
                    rule = RuleResponse(
                        id=row[0],
                        name=row[1],
                        enabled=bool(row[2]),
                        priority=row[3],
                        conditions=conditions,
                        actions=actions,
                        guardrails=guardrails,
                        status=RuleStatus.active,
                        tags=[],
                        created_at=datetime.fromisoformat(row[6]),
                        updated_at=datetime.fromisoformat(row[7])
                    )
                    rules.append(rule)
                    
                except ValidationError as e:
                    logger.error(f"Invalid rule data for rule {row[0]}: {e}")
                    continue
            
            return rules
            
        except Exception as e:
            logger.error(f"Failed to load rules: {e}")
            return []
    
    async def _enrich_event_data(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich event data with additional context"""
        enriched = event_data.copy()
        
        # Add timestamp if not present
        if 'timestamp' not in enriched:
            enriched['timestamp'] = datetime.utcnow().isoformat()
        
        # Add system state
        enriched.update(await self._get_system_state())
        
        # Add asset metadata if asset_id provided
        asset_id = enriched.get('asset_id')
        if asset_id:
            try:
                asset_data = await self._get_asset_metadata(asset_id)
                enriched.update(asset_data)
            except Exception as e:
                logger.warning(f"Failed to enrich with asset metadata: {e}")
        
        return enriched
    
    async def _get_system_state(self) -> Dict[str, Any]:
        """Get current system state with caching"""
        current_time = datetime.utcnow().timestamp()
        
        if (current_time - self._last_cache_update) < self._cache_ttl:
            return self._system_state_cache
        
        try:
            state = {
                'cpu_percent': await self._get_cpu_usage(),
                'gpu_percent': await self._get_gpu_usage(),
                'is_recording': await self._is_recording_active(),
                'memory_available_gb': self._get_available_memory(),
                'disk_free_gb': self._get_disk_free_space()
            }
            
            self._system_state_cache = state
            self._last_cache_update = current_time
            
            return state
            
        except Exception as e:
            logger.error(f"Failed to get system state: {e}")
            return self._system_state_cache  # Return cached state on error
    
    async def _get_asset_metadata(self, asset_id: str) -> Dict[str, Any]:
        """Get asset metadata from database"""
        try:
            db = await get_db()
            async with db.execute(
                """
                SELECT abs_path, size, duration_sec, video_codec, audio_codec,
                       width, height, fps, container, tags_json, status
                FROM so_assets WHERE id = ?
                """,
                (asset_id,)
            ) as cursor:
                row = await cursor.fetchone()
            
            if not row:
                return {}
            
            return {
                'filepath': row[0],
                'file_size_bytes': row[1],
                'duration_sec': row[2],
                'video_codec': row[3],
                'audio_codec': row[4],
                'width': row[5],
                'height': row[6],
                'fps': row[7],
                'container': row[8],
                'tags': json.loads(row[9]) if row[9] else [],
                'status': row[10]
            }
            
        except Exception as e:
            logger.error(f"Failed to get asset metadata: {e}")
            return {}
    
    async def _is_recording_active(self) -> bool:
        """Check if OBS is currently recording"""
        if not self.obs:
            return False
        
        try:
            return await self.obs.is_recording()
        except Exception as e:
            logger.error(f"Failed to check recording status: {e}")
            return False
    
    async def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        try:
            # Non-blocking CPU usage check
            return psutil.cpu_percent(interval=0.1)
        except Exception as e:
            logger.error(f"Failed to get CPU usage: {e}")
            return 0.0
    
    async def _get_gpu_usage(self) -> float:
        """Get current GPU usage percentage"""
        try:
            # This would need to be implemented based on available GPU monitoring
            # For now, return 0 as placeholder
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get GPU usage: {e}")
            return 0.0
    
    def _get_available_memory(self) -> float:
        """Get available memory in GB"""
        try:
            memory = psutil.virtual_memory()
            return memory.available / (1024**3)  # Convert to GB
        except Exception as e:
            logger.error(f"Failed to get memory info: {e}")
            return 0.0
    
    def _get_disk_free_space(self) -> float:
        """Get free disk space in GB"""
        try:
            usage = psutil.disk_usage('/')
            return usage.free / (1024**3)  # Convert to GB
        except Exception as e:
            logger.error(f"Failed to get disk usage: {e}")
            return 0.0
    
    def _substitute_variables(self, value: Any, context: Dict[str, Any]) -> Any:
        """Substitute template variables in values recursively"""
        if isinstance(value, str):
            # Replace context variables
            for key, val in context.items():
                if val is not None:
                    placeholder = f"{{{key}}}"
                    value = value.replace(placeholder, str(val))
            
            # Replace date/time variables
            now = datetime.now()
            date_vars = {
                "{YYYY}": now.strftime("%Y"),
                "{MM}": now.strftime("%m"),
                "{DD}": now.strftime("%d"),
                "{HH}": now.strftime("%H"),
                "{mm}": now.strftime("%M"),
                "{ss}": now.strftime("%S")
            }
            
            for placeholder, replacement in date_vars.items():
                value = value.replace(placeholder, replacement)
            
            return value
            
        elif isinstance(value, dict):
            return {k: self._substitute_variables(v, context) for k, v in value.items()}
        
        elif isinstance(value, list):
            return [self._substitute_variables(v, context) for v in value]
        
        else:
            return value
    
    def _expand_path_pattern(self, pattern: str, context: Dict[str, Any]) -> str:
        """Expand path pattern with variables and add filename if needed"""
        path = self._substitute_variables(pattern, context)
        
        # If path ends with /, add the source filename
        if path.endswith("/"):
            source_path = Path(context.get('filepath', context.get('path', '')))
            if source_path:
                path = path + source_path.name
        
        return path
    
    def _generate_job_id(self, job_type: str) -> str:
        """Generate unique job ID"""
        import hashlib
        import uuid
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{job_type}_{timestamp}_{unique_id}"
    
    async def _log_rule_execution(self, rule: RuleResponse, execution: RuleExecution):
        """Log rule execution for audit trail"""
        try:
            log_entry = {
                "timestamp": execution.executed_at.isoformat(),
                "rule_id": rule.id,
                "rule_name": rule.name,
                "success": execution.success,
                "execution_time": execution.execution_time,
                "actions_performed": execution.actions_performed,
                "asset_id": execution.asset_id,
                "session_id": execution.session_id,
                "error_message": execution.error_message
            }
            
            # Write to structured log
            log_dir = Path(os.getenv("LOG_DIR", "/data/logs"))
            log_dir.mkdir(parents=True, exist_ok=True)
            
            log_file = log_dir / "rule_executions.jsonl"
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            # Also publish as event for real-time monitoring
            if self.nats:
                await self.nats.publish_event("rule.executed", log_entry)
            
        except Exception as e:
            logger.error(f"Failed to log rule execution: {e}")
    
    # Public API methods
    
    def enable(self):
        """Enable rules engine"""
        self.enabled = True
        logger.info("Rules engine enabled")
    
    def disable(self):
        """Disable rules engine"""
        self.enabled = False
        logger.info("Rules engine disabled")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        return {
            **self.stats,
            'enabled': self.enabled,
            'cache_hit_rate': self._cache_ttl,
            'last_cache_update': self._last_cache_update
        }
    
    async def clear_cache(self):
        """Clear system state cache"""
        async with self._lock:
            self._system_state_cache.clear()
            self._last_cache_update = 0
            logger.info("System state cache cleared")
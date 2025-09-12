"""Notification system API endpoints"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
import logging
import aiosqlite

from app.api.db.database import get_db
from app.api.notifications.service import notification_service
from app.api.notifications.providers.base import NotificationChannel, NotificationPriority

logger = logging.getLogger(__name__)
router = APIRouter()


class TemplateCreate(BaseModel):
    name: str
    channel: str
    subject: Optional[str] = None
    body: str
    is_default: bool = False


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    is_default: Optional[bool] = None


class PreviewRequest(BaseModel):
    channel: str
    template_id: Optional[str] = None
    inline_template: Optional[Dict[str, Any]] = None
    payload: Dict[str, Any]


class TestWebhookRequest(BaseModel):
    webhook_id: str


@router.get("/templates")
async def list_templates(
    channel: Optional[str] = Query(None),
    is_default: Optional[bool] = Query(None)
) -> Dict[str, Any]:
    """List all notification templates"""
    try:
        db = await get_db()
        
        query = "SELECT * FROM so_notification_templates WHERE 1=1"
        params = []
        
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        
        if is_default is not None:
            query += " AND is_default = ?"
            params.append(1 if is_default else 0)
        
        query += " ORDER BY updated_at DESC"
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        
        templates = []
        for row in rows:
            templates.append({
                "id": row[0],
                "name": row[1],
                "channel": row[2],
                "subject": row[3],
                "body": row[4],
                "is_default": bool(row[5]),
                "created_at": row[6],
                "updated_at": row[7]
            })
        
        return {"templates": templates}
    
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/templates")
async def create_template(template: TemplateCreate) -> Dict[str, Any]:
    """Create a new notification template"""
    try:
        db = await get_db()
        
        # Generate template ID
        import uuid
        template_id = f"tmpl_{uuid.uuid4().hex[:8]}"
        
        now = datetime.utcnow().isoformat()
        
        await db.execute("""
            INSERT INTO so_notification_templates 
            (id, name, channel, subject, body, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            template_id,
            template.name,
            template.channel,
            template.subject,
            template.body,
            1 if template.is_default else 0,
            now,
            now
        ))
        
        await db.commit()
        
        return {
            "id": template_id,
            "name": template.name,
            "channel": template.channel,
            "subject": template.subject,
            "body": template.body,
            "is_default": template.is_default,
            "created_at": now,
            "updated_at": now
        }
    
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    updates: TemplateUpdate
) -> Dict[str, Any]:
    """Update an existing template"""
    try:
        db = await get_db()
        
        # Build update query
        update_fields = []
        params = []
        
        if updates.name is not None:
            update_fields.append("name = ?")
            params.append(updates.name)
        
        if updates.subject is not None:
            update_fields.append("subject = ?")
            params.append(updates.subject)
        
        if updates.body is not None:
            update_fields.append("body = ?")
            params.append(updates.body)
        
        if updates.is_default is not None:
            update_fields.append("is_default = ?")
            params.append(1 if updates.is_default else 0)
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        
        params.append(template_id)
        
        query = f"UPDATE so_notification_templates SET {', '.join(update_fields)} WHERE id = ?"
        await db.execute(query, params)
        await db.commit()
        
        # Return updated template
        cursor = await db.execute(
            "SELECT * FROM so_notification_templates WHERE id = ?",
            (template_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Template not found")
        
        return {
            "id": row[0],
            "name": row[1],
            "channel": row[2],
            "subject": row[3],
            "body": row[4],
            "is_default": bool(row[5]),
            "created_at": row[6],
            "updated_at": row[7]
        }
    
    except Exception as e:
        logger.error(f"Failed to update template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str) -> Dict[str, Any]:
    """Delete a template"""
    try:
        db = await get_db()
        
        # Check if template exists
        cursor = await db.execute(
            "SELECT id FROM so_notification_templates WHERE id = ?",
            (template_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Delete template
        await db.execute(
            "DELETE FROM so_notification_templates WHERE id = ?",
            (template_id,)
        )
        await db.commit()
        
        return {"success": True, "message": "Template deleted"}
    
    except Exception as e:
        logger.error(f"Failed to delete template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview")
async def preview_template(request: PreviewRequest) -> Dict[str, Any]:
    """Preview how a template will render with given data"""
    try:
        # Get template if template_id provided
        template_body = ""
        template_subject = None
        
        if request.template_id:
            db = await get_db()
            cursor = await db.execute(
                "SELECT subject, body FROM so_notification_templates WHERE id = ?",
                (request.template_id,)
            )
            row = await cursor.fetchone()
            if row:
                template_subject = row[0]
                template_body = row[1]
        elif request.inline_template:
            template_body = request.inline_template.get("body", "")
            template_subject = request.inline_template.get("subject")
        
        # Render template with payload
        try:
            rendered_body = template_body.format(**request.payload)
            rendered_subject = template_subject.format(**request.payload) if template_subject else None
        except KeyError as e:
            rendered_body = f"Template error: missing variable {e}"
            rendered_subject = None
        
        # Check for truncation based on channel
        truncated = False
        if request.channel == "twitter":
            # Twitter has 280 character limit
            if len(rendered_body) > 280:
                rendered_body = rendered_body[:277] + "..."
                truncated = True
        elif request.channel == "discord":
            # Discord embeds have 2048 character limit for description
            if len(rendered_body) > 2048:
                rendered_body = rendered_body[:2045] + "..."
                truncated = True
        
        return {
            "subject": rendered_subject,
            "body": rendered_body,
            "truncated": truncated,
            "channel": request.channel
        }
    
    except Exception as e:
        logger.error(f"Failed to preview template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit")
async def get_audit_log(
    channel: Optional[str] = Query(None),
    event: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    limit: int = Query(50, le=100),
    cursor: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get notification audit log entries"""
    try:
        db = await get_db()
        
        # Build query
        query = "SELECT * FROM so_notification_audit WHERE 1=1"
        params = []
        
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        
        if event:
            query += " AND event_type LIKE ?"
            params.append(f"%{event}%")
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if from_date:
            query += " AND created_at >= ?"
            params.append(from_date)
        
        if to_date:
            query += " AND created_at <= ?"
            params.append(to_date)
        
        if cursor:
            query += " AND created_at < ?"
            params.append(cursor)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit + 1)  # Get one extra to check if there's more
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        
        entries = []
        for i, row in enumerate(rows[:limit]):
            # Parse JSON fields
            request_data = json.loads(row[8]) if row[8] else None
            response_data = json.loads(row[9]) if row[9] else None
            
            # Redact sensitive data in request
            if request_data:
                if "password" in request_data:
                    request_data["password"] = "***REDACTED***"
                if "api_key" in request_data:
                    request_data["api_key"] = "***REDACTED***"
                if "secret" in request_data:
                    request_data["secret"] = "***REDACTED***"
                if "body" in request_data and len(request_data["body"]) > 500:
                    request_data["body"] = request_data["body"][:500] + "..."
            
            entries.append({
                "id": row[0],
                "created_at": row[1],
                "event": row[2],
                "channel": row[3],
                "status": row[4],
                "latency_ms": row[5],
                "provider_msg_id": row[6],
                "error": row[7],
                "request": request_data,
                "response": response_data,
                "retry_count": row[10] if len(row) > 10 else 0,
                "next_retry_at": row[11] if len(row) > 11 else None
            })
        
        # Check if there are more entries
        has_more = len(rows) > limit
        next_cursor = entries[-1]["created_at"] if entries and has_more else None
        
        return {
            "entries": entries,
            "has_more": has_more,
            "next_cursor": next_cursor
        }
    
    except Exception as e:
        logger.error(f"Failed to get audit log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/webhook")
async def test_webhook(request: TestWebhookRequest) -> Dict[str, Any]:
    """Test a specific webhook endpoint"""
    try:
        # Get webhook configuration from settings
        from app.api.services.settings_service import settings_service
        settings = await settings_service.get_settings()
        webhook_config = settings.get("notifications", {}).get("webhook", {})
        
        # Find the specific webhook
        webhook = None
        for endpoint in webhook_config.get("endpoints", []):
            if endpoint.get("id") == request.webhook_id:
                webhook = endpoint
                break
        
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        
        # Send test notification
        from app.api.notifications.providers.webhook import WebhookProvider
        provider = WebhookProvider({
            "enabled": True,
            "endpoints": [webhook]
        })
        
        from app.api.notifications.providers.base import NotificationMessage
        test_message = NotificationMessage(
            event_type="test",
            title="Test Notification",
            content="This is a test notification from StreamOps",
            priority=NotificationPriority.NORMAL,
            metadata={"test": True, "timestamp": datetime.utcnow().isoformat()}
        )
        
        import time
        start_time = time.time()
        result = await provider.send(test_message)
        latency_ms = int((time.time() - start_time) * 1000)
        
        return {
            "ok": result.success,
            "message": "Test webhook sent successfully" if result.success else result.error,
            "details": {
                "webhook_id": request.webhook_id,
                "webhook_name": webhook.get("name"),
                "latency_ms": latency_ms,
                "provider_message_id": result.provider_message_id
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to test webhook: {e}")
        return {
            "ok": False,
            "message": str(e)
        }


@router.get("/events")
async def get_notification_events() -> Dict[str, Any]:
    """Get available notification events and their descriptions"""
    from app.api.notifications.providers.base import NotificationEvent
    
    events = {}
    for event in NotificationEvent:
        category = event.value.split('.')[0]
        events[event.value] = {
            "name": event.value,
            "description": event.value.replace('.', ' ').replace('_', ' ').title(),
            "category": category,
            "severity": "error" if "failed" in event.value or "critical" in event.value else 
                        "warning" if "warning" in event.value or "threshold" in event.value else 
                        "info"
        }
    
    categories = list(set(e["category"] for e in events.values()))
    
    return {
        "events": events,
        "categories": sorted(categories)
    }
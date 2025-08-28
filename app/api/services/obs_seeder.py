"""OBS connection seeder from environment variables"""
import os
import json
import logging
from datetime import datetime
from ulid import ULID

logger = logging.getLogger(__name__)

async def seed_obs_connections_from_env(db):
    """Seed OBS connections from environment variables if table is empty"""
    try:
        # Check if there are any existing connections
        cursor = await db.execute("SELECT COUNT(*) FROM so_obs_connections")
        row = await cursor.fetchone()
        count = row[0] if row else 0
        
        if count > 0:
            logger.info(f"OBS connections table already has {count} entries, skipping seed")
            return
        
        # Look for OBS connections in environment variables
        connections = []
        
        # Support up to 10 OBS instances
        for i in range(1, 11):
            name = os.getenv(f"SO_OBS_{i}_NAME")
            if not name:
                continue  # No more connections defined
            
            url = os.getenv(f"SO_OBS_{i}_URL")
            if not url:
                logger.warning(f"SO_OBS_{i}_NAME defined but SO_OBS_{i}_URL missing")
                continue
            
            password = os.getenv(f"SO_OBS_{i}_PASSWORD", "")
            auto_connect = os.getenv(f"SO_OBS_{i}_AUTO", "1") == "1"
            roles_str = os.getenv(f"SO_OBS_{i}_ROLES", "")
            
            # Parse roles
            roles = []
            if roles_str:
                for role in roles_str.split(','):
                    role = role.strip().lower()
                    if role in ['recording', 'streaming', 'backup']:
                        roles.append(role)
            
            connections.append({
                'id': str(ULID()),
                'name': name,
                'ws_url': url,
                'password': password,
                'auto_connect': auto_connect,
                'roles': roles
            })
            
            logger.info(f"Found OBS connection from env: {name} at {url}")
        
        # Also check for legacy single OBS configuration
        legacy_url = os.getenv("OBS_WS_URL")
        if legacy_url and not connections:
            legacy_password = os.getenv("OBS_WS_PASSWORD", "")
            connections.append({
                'id': str(ULID()),
                'name': 'Default OBS',
                'ws_url': legacy_url,
                'password': legacy_password,
                'auto_connect': True,
                'roles': ['recording', 'streaming']
            })
            logger.info(f"Found legacy OBS configuration: {legacy_url}")
        
        # Insert connections into database
        if connections:
            now = datetime.utcnow().isoformat()
            for conn in connections:
                await db.execute("""
                    INSERT INTO so_obs_connections
                    (id, name, ws_url, password, auto_connect, enabled, roles_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    conn['id'],
                    conn['name'],
                    conn['ws_url'],
                    conn['password'],
                    1 if conn['auto_connect'] else 0,
                    1,  # Enabled by default
                    json.dumps(conn['roles']),
                    now,
                    now
                ))
            
            await db.commit()
            logger.info(f"Seeded {len(connections)} OBS connection(s) from environment")
        else:
            logger.info("No OBS connections found in environment variables")
        
    except Exception as e:
        logger.error(f"Failed to seed OBS connections: {e}")
        # Don't raise - this is optional functionality
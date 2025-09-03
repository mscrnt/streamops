import os
import logging
from pathlib import Path
import aiosqlite
from typing import Optional
import json

logger = logging.getLogger(__name__)

# Global database connection
_db: Optional[aiosqlite.Connection] = None

async def get_db() -> aiosqlite.Connection:
    """Get database connection"""
    global _db
    if _db is None:
        await init_db()
    return _db

async def init_db() -> None:
    """Initialize database with schema"""
    global _db
    
    db_path = Path(os.getenv("DB_PATH", "/data/db/streamops.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        _db = await aiosqlite.connect(
            str(db_path),
            timeout=30.0,
        )
        
        # Enable foreign keys and JSON1
        await _db.execute("PRAGMA foreign_keys = ON")
        await _db.execute("PRAGMA journal_mode = WAL")
        
        # Create tables
        await create_tables()
        
        logger.info(f"Database initialized at {db_path}")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

async def close_db() -> None:
    """Close database connection"""
    global _db
    if _db:
        await _db.close()
        _db = None
        logger.info("Database connection closed")

async def create_tables() -> None:
    """Create all database tables"""
    
    # In prototype phase - drop existing tables to ensure clean schema
    if os.getenv("PROTOTYPE_MODE", "true").lower() == "true":
        logger.info("Prototype mode: Dropping existing tables for clean schema")
        tables = [
            "so_assets_fts",  # Drop FTS table first
            "so_thumbs", "so_jobs", "so_sessions", "so_rules",
            "so_overlays", "so_configs", "so_reports", "so_obs_connections",
            "so_roles", "so_drives", "so_assets"
        ]
        for table in tables:
            try:
                await _db.execute(f"DROP TABLE IF EXISTS {table}")
            except Exception as e:
                logger.debug(f"Could not drop {table}: {e}")
    
    # Assets table
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS so_assets (
            id TEXT PRIMARY KEY,
            abs_path TEXT UNIQUE NOT NULL,
            drive_hint TEXT,
            size INTEGER,
            mtime REAL,
            ctime REAL,
            hash_xxh64 TEXT,
            hash_sha256 TEXT,
            duration_sec REAL,
            video_codec TEXT,
            audio_codec TEXT,
            width INTEGER,
            height INTEGER,
            fps REAL,
            container TEXT,
            streams_json TEXT,
            tags_json TEXT,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Sessions table (OBS recording sessions)
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS so_sessions (
            id TEXT PRIMARY KEY,
            start_ts TIMESTAMP NOT NULL,
            end_ts TIMESTAMP,
            scene_at_start TEXT,
            obs_profile TEXT,
            obs_collection TEXT,
            markers_json TEXT,
            metrics_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Jobs table with blocking support for QP/AH/GR
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS so_jobs (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            asset_id TEXT,
            payload_json TEXT NOT NULL,
            state TEXT DEFAULT 'queued',
            progress REAL DEFAULT 0,
            error TEXT,
            result_json TEXT,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            -- New blocking fields for QP/AH/GR support
            deferred BOOLEAN DEFAULT 0,
            blocked_reason TEXT,
            next_run_at TIMESTAMP,
            attempts INTEGER DEFAULT 0,
            last_check_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES so_assets(id)
        )
    """)
    
    # Rules table with QP/AH support
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS so_rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            enabled BOOLEAN DEFAULT 1,
            priority INTEGER DEFAULT 50,
            -- Legacy columns for compatibility
            when_json TEXT,
            do_json TEXT,
            -- New structure columns
            trigger_json TEXT,
            conditions_json TEXT,
            actions_json TEXT,
            guardrails_json TEXT,
            meta_json TEXT,
            quiet_period_sec INTEGER DEFAULT 45,
            active_hours_json TEXT,
            preset_id TEXT,
            rule_yaml TEXT,
            last_triggered TIMESTAMP,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Thumbnails table
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS so_thumbs (
            asset_id TEXT PRIMARY KEY,
            poster_path TEXT,
            sprite_path TEXT,
            hover_mp4_path TEXT,
            waveform_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES so_assets(id)
        )
    """)
    
    # Overlays table
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS so_overlays (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            manifest_json TEXT NOT NULL,
            schedule_json TEXT,
            stats_json TEXT,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Config table (key-value store)
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS so_configs (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Reports table
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS so_reports (
            id TEXT PRIMARY KEY,
            week_start DATE NOT NULL,
            week_end DATE NOT NULL,
            hours_recorded REAL,
            disk_usage_delta INTEGER,
            top_games_json TEXT,
            backlog_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # OBS connections table for multi-instance support
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS so_obs_connections (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            ws_url TEXT NOT NULL,
            password TEXT,
            auto_connect BOOLEAN DEFAULT 1,
            enabled BOOLEAN DEFAULT 1,
            roles_json TEXT,
            last_status TEXT,
            last_error TEXT,
            last_seen_ts TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Drives table for watch folders
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS so_drives (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            label TEXT,
            type TEXT DEFAULT 'local',
            config_json TEXT,
            stats_json TEXT,
            tags_json TEXT,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Roles table for drive role assignments
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS so_roles (
            role TEXT PRIMARY KEY,
            drive_id TEXT,
            subpath TEXT,
            abs_path TEXT,
            watch BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (drive_id) REFERENCES so_drives(id)
        )
    """)
    
    # Create indexes
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_assets_path ON so_assets(abs_path)")
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_assets_status ON so_assets(status)")
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_assets_created ON so_assets(created_at)")
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state ON so_jobs(state)")
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_type ON so_jobs(type)")
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_asset ON so_jobs(asset_id)")
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_deferred_next_run ON so_jobs(deferred, next_run_at)")
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_blocked ON so_jobs(blocked_reason)")
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_rules_enabled ON so_rules(enabled)")
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_rules_priority ON so_rules(priority)")
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_obs_enabled ON so_obs_connections(enabled)")
    
    # Create FTS5 virtual table for full-text search
    await _db.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS so_assets_fts USING fts5(
            id UNINDEXED,
            abs_path,
            tags_json,
            content=so_assets,
            tokenize='porter'
        )
    """)
    
    # Create triggers to keep FTS in sync
    await _db.execute("""
        CREATE TRIGGER IF NOT EXISTS so_assets_fts_insert
        AFTER INSERT ON so_assets
        BEGIN
            INSERT INTO so_assets_fts(id, abs_path, tags_json)
            VALUES (new.id, new.abs_path, new.tags_json);
        END
    """)
    
    await _db.execute("""
        CREATE TRIGGER IF NOT EXISTS so_assets_fts_update
        AFTER UPDATE ON so_assets
        BEGIN
            UPDATE so_assets_fts
            SET abs_path = new.abs_path,
                tags_json = new.tags_json
            WHERE id = new.id;
        END
    """)
    
    await _db.execute("""
        CREATE TRIGGER IF NOT EXISTS so_assets_fts_delete
        AFTER DELETE ON so_assets
        BEGIN
            DELETE FROM so_assets_fts WHERE id = old.id;
        END
    """)
    
    await _db.commit()
    logger.info("Database schema created successfully")
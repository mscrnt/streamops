from typing import Dict, Any
import os
import shutil
import logging
from pathlib import Path

from app.worker.jobs.base import BaseJob

logger = logging.getLogger(__name__)

class CopyJob(BaseJob):
    """Job processor for copying files"""
    
    async def process(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Copy file to target location"""
        job_id = job_data.get("id")
        data = job_data.get("data", {})
        
        # Get the asset's current path from database
        asset_id = job_data.get("asset_id") or data.get("asset_id")
        input_path = data.get("input_path")
        
        if asset_id:
            # Look up the asset's current path
            import aiosqlite
            try:
                conn = await aiosqlite.connect("/data/db/streamops.db")
                cursor = await conn.execute("""
                    SELECT current_path 
                    FROM so_assets 
                    WHERE id = ?
                """, (asset_id,))
                row = await cursor.fetchone()
                await conn.close()
                
                if row and row[0]:
                    actual_path = row[0]
                    logger.info(f"Asset {asset_id} current_path from DB: {actual_path}")
                    # Use the current_path from database as the input
                    input_path = actual_path
            except Exception as e:
                logger.warning(f"Failed to get asset current_path: {e}")
        
        target_path = data.get("target_path")
        
        if not input_path:
            raise ValueError("No input_path specified")
        
        if not os.path.exists(input_path):
            raise ValueError(f"Input file not found: {input_path}")
        
        if not target_path:
            raise ValueError("No target_path specified")
        
        # Update progress
        await self.update_progress(job_id, 10, "running")
        
        # Resolve the target path
        target = Path(target_path)
        source = Path(input_path)
        
        # If target is a directory, append the filename
        if target.is_dir() or not target.suffix:
            target = target / source.name
        
        # Create parent directory if needed
        target.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Copying {input_path} to {target}")
        
        # Update progress
        await self.update_progress(job_id, 50, "running")
        
        # Perform the copy
        try:
            shutil.copy2(str(source), str(target))  # copy2 preserves metadata
            output_path = str(target)
        except Exception as e:
            error_msg = f"Failed to copy file: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Verify the file was copied
        if not os.path.exists(output_path):
            raise RuntimeError(f"File not found after copy: {output_path}")
        
        output_size = os.path.getsize(output_path)
        
        # Update progress
        await self.update_progress(job_id, 100, "completed")
        
        # Store result in database for rule engine to retrieve
        result = {
            "success": True,
            "output_path": output_path,
            "output_size": output_size,
            "input_path": input_path
        }
        
        # Update job with result
        try:
            import aiosqlite
            import json
            from datetime import datetime
            
            conn = await aiosqlite.connect("/data/db/streamops.db")
            await conn.execute("""
                UPDATE so_jobs 
                SET result_json = ?, state = 'completed', updated_at = ?
                WHERE id = ?
            """, (
                json.dumps(result),
                datetime.utcnow().isoformat(),
                job_id
            ))
            
            # Emit copy_completed event if we have an asset_id
            asset_id = job_data.get("asset_id") or data.get("asset_id")
            if asset_id:
                from app.api.services.asset_events import AssetEventService
                await AssetEventService.emit_copy_completed(asset_id, input_path, output_path)
                logger.info(f"Emitted copy_completed event for asset {asset_id}")
            
            await conn.commit()
            await conn.close()
            logger.info(f"Updated job {job_id} with result in database")
        except Exception as e:
            logger.error(f"Failed to update job result in database: {e}")
        
        # Skip folder reindexing - this is an expensive operation
        # The copied file will be picked up by the file watcher or next scan
        logger.info(f"Copy completed, skipping folder reindex for performance")
        
        logger.info(f"Successfully copied to {output_path}")
        
        return result
from typing import Dict, Any
import os
import shutil
import logging
from pathlib import Path

from app.worker.jobs.base import BaseJob

logger = logging.getLogger(__name__)

class MoveJob(BaseJob):
    """Job processor for moving files"""
    
    async def process(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Move file to target location"""
        logger.info(f"MoveJob received job_data: {job_data}")
        job_id = job_data.get("id")
        data = job_data.get("data", {})
        logger.info(f"MoveJob extracted data: {data}")
        
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
        
        logger.info(f"MoveJob input_path: {input_path}")
        target_path = data.get("target_path")
        logger.info(f"MoveJob target_path: {target_path}")
        
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
        
        logger.info(f"Moving {input_path} to {target}")
        
        # Update progress
        await self.update_progress(job_id, 50, "running")
        
        # Perform the move
        try:
            shutil.move(str(source), str(target))
            output_path = str(target)
        except Exception as e:
            error_msg = f"Failed to move file: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Verify the file was moved
        if not os.path.exists(output_path):
            raise RuntimeError(f"File not found after move: {output_path}")
        
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
        
        # Update job with result and update asset's current_path
        try:
            import aiosqlite
            import json
            from datetime import datetime
            
            conn = await aiosqlite.connect("/data/db/streamops.db")
            
            # Update job result
            await conn.execute("""
                UPDATE so_jobs 
                SET result_json = ?, state = 'completed', updated_at = ?
                WHERE id = ?
            """, (
                json.dumps(result),
                datetime.utcnow().isoformat(),
                job_id
            ))
            
            # Update asset's current_path if we have an asset_id
            asset_id = job_data.get("asset_id") or data.get("asset_id")
            if asset_id:
                await conn.execute("""
                    UPDATE so_assets 
                    SET current_path = ?, updated_at = datetime('now')
                    WHERE id = ?
                """, (output_path, asset_id))
                logger.info(f"Updated asset {asset_id} current_path to {output_path}")
            
            await conn.commit()
            await conn.close()
            logger.info(f"Updated job {job_id} with result in database")
        except Exception as e:
            logger.error(f"Failed to update job result in database: {e}")
        
        # Reindex both source and destination folders after move
        source_folder = os.path.dirname(input_path)
        dest_folder = os.path.dirname(output_path)
        
        logger.info(f"Reindexing folders after move: source={source_folder}, dest={dest_folder}")
        await self.reindex_folder_assets(source_folder)
        if source_folder != dest_folder:  # Only reindex dest if different from source
            await self.reindex_folder_assets(dest_folder)
        
        logger.info(f"Successfully moved to {output_path}")
        
        return result
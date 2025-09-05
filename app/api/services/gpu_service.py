"""GPU detection and management service"""

import logging
import asyncio
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GPUService:
    """Service for GPU detection and monitoring"""
    
    def __init__(self):
        self._gpu_info: Optional[Dict[str, Any]] = None
        self._last_check: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=5)
        self._lock = asyncio.Lock()
    
    async def get_gpu_info(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get GPU information with caching"""
        async with self._lock:
            # Check cache
            if not force_refresh and self._gpu_info and self._last_check:
                if datetime.now() - self._last_check < self._cache_duration:
                    return self._gpu_info
            
            # Detect GPU
            self._gpu_info = await self._detect_gpu()
            self._last_check = datetime.now()
            
            return self._gpu_info
    
    async def _detect_gpu(self) -> Dict[str, Any]:
        """Detect GPU and capabilities (NVIDIA, AMD, Intel)"""
        info = {
            "available": False,
            "vendor": None,  # nvidia, amd, intel
            "name": None,
            "driver_version": None,
            "cuda_version": None,
            "rocm_version": None,  # AMD
            "level_zero": False,  # Intel
            "memory_total": None,
            "memory_free": None,
            "utilization": None,
            "temperature": None,
            "hw_encode_available": False,
            "hw_decode_available": False,
            "hw_filters_available": False
        }
        
        try:
            # Check if nvidia-smi exists and works
            result = await self._run_command([
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,memory.free,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits"
            ])
            
            if result and result[0] == 0:
                parts = result[1].strip().split(", ")
                if len(parts) >= 6:
                    info["available"] = True
                    info["name"] = parts[0]
                    info["driver_version"] = parts[1]
                    info["memory_total"] = int(parts[2])
                    info["memory_free"] = int(parts[3])
                    info["utilization"] = int(parts[4])
                    info["temperature"] = int(parts[5])
                    
                    logger.debug(f"GPU detected via nvidia-smi: {info['name']} (Driver: {info['driver_version']})")
            else:
                logger.debug(f"nvidia-smi failed with code {result[0]}: {result[2]}")
            
            # Check CUDA version
            if info["available"]:
                cuda_result = await self._run_command(["nvidia-smi", "--query"])
                if cuda_result and cuda_result[0] == 0:
                    for line in cuda_result[1].split("\n"):
                        if "CUDA Version" in line:
                            cuda_version = line.split(":")[-1].strip()
                            info["cuda_version"] = cuda_version
                            break
            
            # Check FFmpeg capabilities
            if info["available"]:
                # Detect vendor-specific encoders
                info["vendor"] = "nvidia"
                encoders_result = await self._run_command(["ffmpeg", "-hide_banner", "-encoders"])
                if encoders_result and encoders_result[0] == 0:
                    encoders = encoders_result[1]
                    if "h264_nvenc" in encoders or "hevc_nvenc" in encoders:
                        info["hw_encode_available"] = True
                        logger.info("NVENC hardware encoding available")
                
                # Check for hardware decoders
                decoders_result = await self._run_command(["ffmpeg", "-hide_banner", "-decoders"])
                if decoders_result and decoders_result[0] == 0:
                    decoders = decoders_result[1]
                    if "h264_cuvid" in decoders or "hevc_cuvid" in decoders:
                        info["hw_decode_available"] = True
                        logger.info("NVDEC hardware decoding available")
                
                # Check for hardware filters
                filters_result = await self._run_command(["ffmpeg", "-hide_banner", "-filters"])
                if filters_result and filters_result[0] == 0:
                    filters = filters_result[1]
                    if "scale_cuda" in filters or "yadif_cuda" in filters:
                        info["hw_filters_available"] = True
                        logger.info("CUDA filters available")
            else:
                # Try AMD GPU detection
                amd_result = await self._detect_amd_gpu()
                if amd_result["available"]:
                    info.update(amd_result)
                else:
                    # Try Intel GPU detection
                    intel_result = await self._detect_intel_gpu()
                    if intel_result["available"]:
                        info.update(intel_result)
        
        except Exception as e:
            logger.warning(f"GPU detection failed: {e}")
        
        # If nvidia-smi failed, try alternative detection methods
        if not info["available"]:
            # Check if CUDA device is available via environment
            if "CUDA_VISIBLE_DEVICES" in os.environ:
                cuda_devices = os.environ["CUDA_VISIBLE_DEVICES"]
                if cuda_devices and cuda_devices != "-1":
                    logger.info(f"CUDA devices found in environment: {cuda_devices}")
                    info["available"] = True
                    info["vendor"] = "nvidia"
                    info["name"] = "NVIDIA GPU (via CUDA_VISIBLE_DEVICES)"
                    
            # Check for nvidia devices in /dev
            elif os.path.exists("/dev/nvidia0") or os.path.exists("/dev/nvidiactl"):
                logger.info("NVIDIA device files found in /dev")
                info["available"] = True
                info["vendor"] = "nvidia"
                info["name"] = "NVIDIA GPU (device files detected)"
                
            # Check if FFmpeg has CUDA support
            if not info["available"]:
                encoders_result = await self._run_command(["ffmpeg", "-hide_banner", "-encoders"])
                if encoders_result and encoders_result[0] == 0:
                    if "h264_nvenc" in encoders_result[1] or "hevc_nvenc" in encoders_result[1]:
                        logger.info("NVENC detected in FFmpeg - GPU must be present")
                        info["available"] = True
                        info["vendor"] = "nvidia"
                        info["name"] = "NVIDIA GPU (NVENC detected)"
                        info["hw_encode_available"] = True
        
        return info
    
    async def _run_command(self, cmd: list) -> tuple:
        """Run command and return result"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return process.returncode, stdout.decode(), stderr.decode()
        except Exception as e:
            logger.debug(f"Command failed: {cmd} - {e}")
            return -1, "", str(e)
    
    async def check_gpu_utilization(self) -> Optional[int]:
        """Get current GPU utilization percentage"""
        try:
            result = await self._run_command([
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits"
            ])
            
            if result[0] == 0:
                return int(result[1].strip())
        except Exception as e:
            logger.debug(f"Failed to get GPU utilization: {e}")
        
        return None
    
    async def is_gpu_available_for_work(self, threshold: int = 80) -> bool:
        """Check if GPU is available for processing (below threshold)"""
        utilization = await self.check_gpu_utilization()
        if utilization is None:
            return False  # No GPU or can't check
        
        return utilization < threshold
    
    async def _detect_amd_gpu(self) -> Dict[str, Any]:
        """Detect AMD GPU"""
        info = {"available": False, "vendor": "amd"}
        
        try:
            # Check for ROCm
            result = await self._run_command(["rocm-smi", "--showproductname"])
            if result[0] == 0:
                info["available"] = True
                info["name"] = "AMD GPU"
                logger.info("AMD GPU detected")
                
                # Check for AMF/VCE encoders in FFmpeg
                encoders_result = await self._run_command(["ffmpeg", "-hide_banner", "-encoders"])
                if encoders_result[0] == 0:
                    if "h264_amf" in encoders_result[1] or "h264_vaapi" in encoders_result[1]:
                        info["hw_encode_available"] = True
                        logger.info("AMD hardware encoding available")
        except:
            pass
        
        return info
    
    async def _detect_intel_gpu(self) -> Dict[str, Any]:
        """Detect Intel GPU"""
        info = {"available": False, "vendor": "intel"}
        
        try:
            # Check for Intel GPU via vainfo
            result = await self._run_command(["vainfo"])
            if result[0] == 0 and "Intel" in result[1]:
                info["available"] = True
                info["name"] = "Intel GPU"
                logger.info("Intel GPU detected")
                
                # Check for QSV encoders in FFmpeg
                encoders_result = await self._run_command(["ffmpeg", "-hide_banner", "-encoders"])
                if encoders_result[0] == 0:
                    if "h264_qsv" in encoders_result[1] or "h264_vaapi" in encoders_result[1]:
                        info["hw_encode_available"] = True
                        logger.info("Intel Quick Sync hardware encoding available")
        except:
            pass
        
        return info


# Global instance
gpu_service = GPUService()
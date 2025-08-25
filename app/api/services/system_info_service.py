"""System information service with caching"""

import os
import sys
import platform
import psutil
import subprocess
import asyncio
import json
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SystemInfoService:
    """Service for collecting and caching system information"""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_times: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(minutes=10)  # 10 minute cache for expensive operations
        self._lock = asyncio.Lock()
    
    async def get_info(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get comprehensive system information"""
        async with self._lock:
            # Check if we need to refresh
            cache_key = "system_info"
            if not force_refresh and cache_key in self._cache:
                if datetime.now() - self._cache_times[cache_key] < self._cache_ttl:
                    # Return cached data with fresh runtime stats
                    cached = self._cache[cache_key].copy()
                    cached["uptime_sec"] = self._get_uptime()
                    cached["memory"] = self._get_memory_info()
                    return cached
            
            # Collect all system information
            info = {
                "version": self._get_app_version(),
                "platform": self._get_platform_info(),
                "python": self._get_python_info(),
                "uptime_sec": self._get_uptime(),
                "cpu": self._get_cpu_info(),
                "memory": self._get_memory_info(),
                "containers": self._get_container_info(),
                "ffmpeg": await self._get_ffmpeg_info(),
                "gpu": await self._get_gpu_info()
            }
            
            # Cache the expensive parts (exclude runtime stats)
            self._cache[cache_key] = info.copy()
            self._cache_times[cache_key] = datetime.now()
            
            return info
    
    def _get_app_version(self) -> str:
        """Get application version"""
        # Try to read from package.json or version file
        try:
            package_path = Path("/opt/streamops/package.json")
            if package_path.exists():
                with open(package_path) as f:
                    data = json.load(f)
                    return data.get("version", "1.0.0")
        except:
            pass
        return "1.0.0"
    
    def _get_platform_info(self) -> Dict[str, str]:
        """Get platform information"""
        info = {
            "os": platform.system(),
            "distro": "",
            "kernel": platform.release()
        }
        
        # Try to get distribution info
        try:
            if platform.system() == "Linux":
                # Try to read from /etc/os-release
                if Path("/etc/os-release").exists():
                    with open("/etc/os-release") as f:
                        for line in f:
                            if line.startswith("ID="):
                                info["distro"] = line.split("=")[1].strip().strip('"')
                                break
                else:
                    info["distro"] = platform.linux_distribution()[0] if hasattr(platform, 'linux_distribution') else "unknown"
        except:
            info["distro"] = "unknown"
        
        return info
    
    def _get_python_info(self) -> Dict[str, str]:
        """Get Python information"""
        return {
            "version": sys.version.split()[0]
        }
    
    def _get_uptime(self) -> int:
        """Get system uptime in seconds"""
        try:
            # Try /proc/uptime first (Linux)
            if Path("/proc/uptime").exists():
                with open("/proc/uptime") as f:
                    return int(float(f.read().split()[0]))
            
            # Fallback to psutil
            boot_time = psutil.boot_time()
            return int(datetime.now().timestamp() - boot_time)
        except:
            return 0
    
    def _get_cpu_info(self) -> Dict[str, int]:
        """Get CPU information"""
        return {
            "cores_logical": psutil.cpu_count(logical=True),
            "cores_physical": psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True)
        }
    
    def _get_memory_info(self) -> Dict[str, int]:
        """Get memory information (always fresh)"""
        mem = psutil.virtual_memory()
        return {
            "total_bytes": mem.total,
            "available_bytes": mem.available
        }
    
    def _get_container_info(self) -> Dict[str, bool]:
        """Check if running inside a container"""
        inside_container = False
        
        # Check common container indicators
        if Path("/.dockerenv").exists():
            inside_container = True
        elif Path("/proc/1/cgroup").exists():
            try:
                with open("/proc/1/cgroup") as f:
                    if "docker" in f.read() or "containerd" in f.read():
                        inside_container = True
            except:
                pass
        
        return {
            "inside_container": inside_container
        }
    
    async def _get_ffmpeg_info(self) -> Dict[str, Any]:
        """Get FFmpeg information"""
        info = {
            "version": None,
            "build": None,
            "path": None,
            "hwaccels": [],
            "encoders": []
        }
        
        try:
            # Find FFmpeg path
            result = await self._run_command(["which", "ffmpeg"])
            if result[0] == 0:
                info["path"] = result[1].strip()
            else:
                info["path"] = "/usr/bin/ffmpeg"  # Common default
            
            # Get version
            result = await self._run_command(["ffmpeg", "-hide_banner", "-version"])
            if result[0] == 0:
                lines = result[1].split('\n')
                if lines:
                    # Parse first line: "ffmpeg version 6.1.1 ..."
                    version_match = re.search(r'ffmpeg version (\S+)', lines[0])
                    if version_match:
                        info["version"] = version_match.group(1)
                    info["build"] = lines[0]  # Full build string
            
            # Get hardware accelerations
            result = await self._run_command(["ffmpeg", "-hide_banner", "-hwaccels"])
            if result[0] == 0:
                lines = result[1].strip().split('\n')
                # Skip header line "Hardware acceleration methods:"
                if len(lines) > 1:
                    info["hwaccels"] = [l.strip() for l in lines[1:] if l.strip()]
            
            # Get NVENC encoders
            result = await self._run_command(["ffmpeg", "-hide_banner", "-encoders"])
            if result[0] == 0:
                nvenc_encoders = []
                for line in result[1].split('\n'):
                    if 'nvenc' in line.lower():
                        # Parse encoder name from line like " V..... h264_nvenc ..."
                        parts = line.split()
                        if len(parts) >= 2:
                            encoder = parts[1]
                            if 'nvenc' in encoder:
                                nvenc_encoders.append(encoder)
                info["encoders"] = nvenc_encoders
        
        except Exception as e:
            logger.warning(f"Failed to get FFmpeg info: {e}")
        
        return info
    
    async def _get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU information for NVIDIA, AMD, and Intel"""
        info = {
            "present": False,
            "vendor": None,  # nvidia, amd, intel
            "driver": None,
            "cuda": {"enabled": False, "version": None},
            "rocm": {"enabled": False, "version": None},  # AMD ROCm
            "level_zero": {"enabled": False},  # Intel Level Zero
            "count": 0,
            "gpus": [],
            "ffmpeg_hwaccels": [],
            "ffmpeg_encoders": []
        }
        
        # Try NVIDIA detection first
        nvidia_info = await self._detect_nvidia_gpu()
        if nvidia_info["present"]:
            info.update(nvidia_info)
            info["vendor"] = "nvidia"
        else:
            # Try AMD detection
            amd_info = await self._detect_amd_gpu()
            if amd_info["present"]:
                info.update(amd_info)
                info["vendor"] = "amd"
            else:
                # Try Intel detection
                intel_info = await self._detect_intel_gpu()
                if intel_info["present"]:
                    info.update(intel_info)
                    info["vendor"] = "intel"
        
        # Get FFmpeg capabilities regardless of vendor
        if info["present"]:
            ffmpeg_info = await self._get_ffmpeg_info()
            
            # Get all hardware acceleration methods
            info["ffmpeg_hwaccels"] = ffmpeg_info.get("hwaccels", [])
            
            # Get vendor-specific encoders
            all_encoders = []
            if info["vendor"] == "nvidia":
                # NVENC encoders
                for line in ffmpeg_info.get("encoders", []):
                    if "nvenc" in line:
                        all_encoders.append(line)
            elif info["vendor"] == "amd":
                # AMF/VCE encoders
                for line in ffmpeg_info.get("encoders", []):
                    if "amf" in line or "vaapi" in line:
                        all_encoders.append(line)
            elif info["vendor"] == "intel":
                # QSV/VAAPI encoders
                for line in ffmpeg_info.get("encoders", []):
                    if "qsv" in line or "vaapi" in line:
                        all_encoders.append(line)
            
            info["ffmpeg_encoders"] = all_encoders
        
        return info
    
    async def _detect_nvidia_gpu(self) -> Dict[str, Any]:
        """Detect NVIDIA GPU"""
        info = {
            "present": False,
            "driver": None,
            "cuda": {"enabled": False, "version": None},
            "count": 0,
            "gpus": []
        }
        
        try:
            # Try nvidia-smi
            result = await self._run_command([
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader"
            ])
            
            if result[0] == 0:
                info["present"] = True
                lines = result[1].strip().split('\n')
                info["count"] = len(lines)
                
                for line in lines:
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 3:
                        # Parse memory (comes as "12079 MiB")
                        memory_str = parts[1]
                        memory_bytes = 0
                        if 'MiB' in memory_str:
                            memory_bytes = int(memory_str.replace('MiB', '').strip()) * 1024 * 1024
                        
                        info["gpus"].append({
                            "name": parts[0],
                            "memory_total_bytes": memory_bytes
                        })
                        
                        if not info["driver"]:
                            info["driver"] = parts[2]
            
            # Get CUDA version
            if info["present"]:
                result = await self._run_command(["nvidia-smi"])
                if result[0] == 0:
                    # Parse CUDA version from header
                    for line in result[1].split('\n'):
                        if 'CUDA Version' in line:
                            cuda_match = re.search(r'CUDA Version:\s*(\d+\.\d+)', line)
                            if cuda_match:
                                info["cuda"]["enabled"] = True
                                info["cuda"]["version"] = cuda_match.group(1)
                                break
        
        except Exception as e:
            logger.debug(f"NVIDIA GPU detection failed: {e}")
        
        return info
    
    async def _detect_amd_gpu(self) -> Dict[str, Any]:
        """Detect AMD GPU"""
        info = {
            "present": False,
            "driver": None,
            "rocm": {"enabled": False, "version": None},
            "count": 0,
            "gpus": []
        }
        
        try:
            # Try rocm-smi for AMD GPUs
            result = await self._run_command(["rocm-smi", "--showproductname"])
            if result[0] == 0:
                info["present"] = True
                # Parse GPU names
                for line in result[1].split('\n'):
                    if 'GPU' in line and ':' in line:
                        gpu_name = line.split(':')[1].strip()
                        if gpu_name:
                            info["gpus"].append({"name": gpu_name, "memory_total_bytes": 0})
                info["count"] = len(info["gpus"])
                
                # Get ROCm version
                ver_result = await self._run_command(["rocm-smi", "--showversion"])
                if ver_result[0] == 0:
                    for line in ver_result[1].split('\n'):
                        if 'ROCm' in line:
                            match = re.search(r'(\d+\.\d+)', line)
                            if match:
                                info["rocm"]["enabled"] = True
                                info["rocm"]["version"] = match.group(1)
                                break
            else:
                # Fallback to checking for AMD GPU via lspci
                result = await self._run_command(["lspci"])
                if result[0] == 0:
                    for line in result[1].split('\n'):
                        if 'VGA' in line and ('AMD' in line or 'ATI' in line or 'Radeon' in line):
                            info["present"] = True
                            info["count"] = 1
                            # Extract GPU name
                            gpu_name = line.split(': ')[1] if ': ' in line else 'AMD GPU'
                            info["gpus"].append({"name": gpu_name, "memory_total_bytes": 0})
                            break
        
        except Exception as e:
            logger.debug(f"AMD GPU detection failed: {e}")
        
        return info
    
    async def _detect_intel_gpu(self) -> Dict[str, Any]:
        """Detect Intel GPU"""
        info = {
            "present": False,
            "driver": None,
            "level_zero": {"enabled": False},
            "count": 0,
            "gpus": []
        }
        
        try:
            # Check for Intel GPU via sysfs
            import glob
            intel_gpu_paths = glob.glob("/sys/class/drm/card*/device/vendor")
            for path in intel_gpu_paths:
                try:
                    with open(path, 'r') as f:
                        vendor_id = f.read().strip()
                        # Intel vendor ID is 0x8086
                        if vendor_id == "0x8086":
                            info["present"] = True
                            info["count"] += 1
                            # Try to get GPU name
                            device_path = path.replace('/vendor', '/device')
                            with open(device_path, 'r') as df:
                                device_id = df.read().strip()
                                info["gpus"].append({
                                    "name": f"Intel GPU ({device_id})",
                                    "memory_total_bytes": 0
                                })
                except:
                    pass
            
            # Alternative: Check via lspci
            if not info["present"]:
                result = await self._run_command(["lspci"])
                if result[0] == 0:
                    for line in result[1].split('\n'):
                        if 'VGA' in line and 'Intel' in line:
                            info["present"] = True
                            info["count"] = 1
                            # Extract GPU name
                            gpu_name = line.split(': ')[1] if ': ' in line else 'Intel GPU'
                            info["gpus"].append({"name": gpu_name, "memory_total_bytes": 0})
                            break
            
            # Check for Level Zero runtime
            if info["present"]:
                result = await self._run_command(["clinfo"])
                if result[0] == 0:
                    info["level_zero"]["enabled"] = True
        
        except Exception as e:
            logger.debug(f"Intel GPU detection failed: {e}")
        
        return info
    
    async def _run_command(self, cmd: list, timeout: float = 5.0) -> tuple:
        """Run command with timeout"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                return process.returncode, stdout.decode(), stderr.decode()
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return -1, "", "Command timed out"
        
        except Exception as e:
            return -1, "", str(e)


# Global instance
system_info_service = SystemInfoService()
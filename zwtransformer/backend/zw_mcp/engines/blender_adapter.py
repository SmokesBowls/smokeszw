# backend/zw_mcp/engines/blender_adapter.py
import os
import subprocess
import tempfile
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from ..base_adapter import BaseEngineAdapter


logger = logging.getLogger(__name__)


class BlenderAdapter(BaseEngineAdapter):
    """
    Blender engine adapter for processing ZW data through Blender.
    Handles 3D mesh generation, scene setup, materials, lighting, and cameras.
    """
    
    def __init__(self, blender_path: str = "blender"):
        super().__init__(name="blender", version="daemon-bridge")
        self.blender_path = blender_path
        self.blender_script_path = "backend/blender_scripts/blender_zw_processor.py"
        self.capabilities = ["mesh", "scene", "material", "light", "camera", "animation", "compose"]
        
    def get_capabilities(self) -> List[str]:
        """Return list of ZW block types this adapter can process."""
        return self.capabilities.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current adapter status."""
        # Test if Blender is accessible
        blender_available = self._test_blender_availability()
        
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": self.capabilities,
            "status": "active" if blender_available else "error",
            "blender_path": self.blender_path,
            "blender_available": blender_available,
            "script_path": self.blender_script_path
        }
    
    def process_zw_data(self, zw_data: str, parsed_zw: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Process ZW data using Blender.
        
        Args:
            zw_data: Raw ZW string
            parsed_zw: Parsed ZW dictionary  
            **kwargs: Additional parameters (blender_path override, etc.)
            
        Returns:
            Processing results dictionary
        """
        # Use custom blender path if provided
        blender_exec = kwargs.get("blender_path", self.blender_path)
        
        # Validate Blender availability
        if not self._test_blender_availability(blender_exec):
            return {
                "status": "error",
                "message": f"Blender not accessible at: {blender_exec}",
                "results": [],
                "stdout": "",
                "stderr": "Blender executable not found or not accessible"
            }
        
        try:
            # Create temporary files for ZW input and JSON output
            with tempfile.NamedTemporaryFile('w', suffix='.zw', delete=False) as zw_file:
                zw_file.write(zw_data)
                zw_input_path = zw_file.name
            
            output_path = zw_input_path + ".json"
            
            # Construct Blender command
            cmd = [
                blender_exec,
                "--background",  # Run without UI
                "--python", self.blender_script_path,
                "--", zw_input_path, output_path
            ]
            
            logger.info(f"Executing Blender command: {' '.join(cmd)}")
            
            # Execute Blender with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
                cwd=os.getcwd()
            )
            
            # Parse results
            blender_results = []
            if os.path.exists(output_path):
                try:
                    with open(output_path, 'r') as f:
                        blender_results = json.load(f)
                    os.unlink(output_path)  # Clean up
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    logger.warning(f"Could not parse Blender output JSON: {e}")
            
            # Clean up input file
            os.unlink(zw_input_path)
            
            # Determine status
            status = "success" if result.returncode == 0 else "error"
            
            # Count successful operations
            success_count = len([r for r in blender_results if r.get("status") == "success"])
            total_count = len(blender_results)
            
            return {
                "status": status,
                "message": f"Blender processing {'completed' if status == 'success' else 'failed'}: {success_count}/{total_count} operations successful",
                "results": blender_results,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "temp_input": zw_input_path,
                "temp_output": output_path
            }
            
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "message": "Blender processing timed out after 2 minutes",
                "results": [],
                "stdout": "",
                "stderr": "Process timeout"
            }
        except Exception as e:
            logger.error(f"Error during Blender processing: {e}")
            return {
                "status": "error", 
                "message": f"Blender processing failed: {str(e)}",
                "results": [],
                "stdout": "",
                "stderr": str(e)
            }
    
    def _test_blender_availability(self, blender_path: Optional[str] = None) -> bool:
        """
        Test if Blender is available and accessible.
        
        Args:
            blender_path: Optional override for Blender executable path
            
        Returns:
            True if Blender is accessible, False otherwise
        """
        test_path = blender_path or self.blender_path
        
        try:
            # Try to get Blender version (quick test)
            result = subprocess.run(
                [test_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return False
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate Blender-specific configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            True if configuration is valid
        """
        # Check if custom blender path is provided and valid
        if "blender_path" in config:
            custom_path = config["blender_path"]
            if not self._test_blender_availability(custom_path):
                logger.error(f"Invalid Blender path in config: {custom_path}")
                return False
        
        # Check if Blender script exists
        if not os.path.exists(self.blender_script_path):
            logger.error(f"Blender script not found: {self.blender_script_path}")
            return False
        
        return True
    
    def get_supported_zw_blocks(self, parsed_zw: Dict[str, Any]) -> List[str]:
        """
        Get ZW blocks that Blender can specifically handle.
        
        Args:
            parsed_zw: Parsed ZW dictionary
            
        Returns:
            List of ZW block types Blender can process
        """
        blender_blocks = []
        
        # Map ZW block types to Blender capabilities
        zw_to_blender_map = {
            "ZW-MESH": "mesh",
            "ZW-OBJECT": "mesh", 
            "ZW-SCENE": "scene",
            "ZW-MATERIAL": "material",
            "ZW-LIGHT": "light", 
            "ZW-CAMERA": "camera",
            "ZW-ANIMATION": "animation",
            "ZW-COMPOSE": "compose"
        }
        
        for zw_key in parsed_zw.keys():
            zw_upper = zw_key.upper()
            if zw_upper in zw_to_blender_map:
                capability = zw_to_blender_map[zw_upper]
                if capability in self.capabilities:
                    blender_blocks.append(capability)
        
        return blender_blocks
    
    def initialize(self) -> bool:
        """
        Initialize the Blender adapter.
        
        Returns:
            True if initialization successful
        """
        # Test Blender availability
        if not self._test_blender_availability():
            logger.error(f"Blender initialization failed: executable not found at {self.blender_path}")
            self.status = "error"
            return False
        
        # Check for required Blender script
        if not os.path.exists(self.blender_script_path):
            logger.error(f"Blender script not found: {self.blender_script_path}")
            self.status = "error"
            return False
        
        self.status = "active"
        logger.info(f"Blender adapter initialized successfully (path: {self.blender_path})")
        return True
    
    def __repr__(self) -> str:
        return f"<BlenderAdapter(path='{self.blender_path}', status='{self.status}', capabilities={len(self.capabilities)})>"

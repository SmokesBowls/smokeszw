# backend/zw_mcp/base_adapter.py
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class BaseEngineAdapter(ABC):
    """
    Abstract base class for all engine adapters in the ZW Multi-Engine Router system.
    Each engine (Blender, Godot, Unity, etc.) implements this interface.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name.lower()
        self.version = version
        self.capabilities: List[str] = []
        self.status = "inactive"
        
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Returns a list of ZW block types this engine can process.
        Example: ["mesh", "scene", "material", "light", "camera"]
        """
        pass
    
    @abstractmethod
    def process_zw_data(self, zw_data: str, parsed_zw: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Process ZW data using this engine.
        
        Args:
            zw_data: Raw ZW string
            parsed_zw: Parsed ZW dictionary
            **kwargs: Additional engine-specific parameters
            
        Returns:
            Dictionary with processing results:
            {
                "status": "success" | "error" | "partial",
                "message": "Human readable status",
                "results": [...],  # Engine-specific results
                "stdout": "...",   # Optional stdout capture
                "stderr": "...",   # Optional stderr capture
            }
        """
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Returns current engine status information.
        
        Returns:
            {
                "name": self.name,
                "version": self.version,
                "capabilities": self.capabilities,
                "status": self.status,
                "additional_info": {...}
            }
        """
        pass
    
    def can_process(self, zw_block_type: str) -> bool:
        """
        Check if this engine can process a specific ZW block type.
        
        Args:
            zw_block_type: The ZW block type (e.g., "mesh", "scene", "light")
            
        Returns:
            True if this engine can process the block type
        """
        return zw_block_type.lower() in [cap.lower() for cap in self.capabilities]
    
    def initialize(self) -> bool:
        """
        Initialize the engine adapter. Override if needed.
        
        Returns:
            True if initialization successful, False otherwise
        """
        self.status = "active"
        return True
    
    def shutdown(self) -> bool:
        """
        Shutdown the engine adapter. Override if needed.
        
        Returns:
            True if shutdown successful, False otherwise
        """
        self.status = "inactive"
        return True
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate engine-specific configuration. Override if needed.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            True if configuration is valid
        """
        return True
    
    def get_supported_zw_blocks(self, parsed_zw: Dict[str, Any]) -> List[str]:
        """
        Extract ZW block types from parsed ZW that this engine can handle.
        
        Args:
            parsed_zw: Parsed ZW dictionary
            
        Returns:
            List of ZW block types this engine can process
        """
        supported_blocks = []
        
        # Check top-level ZW blocks
        for key in parsed_zw.keys():
            if key.upper().startswith('ZW-'):
                # Extract block type (e.g., "ZW-MESH" -> "mesh")
                block_type = key.upper().replace('ZW-', '').lower()
                if self.can_process(block_type):
                    supported_blocks.append(block_type)
        
        return supported_blocks
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', version='{self.version}', status='{self.status}')>"

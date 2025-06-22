# backend/zw_mcp/engine_router.py
import logging
from typing import Dict, List, Any, Optional
from .base_adapter import BaseEngineAdapter

logger = logging.getLogger(__name__)


class EngineRouter:
    """
    Central router for managing and coordinating multiple engine adapters.
    Routes ZW data to appropriate engines based on content and capabilities.
    """
    
    def __init__(self):
        self.adapters: Dict[str, BaseEngineAdapter] = {}
        self.default_engine: Optional[str] = None
        self.routing_rules: Dict[str, List[str]] = {}  # ZW block type -> engine names
        
    def register_adapter(self, adapter: BaseEngineAdapter, is_default: bool = False) -> bool:
        """
        Register an engine adapter with the router.
        
        Args:
            adapter: Engine adapter instance
            is_default: Whether this should be the default engine
            
        Returns:
            True if registration successful
        """
        try:
            engine_name = adapter.name.lower()
            
            # Initialize the adapter
            if not adapter.initialize():
                logger.error(f"Failed to initialize adapter: {engine_name}")
                return False
            
            self.adapters[engine_name] = adapter
            
            # Set as default if requested or if no default exists
            if is_default or self.default_engine is None:
                self.default_engine = engine_name
            
            # Update routing rules based on adapter capabilities
            self._update_routing_rules(adapter)
            
            logger.info(f"Registered engine adapter: {engine_name} (capabilities: {adapter.get_capabilities()})")
            return True
            
        except Exception as e:
            logger.error(f"Error registering adapter {adapter.name}: {e}")
            return False
    
    def unregister_adapter(self, engine_name: str) -> bool:
        """
        Unregister an engine adapter.
        
        Args:
            engine_name: Name of the engine to unregister
            
        Returns:
            True if unregistration successful
        """
        engine_name = engine_name.lower()
        
        if engine_name not in self.adapters:
            logger.warning(f"Attempt to unregister unknown engine: {engine_name}")
            return False
        
        try:
            adapter = self.adapters[engine_name]
            adapter.shutdown()
            del self.adapters[engine_name]
            
            # Update default if needed
            if self.default_engine == engine_name:
                self.default_engine = next(iter(self.adapters.keys())) if self.adapters else None
            
            # Rebuild routing rules
            self._rebuild_routing_rules()
            
            logger.info(f"Unregistered engine adapter: {engine_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error unregistering adapter {engine_name}: {e}")
            return False
    
    def route_zw_packet(self, zw_data: str, parsed_zw: Dict[str, Any], 
                       target_engines: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        """
        Route ZW data to appropriate engines for processing.
        
        Args:
            zw_data: Raw ZW string
            parsed_zw: Parsed ZW dictionary
            target_engines: Specific engines to use (optional)
            **kwargs: Additional parameters for engines
            
        Returns:
            Dictionary with routing results from all engines
        """
        if not self.adapters:
            return {
                "status": "error",
                "message": "No engine adapters registered",
                "results": {},
                "engines_used": [],
                "successful_engines": 0,
                "total_engines": 0
            }
        
        # Determine which engines to use
        engines_to_use = self._determine_target_engines(parsed_zw, target_engines)
        
        if not engines_to_use:
            return {
                "status": "error", 
                "message": "No suitable engines found for the provided ZW data",
                "results": {},
                "engines_used": [],
                "successful_engines": 0,
                "total_engines": 0
            }
        
        # Route to each selected engine
        results = {}
        successful_count = 0
        
        for engine_name in engines_to_use:
            try:
                adapter = self.adapters[engine_name]
                logger.info(f"Routing ZW data to engine: {engine_name}")
                
                # Process with the specific engine
                result = adapter.process_zw_data(zw_data, parsed_zw, **kwargs)
                results[engine_name] = result
                
                # Count successes
                if result.get("status") == "success":
                    successful_count += 1
                
            except Exception as e:
                logger.error(f"Error processing ZW data with engine {engine_name}: {e}")
                results[engine_name] = {
                    "status": "error",
                    "message": f"Exception during processing: {str(e)}",
                    "results": []
                }
        
        # Determine overall status
        total_engines = len(engines_to_use)
        if successful_count == total_engines:
            overall_status = "success"
        elif successful_count > 0:
            overall_status = "partial_success"
        else:
            overall_status = "error"
        
        return {
            "status": overall_status,
            "message": f"Processed by {successful_count}/{total_engines} engines successfully",
            "results": results,
            "engines_used": engines_to_use,
            "successful_engines": successful_count,
            "total_engines": total_engines
        }
    
    def get_router_status(self) -> Dict[str, Any]:
        """
        Get comprehensive router status information.
        
        Returns:
            Router status dictionary
        """
        engines_status = {}
        total_capabilities = 0
        
        for name, adapter in self.adapters.items():
            status = adapter.get_status()
            engines_status[name] = status
            total_capabilities += len(status.get("capabilities", []))
        
        return {
            "registered_engines": len(self.adapters),
            "default_engine": self.default_engine,
            "engines": engines_status,
            "total_capabilities": total_capabilities,
            "routing_rules": self.routing_rules
        }
    
    def get_all_capabilities(self) -> Dict[str, List[str]]:
        """
        Get capabilities of all registered engines.
        
        Returns:
            Dictionary mapping engine names to their capabilities
        """
        return {name: adapter.get_capabilities() for name, adapter in self.adapters.items()}
    
    def get_engines_for_block_type(self, block_type: str) -> List[str]:
        """
        Get list of engines that can process a specific ZW block type.
        
        Args:
            block_type: ZW block type (e.g., "mesh", "scene")
            
        Returns:
            List of engine names that can process this block type
        """
        capable_engines = []
        for name, adapter in self.adapters.items():
            if adapter.can_process(block_type):
                capable_engines.append(name)
        return capable_engines
    
    def _determine_target_engines(self, parsed_zw: Dict[str, Any], 
                                 target_engines: Optional[List[str]] = None) -> List[str]:
        """
        Determine which engines should process the ZW data.
        
        Args:
            parsed_zw: Parsed ZW dictionary
            target_engines: Explicitly requested engines
            
        Returns:
            List of engine names to use
        """
        if target_engines:
            # Use explicitly requested engines (if they exist)
            valid_engines = []
            for engine in target_engines:
                engine_lower = engine.lower()
                if engine_lower in self.adapters:
                    valid_engines.append(engine_lower)
                else:
                    logger.warning(f"Requested engine '{engine}' not registered")
            return valid_engines
        
        # Auto-detect based on ZW content and engine capabilities
        suitable_engines = set()
        
        # Check what ZW blocks are present
        for key in parsed_zw.keys():
            if key.upper().startswith('ZW-'):
                block_type = key.upper().replace('ZW-', '').lower()
                capable_engines = self.get_engines_for_block_type(block_type)
                suitable_engines.update(capable_engines)
        
        # If no specific blocks found or no capable engines, use default
        if not suitable_engines and self.default_engine:
            suitable_engines.add(self.default_engine)
        
        return list(suitable_engines)
    
    def _update_routing_rules(self, adapter: BaseEngineAdapter):
        """
        Update routing rules when a new adapter is registered.
        
        Args:
            adapter: The newly registered adapter
        """
        for capability in adapter.get_capabilities():
            cap_lower = capability.lower()
            if cap_lower not in self.routing_rules:
                self.routing_rules[cap_lower] = []
            
            if adapter.name not in self.routing_rules[cap_lower]:
                self.routing_rules[cap_lower].append(adapter.name)
    
    def _rebuild_routing_rules(self):
        """
        Rebuild all routing rules from current adapters.
        """
        self.routing_rules = {}
        for adapter in self.adapters.values():
            self._update_routing_rules(adapter)
    
    def __repr__(self) -> str:
        return f"<EngineRouter(engines={len(self.adapters)}, default='{self.default_engine}')>"

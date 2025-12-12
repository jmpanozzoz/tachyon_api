"""
Engine Configuration System

Provides a way to configure and switch between different ASGI engines
(Starlette vs tachyon-engine) for the Tachyon application.
"""

import os
from enum import Enum
from typing import Optional

from .adapters import (
    AsgiApplicationAdapter,
    StarletteApplicationAdapter,
    TACHYON_ENGINE_AVAILABLE,
)

if TACHYON_ENGINE_AVAILABLE:
    from .adapters import TachyonEngineApplicationAdapter


class AsgiEngine(Enum):
    """ASGI engine selection options."""
    
    STARLETTE = "starlette"
    TACHYON = "tachyon"
    AUTO = "auto"  # Try tachyon-engine first, fallback to Starlette


class EngineConfig:
    """
    Configuration for ASGI engine selection.
    
    Allows runtime switching between Starlette and tachyon-engine
    via explicit configuration, environment variables, or auto-detection.
    """
    
    def __init__(self, engine: Optional[AsgiEngine] = None):
        """
        Initialize engine configuration.
        
        Args:
            engine: Explicit engine choice (AsgiEngine.STARLETTE, AsgiEngine.TACHYON, or AsgiEngine.AUTO)
                   If None, checks TACHYON_ENGINE environment variable, defaults to AUTO.
        
        Environment Variables:
            TACHYON_ENGINE: Set to "starlette", "tachyon", or "auto" to control engine selection
        
        Examples:
            # Explicit engine selection
            config = EngineConfig(AsgiEngine.TACHYON)
            
            # Auto-detection (default)
            config = EngineConfig()
            
            # Via environment variable
            os.environ['TACHYON_ENGINE'] = 'tachyon'
            config = EngineConfig()
        """
        # Priority: explicit argument > environment variable > AUTO
        if engine is not None:
            self.engine = engine
        else:
            env_engine = os.environ.get('TACHYON_ENGINE', 'auto').lower()
            if env_engine == 'starlette':
                self.engine = AsgiEngine.STARLETTE
            elif env_engine == 'tachyon':
                self.engine = AsgiEngine.TACHYON
            else:
                self.engine = AsgiEngine.AUTO
    
    def get_adapter(self, lifespan=None, debug: bool = False) -> AsgiApplicationAdapter:
        """
        Get the appropriate ASGI application adapter based on configuration.
        
        Args:
            lifespan: Optional lifespan context manager
            debug: Enable debug mode
        
        Returns:
            AsgiApplicationAdapter: Either StarletteApplicationAdapter or TachyonEngineApplicationAdapter
        
        Raises:
            ImportError: If tachyon-engine is requested but not installed
        """
        if self.engine == AsgiEngine.TACHYON:
            # Explicit tachyon-engine request
            if not TACHYON_ENGINE_AVAILABLE:
                raise ImportError(
                    "tachyon-engine is not installed. "
                    "Install it with: pip install tachyon-api[engine]"
                )
            return TachyonEngineApplicationAdapter(lifespan=lifespan, debug=debug)
        
        elif self.engine == AsgiEngine.STARLETTE:
            # Explicit Starlette request
            return StarletteApplicationAdapter(lifespan=lifespan, debug=debug)
        
        else:  # AsgiEngine.AUTO
            # Try tachyon-engine first, fallback to Starlette
            if TACHYON_ENGINE_AVAILABLE:
                try:
                    return TachyonEngineApplicationAdapter(lifespan=lifespan, debug=debug)
                except Exception:
                    # If tachyon-engine fails for any reason, fallback to Starlette
                    return StarletteApplicationAdapter(lifespan=lifespan, debug=debug)
            else:
                # tachyon-engine not available, use Starlette
                return StarletteApplicationAdapter(lifespan=lifespan, debug=debug)
    
    def get_engine_name(self) -> str:
        """
        Get the name of the engine that will be used.
        
        Returns:
            str: "tachyon-engine" or "starlette"
        """
        if self.engine == AsgiEngine.TACHYON:
            return "tachyon-engine"
        elif self.engine == AsgiEngine.STARLETTE:
            return "starlette"
        else:  # AUTO
            return "tachyon-engine" if TACHYON_ENGINE_AVAILABLE else "starlette"
    
    def is_tachyon_engine(self) -> bool:
        """
        Check if tachyon-engine will be used.
        
        Returns:
            bool: True if tachyon-engine will be used, False if Starlette will be used
        """
        return self.get_engine_name() == "tachyon-engine"
    
    @staticmethod
    def set_default_engine(engine: AsgiEngine) -> None:
        """
        Set the default engine via environment variable.
        
        This affects all future EngineConfig instances that don't explicitly specify an engine.
        
        Args:
            engine: Engine to use as default
        
        Example:
            EngineConfig.set_default_engine(AsgiEngine.TACHYON)
        """
        os.environ['TACHYON_ENGINE'] = engine.value
    
    @staticmethod
    def get_available_engines() -> list:
        """
        Get list of available engines.
        
        Returns:
            list: List of engine names that are available
        """
        engines = ["starlette"]
        if TACHYON_ENGINE_AVAILABLE:
            engines.append("tachyon-engine")
        return engines

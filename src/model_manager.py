"""
Global model manager for caching and device detection.
Prevents reloading models on every request.
"""

import os
import torch
import logging
from typing import Dict, Optional
from src.models.retinanet import SimpleRetinaNet

logger = logging.getLogger("lung_nodule_model_manager")


class ModelManager:
    """Singleton model manager with caching and device detection."""
    
    _instance = None
    _models_cache: Dict[str, Optional[object]] = {}
    _device = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._detect_device()
        logger.info(f"ModelManager initialized with device: {self._device}")
    
    def _detect_device(self):
        """Detect available device (CUDA or CPU)."""
        if torch.cuda.is_available():
            self._device = torch.device("cuda")
            logger.info(f"CUDA available. Using device: {self._device} ({torch.cuda.get_device_name(0)})")
        else:
            self._device = torch.device("cpu")
            logger.info("CUDA not available. Using CPU.")
    
    @property
    def device(self):
        """Get the current compute device."""
        return self._device
    
    def get_device_name(self) -> str:
        """Get human-readable device name."""
        if self._device.type == "cuda":
            return f"CUDA ({torch.cuda.get_device_name(0)})"
        return "CPU"
    
    def load_model(self, model_path: str, force_reload: bool = False) -> Optional[object]:
        """
        Load a model from disk with caching.
        
        Args:
            model_path: Path to .pth file
            force_reload: If True, reload even if cached
            
        Returns:
            Loaded model or None if loading fails
        """
        abs_path = os.path.abspath(model_path)
        
        # Check cache first
        if not force_reload and abs_path in self._models_cache:
            logger.info(f"Using cached model: {abs_path}")
            return self._models_cache[abs_path]
        
        try:
            # Validate file
            if not os.path.exists(abs_path):
                logger.error(f"Model file not found: {abs_path}")
                return None
            
            if os.path.getsize(abs_path) == 0:
                logger.error(f"Model file is empty: {abs_path}")
                return None
            
            logger.info(f"Loading model from: {abs_path} on device {self._device}")
            
            # Create model and load weights
            model = SimpleRetinaNet()
            state = torch.load(abs_path, map_location=self._device)
            
            # Handle both raw state_dict and packaged state_dict
            if isinstance(state, dict) and "model_state_dict" in state:
                state_dict = state["model_state_dict"]
            else:
                state_dict = state
            
            result = model.load_state_dict(state_dict, strict=False)
            
            if result.missing_keys or result.unexpected_keys:
                logger.warning(
                    f"State dict mismatch - Missing: {len(result.missing_keys)}, "
                    f"Unexpected: {len(result.unexpected_keys)}"
                )
            
            model.to(self._device)
            model.eval()
            
            logger.info(f"Model loaded successfully on {self._device}")
            
            # Cache the model
            self._models_cache[abs_path] = model
            return model
            
        except Exception as e:
            logger.error(f"Failed to load model {abs_path}: {e}")
            self._models_cache[abs_path] = None
            return None
    
    def unload_model(self, model_path: str):
        """Remove a model from cache to free memory."""
        abs_path = os.path.abspath(model_path)
        if abs_path in self._models_cache:
            del self._models_cache[abs_path]
            logger.info(f"Unloaded model: {abs_path}")
    
    def clear_cache(self):
        """Clear all cached models."""
        self._models_cache.clear()
        if self._device.type == "cuda":
            torch.cuda.empty_cache()
        logger.info("Model cache cleared")
    
    def get_cache_info(self) -> Dict:
        """Get info about cached models."""
        return {
            "device": str(self._device),
            "cached_models": len(self._models_cache),
            "model_paths": list(self._models_cache.keys())
        }


# Global singleton instance
_model_manager = None

def get_model_manager() -> ModelManager:
    """Get or create the global model manager instance."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager

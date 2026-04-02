class CVCutterError(Exception):
    """Base exception for all CVCutter errors."""
    pass

class DataError(CVCutterError):
    """Raised when there is an issue with data (e.g., DB, File IO)."""
    pass

class AudioProcessingError(CVCutterError):
    """Raised when an error occurs during audio processing."""
    pass

class VideoProcessingError(CVCutterError):
    """Raised when an error occurs during video processing."""
    pass

class MultimodalAnalysisError(CVCutterError):
    """Raised when an error occurs during AI/Multimodal analysis."""
    pass

class APIIntegrationError(CVCutterError):
    """Raised when external API integration fails."""
    pass

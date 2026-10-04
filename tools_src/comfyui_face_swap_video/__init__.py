"""Register nodes only when loaded by ComfyUI, never by the CLI."""
try:
    import folder_paths
except ImportError:
    NODE_CLASS_MAPPINGS={}
    NODE_DISPLAY_NAME_MAPPINGS={}
else:
    from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

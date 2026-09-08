"""Local mask session client plus optional ComfyUI route registration."""

# ComfyUI imports a custom-node package while its `server` module is available.
# Ordinary CLI/tests import this package without ComfyUI on sys.path, so route
# registration remains optional and the image helpers stay independently usable.
try:
    from server import PromptServer  # type: ignore  # noqa: F401
except ImportError:
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}
else:
    from .comfyui_plugin.server_routes import register_routes

    register_routes()
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

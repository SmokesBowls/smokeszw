import sys
import os
import datetime
import json
import yaml
import uvicorn
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import tempfile

# === CONFIGURATION ===
DEFAULT_BLENDER_EXEC = "/home/tran/Downloads/blender-4.4.3-linux-x64/blender"
BLENDER_HELPER_SCRIPT_NAME = "backend/blender_scripts/blender_zw_processor.py"

# === LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zw_transformer_daemon")

# === APP INITIALIZATION ===
app = FastAPI(title="ZW Transformer Multi-Engine Daemon", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === BLENDER ADAPTER FOR DAEMON ===
class BlenderAdapterDaemon:
    def __init__(self, blender_path='blender'):
        self.name = "blender"
        self.version = "daemon-bridge"
        self.capabilities = ["mesh", "scene", "material", "light", "camera"]
        self.status = "active"
        self.blender_path = blender_path

    def get_status(self):
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": self.capabilities,
            "status": self.status
        }

    def process_scene(self, scene_data):
        zw_string = yaml.dump({"ZW-SCENE": scene_data})
        return self._run_blender_script(zw_string)

    def _run_blender_script(self, zw_data):
        with tempfile.NamedTemporaryFile('w', suffix='.zw', delete=False) as zw_file:
            zw_file.write(zw_data)
            zw_path = zw_file.name

        output_path = zw_path + ".json"

        try:
            result = subprocess.run([
                self.blender_path,
                "--background",
                "--python", BLENDER_HELPER_SCRIPT_NAME,
                "--", zw_path, output_path
            ], capture_output=True, text=True, timeout=60)

            stdout, stderr = result.stdout, result.stderr
            return_code = result.returncode

            blender_results = []
            if os.path.exists(output_path):
                with open(output_path) as f:
                    blender_results = json.load(f)

            return {
                "status": "success" if return_code == 0 else "error",
                "return_code": return_code,
                "stdout": stdout,
                "stderr": stderr,
                "blender_results": blender_results,
                "temp_input": zw_path,
                "temp_output": output_path
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Timeout while running Blender"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# === ENGINE ROUTER ===
class DummyEngineRouter:
    def __init__(self):
        self.adapters = {}
        self.default_engine = None

    def register_adapter(self, adapter, is_default=False):
        name = adapter.name.lower()
        self.adapters[name] = adapter
        if is_default or self.default_engine is None:
            self.default_engine = name

    def route_zw_packet(self, zw_data, parsed_zw, target_engines=None, **kwargs):
        if not target_engines:
            target_engines = [self.default_engine]
        results = {}
        for engine_name in target_engines:
            adapter = self.adapters.get(engine_name)
            if not adapter:
                results[engine_name] = {"status": "error", "message": f"Adapter '{engine_name}' not found"}
                continue
            result = adapter.process_scene(parsed_zw)
            results[engine_name] = result
        return results

    def get_router_status(self):
        return {
            "registered_engines": len(self.adapters),
            "default_engine": self.default_engine,
            "engines": {name: adapter.get_status() for name, adapter in self.adapters.items()},
            "total_capabilities": sum(len(adapter.capabilities) for adapter in self.adapters.values())
        }

    def get_all_capabilities(self):
        return {name: adapter.capabilities for name, adapter in self.adapters.items()}

engine_router = DummyEngineRouter()
blender_adapter = BlenderAdapterDaemon(blender_path=DEFAULT_BLENDER_EXEC)
engine_router.register_adapter(blender_adapter, is_default=True)

# === MODELS ===
class ZWRequest(BaseModel):
    zw_data: str
    route_to_blender: bool = False
    blender_path: str | None = None
    target_engines: list[str] | None = None

# === ROUTES ===
@app.post("/process_zw")
async def process_zw(req: ZWRequest):
    logger.info("[ZW PROCESS] Processing new ZW packet")
    logger.info("Route to Blender: %s", req.route_to_blender)

    try:
        cleaned_zw = req.zw_data.strip()
        if cleaned_zw.startswith("```yaml"):
            cleaned_zw = cleaned_zw.replace("```yaml", "").replace("```", "").strip()

        parsed_zw = yaml.safe_load(cleaned_zw)

        result = engine_router.route_zw_packet(
            zw_data=req.zw_data,
            parsed_zw=parsed_zw,
            target_engines=req.target_engines,
            blender_path=req.blender_path
        )

        return JSONResponse(content={
            "status": "processed",
            "results": result,
            "received_length": len(req.zw_data),
            "parsed_sections": list(parsed_zw.keys()) if isinstance(parsed_zw, dict) else [],
            "timestamp": str(datetime.datetime.now())
        })

    except Exception as e:
        logger.exception("Error during ZW processing")
        return JSONResponse(content={
            "status": "error",
            "message": str(e)
        }, status_code=500)

@app.get("/asset_source_statuses")
async def asset_statuses():
    logger.info("[ASSET STATUS] Requested asset service status")
    services = {
        "polyhaven": {"enabled": True, "message": "Polyhaven asset service is available."},
        "sketchfab": {"enabled": False, "message": "Sketchfab integration disabled in dev mode."},
        "internalLibrary": {"enabled": True, "message": "Internal asset library is accessible."}
    }
    return JSONResponse(content={
        "services": services,
        "timestamp": str(datetime.datetime.now()),
        "multi_engine_router": engine_router.get_router_status()
    })

@app.get("/engines")
async def get_engines():
    logger.info("[ENGINES] Engine status requested")
    router_status = engine_router.get_router_status()
    capabilities = engine_router.get_all_capabilities()
    return JSONResponse(content={
        "router_status": router_status,
        "capabilities": capabilities,
        "timestamp": str(datetime.datetime.now())
    })

@app.get("/debug/zw_parse")
async def debug_zw_parser(zw: str):
    try:
        parsed = yaml.safe_load(zw)
        return {"parsed": parsed, "valid_keys": list(parsed.keys()) if isinstance(parsed, dict) else []}
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
async def root():
    logger.info("[BOOT] EngAIn-ZW Daemon started on port 1111")
    return {
        "message": "Unified EngAIn-ZW Daemon active",
        "router_status": engine_router.get_router_status()
    }

if __name__ == "__main__":
    uvicorn.run("zw_transformer_daemon:app", host="127.0.0.1", port=1111, reload=True)


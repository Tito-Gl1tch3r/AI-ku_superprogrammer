"""Family registry: discovers Family subclasses across generator modules."""
from __future__ import annotations

import importlib

FAMILY_MODULES = [
    "generators.write.python_families",
    "generators.write.sql_families",
    "generators.write.bash_families",
    "generators.write.c_families",
    "generators.write.cpp_families",
    "generators.write.java_families",
    "generators.write.javascript_families",
    "generators.write.typescript_families",
    "generators.write.php_families",
    "generators.write.rust_families",
    "generators.write.go_families",
    "generators.write.html_families",
    "generators.write.css_families",
    "generators.write.powershell_families",
    "generators.media.families",
    "generators.game.families",
]

# Families that belong to the media / game-engineering datasets.
DATASET_FAMILIES = {
    "AI-ku_superprogrammer_media": ("media_timeline_easing", "media_frame_renderer",
                                    "media_audio_analysis", "media_ts_logic",
                                    "media_glsl_shaders", "media_project_multifile"),
    "AI-ku_superprogrammer_game_engineering": ("game_binary_formats",
                                               "game_coord_conversion",
                                               "game_sprite_atlas", "game_script_vm",
                                               "game_mod_plugin_system",
                                               "game_interop_project"),
}


def dataset_for_family(name: str) -> str:
    for ds, names in DATASET_FAMILIES.items():
        if name in names:
            return ds
    return "AI-ku_superprogrammer_write"

_cache = None


def all_families():
    global _cache
    if _cache is None:
        out = []
        for mod_name in FAMILY_MODULES:
            try:
                mod = importlib.import_module(mod_name)
            except ImportError:
                continue  # optional family packs (e.g. toolchain-specific)
            for fam in getattr(mod, "__families__", []):
                out.append(fam)
        _cache = out
    return _cache


def families_for_language(language: str):
    return [f for f in all_families() if f.LANGUAGE == language]


def family_by_name(name: str):
    for f in all_families():
        if f.NAME == name:
            return f
    return None

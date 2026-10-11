"""Family registry: discovers Family subclasses across generator modules."""
from __future__ import annotations

import importlib

FAMILY_MODULES = [
    "generators.write.python_families",
    "generators.write.bases_families",
    "generators.write.craft_families",
    "generators.write.verify_families",
    "generators.write.systems_families",
    "generators.write.re_families",
    "generators.write.ops_families",
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
    "generators.write.evolution_families",
    "generators.write.verification_craft",
    "generators.media.families",
    "generators.media.video_families",
    "generators.media.ts_video_families",
    "generators.media.ts_beat_families",
    "generators.media.video_verify_family",
    "generators.media.ts_project_family",
    "generators.media.opus_families",
    "generators.game.families",
    "generators.game.modding_families",
    "generators.game.crossover_families",
]

# Families that belong to the media / game-engineering datasets.
DATASET_FAMILIES = {
    "AI-ku_superprogrammer_media": ("media_timeline_easing", "media_frame_renderer",
                                    "media_audio_analysis", "media_ts_logic",
                                    "media_glsl_shaders", "media_project_multifile",
                                    "media_mv_scene_engine", "media_mv_karaoke",
                                    "media_mv_project", "media_mv_post_chain",
                                    "media_mv_line_batch", "media_mv_shot_reads",
                                    "media_ts_theme", "media_ts_motion_rules",
                                    "media_ts_deterministic_render",
                                    "media_ts_beat_grid", "media_render_verify",
                                    "media_ts_mv_project"),
    "AI-ku_superprogrammer_game_engineering": ("game_binary_formats",
                                               "game_coord_conversion",
                                               "game_sprite_atlas", "game_script_vm",
                                               "game_mod_plugin_system",
                                               "game_interop_project",
                                               "game_engine_recon",
                                               "game_save_backup",
                                               "game_publish_lint",
                                               "game_oracle_replay",
                                               "game_crossover_bridge",
                                               "game_state_scan"),
    "AI-ku_superprogrammer_reverse_engineering": (
        "re_elf_parser", "re_disasm_analysis", "re_blackbox_reimpl",
        "re_version_diff", "re_strings_decode"),
    "AI-ku_superprogrammer_agent_ops": (
        "ops_monitor_watchdog", "ops_two_stage_orchestrator",
        "ops_progress_supervisor", "ops_scope_elevation",
        "ops_goal_decomposition", "ops_failure_autopsy",
        "ops_done_criteria"),
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

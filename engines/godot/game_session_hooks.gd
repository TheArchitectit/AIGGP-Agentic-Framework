extends Node
# spec: session-01, session-02, session-03, session-04, session-06
## GameSessionHooks — Godot runtime adapter for `aiggp.session/v1`.
##
## Thin 3-step adapter on the play side:
##   1. Construct the runtime `aiggp.session/v1` (`kind: "play"`) manifest from
##      the game's runtime configuration.
##   2. Invoke `<devgate>/scripts/game_session_start.py` (`--manifest <tmp> --root <root>`).
##      The brain evaluates `scene-inventory-report.json` when present (or
##      this hook runs `scene_inventory.py --write-report` beforehand when
##      `evaluate_screen_inventory` is true).
##   3. Exit 0 -> log the advisory block and opt-in wire `radredeye_capture`
##      when `capture.stream_id` is non-empty; exit 2 or 1 -> push_error and
##      refuse the play session (`get_tree().quit(exit_code)` when `quit_on_refusal`
##      is enabled).
##
## Zero business logic lives here: schema validation, determinism enforcement,
## advisory formatting, and `.guardrails/sessions.jsonl` appending all stay in
## `scripts/game_session_start.py`.

signal session_accepted(manifest: Dictionary, advisory: String)
signal session_refused(exit_code: int, message: String)

const SCHEMA_ID: String = "aiggp.session/v1"
const REDEYE_AUTOSAVE_PATH: String = "res://addons/radredeye_capture/screenshot_autosave.gd"

@export var auto_start_on_ready: bool = false
@export var game_slug: String = ""
@export var phase: String = "alpha"
@export var session_seed: String = ""
@export var build_id: String = ""
@export var capture_stream_id: String = ""
@export var capture_review: bool = false
@export var evaluate_screen_inventory: bool = true
@export var quit_on_refusal: bool = true
@export var python_executable: String = "python3"

var last_exit_code: int = -1
var last_advisory: String = ""
var last_manifest: Dictionary = {}
var capture_node: Node = null


func _ready() -> void:
	if auto_start_on_ready:
		start_play_session()


func resolve_project_root() -> String:
	var root: String = ProjectSettings.globalize_path("res://")
	if root.ends_with("/"):
		root = root.left(root.length() - 1)
	return root


func resolve_devgate_script(project_root: String, script_name: String) -> String:
	var sub_path: String = project_root.path_join(".devgate/scripts/" + script_name)
	if FileAccess.file_exists(sub_path):
		return sub_path
	var direct_path: String = project_root.path_join("scripts/" + script_name)
	if FileAccess.file_exists(direct_path):
		return direct_path
	return sub_path


func build_play_manifest(overrides: Dictionary = {}) -> Dictionary:
	var slug: String = String(overrides.get("game", game_slug)).strip_edges()
	if slug == "":
		slug = String(ProjectSettings.get_setting("application/config/name", "game")).to_lower().replace(" ", "")
	var ver_info: Dictionary = Engine.get_version_info()
	var godot_ver: String = "%d.%d" % [int(ver_info.get("major", 4)), int(ver_info.get("minor", 0))]
	var opened_at: String = String(overrides.get("opened_at", ""))
	if opened_at == "":
		opened_at = Time.get_datetime_string_from_system(true, false) + "Z"
	var manifest: Dictionary = {
		"schema": SCHEMA_ID,
		"kind": "play",
		"game": slug,
		"opened_at": opened_at,
		"opened_by": String(overrides.get("opened_by", "runtime:godot-" + godot_ver)),
	}
	var ph: String = String(overrides.get("phase", phase)).strip_edges()
	if ph != "":
		manifest["phase"] = ph
	var seed_val: String = String(overrides.get("seed", session_seed))
	if overrides.has("seed") or seed_val != "":
		manifest["seed"] = seed_val
	var scene_val: String = String(overrides.get("scene", ""))
	if scene_val == "" and get_tree() != null and get_tree().current_scene != null:
		scene_val = get_tree().current_scene.scene_file_path
	if scene_val == "":
		scene_val = String(ProjectSettings.get_setting("application/run/main_scene", ""))
	if scene_val != "":
		manifest["scene"] = scene_val
	var bld: String = String(overrides.get("build", build_id)).strip_edges()
	if bld != "":
		manifest["build"] = bld
	if overrides.has("capture") and overrides["capture"] is Dictionary:
		manifest["capture"] = overrides["capture"]
	elif capture_stream_id.strip_edges() != "":
		manifest["capture"] = {
			"stream_id": capture_stream_id.strip_edges(),
			"review": bool(overrides.get("capture_review", capture_review)),
		}
	return manifest


func start_play_session(overrides: Dictionary = {}) -> int:
	var project_root: String = String(overrides.get("project_root", resolve_project_root()))
	last_manifest = build_play_manifest(overrides)

	if evaluate_screen_inventory:
		var inv_script: String = resolve_devgate_script(project_root, "scene_inventory.py")
		if FileAccess.file_exists(inv_script):
			var inv_out: Array = []
			OS.execute(python_executable, [inv_script, "--root", project_root, "--write-report"], inv_out, true)

	var brain_script: String = resolve_devgate_script(project_root, "game_session_start.py")
	var tmp_manifest: String = OS.get_user_data_dir().path_join("aiggp_play_session_manifest.json")
	var fh: FileAccess = FileAccess.open(tmp_manifest, FileAccess.WRITE)
	if fh == null:
		last_exit_code = 1
		last_advisory = "game-session-start: cannot write temporary manifest: " + tmp_manifest
		push_error(last_advisory)
		session_refused.emit(last_exit_code, last_advisory)
		return last_exit_code
	fh.store_string(JSON.stringify(last_manifest))
	fh.close()

	var output: Array = []
	last_exit_code = OS.execute(
		python_executable,
		[brain_script, "--manifest", tmp_manifest, "--root", project_root],
		output,
		true
	)
	DirAccess.remove_absolute(tmp_manifest)
	last_advisory = "\n".join(PackedStringArray(output)).strip_edges()

	if last_exit_code != 0:
		push_error("[GameSessionHooks] play session refused (exit %d): %s" % [last_exit_code, last_advisory])
		session_refused.emit(last_exit_code, last_advisory)
		if quit_on_refusal and get_tree() != null:
			get_tree().quit(last_exit_code)
		return last_exit_code

	print(last_advisory)
	_wire_optional_redeye_capture(last_manifest)
	session_accepted.emit(last_manifest, last_advisory)
	return 0


func _wire_optional_redeye_capture(manifest: Dictionary) -> void:
	if not manifest.has("capture") or not (manifest["capture"] is Dictionary):
		return
	var cap: Dictionary = manifest["capture"]
	var stream_id: String = String(cap.get("stream_id", "")).strip_edges()
	if stream_id == "":
		return
	var script_path: String = String(cap.get("addon_script", REDEYE_AUTOSAVE_PATH))
	if not ResourceLoader.exists(script_path):
		push_warning("[GameSessionHooks] capture stream '%s' requested, but %s is not installed" % [stream_id, script_path])
		return
	var script_res: Script = load(script_path) as Script
	if script_res == null:
		return
	capture_node = script_res.new()
	capture_node.name = "RadRedeyeCapture_" + stream_id
	capture_node.set("output_directory", "user://redeye_captures/" + stream_id)
	capture_node.set("enabled", true)
	add_child(capture_node)

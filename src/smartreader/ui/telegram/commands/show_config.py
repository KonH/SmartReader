"""TelegramShowConfigCommand — hierarchical inline-keyboard config editor."""
from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from ...commands import ShowConfigCommand
from ..common import run_async, async_send_buttons, async_send_text, send_action_menu
from ..state import TelegramSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState

logger = logging.getLogger(__name__)


class TelegramShowConfigCommand(ShowConfigCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "config"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return
        # Drain stale queue entries
        while not self._tg.add_step_queue.empty():
            self._tg.add_step_queue.get_nowait()
        self._tg.mode_state = "config"
        try:
            self._run_config_flow(sender_id)
        finally:
            self._tg.mode_state = ""
        send_action_menu(self._tg, sender_id)

    def _run_config_flow(self, sender_id: int) -> None:
        s = self._tg
        state = "root"
        section = ""
        section_data: dict = {}
        pipeline: list[dict] = []
        stage_idx = 0
        add_after = True
        new_stage_type = ""
        new_stage_params: dict = {}

        while True:
            if state == "root":
                self._send_root(sender_id)
                val = s.add_step_queue.get()
                if val is None or val == "__back__":
                    return
                if val == "sect:pipeline":
                    pipeline = self._read_pipeline()
                    state = "pipeline_list"
                elif val.startswith("sect:"):
                    section = val[5:]
                    section_data = self._read_section(section)
                    state = "section"

            elif state == "section":
                self._send_section(sender_id, section, section_data)
                val = s.add_step_queue.get()
                if val is None:
                    return
                if val == "__back__":
                    state = "root"
                    continue
                if val.startswith("key:"):
                    try:
                        key_idx = int(val[4:])
                    except ValueError:
                        continue
                    fields = self.SECTION_FIELDS.get(section, [])
                    if key_idx < 0 or key_idx >= len(fields):
                        continue
                    key, type_hint = fields[key_idx]
                    current_val = section_data.get(key)
                    self._send_key_edit_prompt(sender_id, key, current_val, type_hint)
                    text_val = s.add_step_queue.get()
                    if text_val is None:
                        return
                    if text_val == "__back__":
                        continue
                    if type_hint == "str" and text_val.strip() == "_":
                        section_data.pop(key, None)
                    else:
                        try:
                            section_data[key] = self._coerce(text_val.strip(), type_hint)
                        except (ValueError, TypeError) as exc:
                            run_async(s, async_send_text(
                                s, sender_id,
                                f"<b>Invalid value:</b> {html.escape(str(exc))}",
                                parse_mode="html",
                            ))
                            continue
                    is_cron = section == "common" and key == "cron_schedule"
                    self._write_section_and_restart(section, section_data, is_cron_change=is_cron)
                    run_async(s, async_send_text(
                        s, sender_id,
                        f"\u2713 <code>{html.escape(key)}</code> updated",
                        parse_mode="html",
                    ))
                    section_data = self._read_section(section)

            elif state == "pipeline_list":
                pipeline = self._read_pipeline()
                self._send_pipeline_list(sender_id, pipeline)
                val = s.add_step_queue.get()
                if val is None:
                    return
                if val == "__back__":
                    state = "root"
                    continue
                if val.startswith("stage:"):
                    try:
                        stage_idx = int(val[6:])
                    except ValueError:
                        continue
                    if stage_idx < 0 or stage_idx >= len(pipeline):
                        continue
                    state = "stage_view"

            elif state == "stage_view":
                stage = pipeline[stage_idx]
                stage_type = str(stage.get("type", ""))
                self._send_stage_view(sender_id, stage_idx, stage, pipeline)
                val = s.add_step_queue.get()
                if val is None:
                    return
                if val == "__back__":
                    state = "pipeline_list"
                    continue
                if val == "action:edit":
                    if not self.STAGE_PARAMS.get(stage_type):
                        continue
                    state = "stage_param_list"
                elif val == "action:add_before":
                    add_after = False
                    state = "add_stage_type"
                elif val == "action:add_after":
                    add_after = True
                    state = "add_stage_type"
                elif val == "action:delete":
                    pipeline.pop(stage_idx)
                    self._write_pipeline_and_restart(pipeline)
                    run_async(s, async_send_text(s, sender_id, "\u2713 Stage deleted", parse_mode="html"))
                    state = "pipeline_list"

            elif state == "stage_param_list":
                stage = pipeline[stage_idx]
                stage_type = str(stage.get("type", ""))
                params = self.STAGE_PARAMS.get(stage_type, [])
                self._send_stage_param_list(sender_id, stage_idx, stage, params)
                val = s.add_step_queue.get()
                if val is None:
                    return
                if val == "__back__":
                    state = "stage_view"
                    continue
                if val.startswith("param:"):
                    try:
                        param_idx = int(val[6:])
                    except ValueError:
                        continue
                    if param_idx < 0 or param_idx >= len(params):
                        continue
                    param_name, default = params[param_idx]
                    type_hint = self._infer_type(default)
                    current = stage.get(param_name, default)
                    self._send_param_edit_prompt(sender_id, param_name, current, type_hint)
                    text_val = s.add_step_queue.get()
                    if text_val is None:
                        return
                    if text_val == "__back__":
                        continue
                    try:
                        pipeline[stage_idx][param_name] = self._coerce(text_val.strip(), type_hint)
                    except (ValueError, TypeError) as exc:
                        run_async(s, async_send_text(
                            s, sender_id,
                            f"<b>Invalid value:</b> {html.escape(str(exc))}",
                            parse_mode="html",
                        ))
                        continue
                    self._write_pipeline_and_restart(pipeline)
                    run_async(s, async_send_text(
                        s, sender_id,
                        f"\u2713 <code>{html.escape(param_name)}</code> updated",
                        parse_mode="html",
                    ))

            elif state == "add_stage_type":
                self._send_stage_type_buttons(sender_id)
                val = s.add_step_queue.get()
                if val is None:
                    return
                if val == "__back__":
                    state = "stage_view"
                    continue
                if val.startswith("type:"):
                    new_stage_type = val[5:]
                    default_params = self.STAGE_PARAMS.get(new_stage_type, [])
                    new_stage_params = {"type": new_stage_type}
                    for pname, pdefault in default_params:
                        new_stage_params[pname] = pdefault
                    state = "add_stage_confirm"

            elif state == "add_stage_confirm":
                self._send_add_stage_confirm(sender_id, new_stage_type, new_stage_params)
                val = s.add_step_queue.get()
                if val is None:
                    return
                if val == "__back__":
                    state = "add_stage_type"
                    continue
                if val == "__done__":
                    insert_idx = stage_idx + 1 if add_after else stage_idx
                    pipeline.insert(insert_idx, new_stage_params)
                    self._write_pipeline_and_restart(pipeline)
                    run_async(s, async_send_text(s, sender_id, "\u2713 Stage added", parse_mode="html"))
                    state = "pipeline_list"
                    continue
                if val.startswith("param:"):
                    default_params = self.STAGE_PARAMS.get(new_stage_type, [])
                    try:
                        param_idx = int(val[6:])
                    except ValueError:
                        continue
                    if param_idx < 0 or param_idx >= len(default_params):
                        continue
                    param_name, default = default_params[param_idx]
                    type_hint = self._infer_type(default)
                    current = new_stage_params.get(param_name, default)
                    self._send_param_edit_prompt(sender_id, param_name, current, type_hint)
                    text_val = s.add_step_queue.get()
                    if text_val is None:
                        return
                    if text_val == "__back__":
                        continue
                    try:
                        new_stage_params[param_name] = self._coerce(text_val.strip(), type_hint)
                    except (ValueError, TypeError) as exc:
                        run_async(s, async_send_text(
                            s, sender_id,
                            f"<b>Invalid value:</b> {html.escape(str(exc))}",
                            parse_mode="html",
                        ))

    # ── Display helpers ──────────────────────────────────────────────────────────

    def _send_root(self, sender_id: int) -> None:
        s = self._tg
        run_async(s, async_send_buttons(
            s, sender_id,
            "\u2699 <b>CONFIG</b> \u2014 select a section:",
            [
                [("inline", "COMMON", "cfg_sect:common")],
                [("inline", "SCORING", "cfg_sect:scoring")],
                [("inline", "TELEGRAM UI", "cfg_sect:telegram_ui")],
                [("inline", "TELEGRAM", "cfg_sect:telegram")],
                [("inline", "PIPELINE", "cfg_sect:pipeline")],
                [("inline", "\u2716 Cancel", "cfg_cancel")],
            ],
            parse_mode="html",
        ))

    def _send_section(self, sender_id: int, section: str, data: dict) -> None:
        s = self._tg
        fields = self.SECTION_FIELDS.get(section, [])
        lines = [f"\u2699 <b>{html.escape(section.upper())}</b>\n"]
        for i, (key, _) in enumerate(fields):
            val = data.get(key)
            val_str = f"<code>{html.escape(str(val))}</code>" if val is not None else "<i>(not set)</i>"
            lines.append(f"{i + 1}. <code>{html.escape(key)}</code> = {val_str}")
        text = "\n".join(lines)
        buttons: list[list[tuple[str, str, str]]] = []
        row: list[tuple[str, str, str]] = []
        for i in range(len(fields)):
            row.append(("inline", str(i + 1), f"cfg_key:{i}"))
            if len(row) == 5:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([("inline", "\u2190 Back", "cfg_back"), ("inline", "\u2716 Cancel", "cfg_cancel")])
        run_async(s, async_send_buttons(s, sender_id, text, buttons, parse_mode="html"))

    def _send_key_edit_prompt(self, sender_id: int, key: str, current: object, type_hint: str) -> None:
        s = self._tg
        cur_str = f"<code>{html.escape(str(current))}</code>" if current is not None else "<i>(not set)</i>"
        text = (
            f"<b>{html.escape(key)}</b> ({type_hint})\n"
            f"Current: {cur_str}\n\n"
            "Send new value, or <code>_</code> to clear this field."
        )
        run_async(s, async_send_buttons(
            s, sender_id, text,
            [[("inline", "\u2190 Back", "cfg_back"), ("inline", "\u2716 Cancel", "cfg_cancel")]],
            parse_mode="html",
        ))

    def _send_pipeline_list(self, sender_id: int, pipeline: list[dict]) -> None:
        s = self._tg
        if pipeline:
            lines = ["\u2699 <b>PIPELINE</b>\n"]
            for i, stage in enumerate(pipeline):
                stage_type = html.escape(str(stage.get("type", "?")))
                params = {k: v for k, v in stage.items() if k != "type"}
                param_str = ", ".join(
                    f"{html.escape(k)}={html.escape(str(v))}" for k, v in params.items()
                )
                entry = f"{i + 1}. <code>{stage_type}</code>"
                if param_str:
                    entry += f" \u2014 {param_str}"
                lines.append(entry)
            text = "\n".join(lines)
        else:
            text = "\u2699 <b>PIPELINE</b>\n<i>(empty)</i>"
        buttons: list[list[tuple[str, str, str]]] = []
        row: list[tuple[str, str, str]] = []
        for i in range(len(pipeline)):
            row.append(("inline", str(i + 1), f"pl_stage:{i}"))
            if len(row) == 5:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([("inline", "\u2190 Back", "cfg_back"), ("inline", "\u2716 Cancel", "cfg_cancel")])
        run_async(s, async_send_buttons(s, sender_id, text, buttons, parse_mode="html"))

    def _send_stage_view(self, sender_id: int, idx: int, stage: dict, pipeline: list[dict]) -> None:
        s = self._tg
        stage_type = str(stage.get("type", ""))
        params = {k: v for k, v in stage.items() if k != "type"}
        lines = [f"\u2699 <b>Stage {idx + 1}: <code>{html.escape(stage_type)}</code></b>\n"]
        if params:
            for k, v in params.items():
                lines.append(f"  <code>{html.escape(k)}</code> = <code>{html.escape(str(v))}</code>")
        else:
            lines.append("  <i>(no params)</i>")
        text = "\n".join(lines)
        buttons: list[list[tuple[str, str, str]]] = []
        if self.STAGE_PARAMS.get(stage_type):
            buttons.append([("inline", "\u270f EDIT PARAMS", "pl_action:edit")])
        buttons.append([
            ("inline", "\u2190 ADD BEFORE", "pl_action:add_before"),
            ("inline", "ADD AFTER \u2192", "pl_action:add_after"),
        ])
        buttons.append([("inline", "\U0001f5d1 DELETE", "pl_action:delete")])
        buttons.append([("inline", "\u2190 Back", "cfg_back"), ("inline", "\u2716 Cancel", "cfg_cancel")])
        run_async(s, async_send_buttons(s, sender_id, text, buttons, parse_mode="html"))

    def _send_stage_param_list(
        self, sender_id: int, idx: int, stage: dict, params: list[tuple[str, object]]
    ) -> None:
        s = self._tg
        stage_type = str(stage.get("type", ""))
        lines = [f"\u2699 <b>Stage {idx + 1}: <code>{html.escape(stage_type)}</code> \u2014 params</b>\n"]
        for i, (pname, default) in enumerate(params):
            cur = stage.get(pname, default)
            lines.append(f"{i + 1}. <code>{html.escape(pname)}</code> = <code>{html.escape(str(cur))}</code>")
        text = "\n".join(lines)
        buttons: list[list[tuple[str, str, str]]] = []
        row: list[tuple[str, str, str]] = []
        for i in range(len(params)):
            row.append(("inline", str(i + 1), f"pl_param:{i}"))
            if len(row) == 5:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([("inline", "\u2190 Back", "cfg_back"), ("inline", "\u2716 Cancel", "cfg_cancel")])
        run_async(s, async_send_buttons(s, sender_id, text, buttons, parse_mode="html"))

    def _send_param_edit_prompt(self, sender_id: int, param_name: str, current: object, type_hint: str) -> None:
        s = self._tg
        cur_str = html.escape(str(current))
        text = (
            f"<b>{html.escape(param_name)}</b> ({type_hint})\n"
            f"Current: <code>{cur_str}</code>\n\n"
            "Send new value:"
        )
        run_async(s, async_send_buttons(
            s, sender_id, text,
            [[("inline", "\u2190 Back", "cfg_back"), ("inline", "\u2716 Cancel", "cfg_cancel")]],
            parse_mode="html",
        ))

    def _send_stage_type_buttons(self, sender_id: int) -> None:
        s = self._tg
        buttons: list[list[tuple[str, str, str]]] = [
            [("inline", st, f"pl_type:{st}")] for st in self.STAGE_PARAMS
        ]
        buttons.append([("inline", "\u2190 Back", "cfg_back"), ("inline", "\u2716 Cancel", "cfg_cancel")])
        run_async(s, async_send_buttons(
            s, sender_id, "Select stage type:", buttons, parse_mode="html",
        ))

    def _send_add_stage_confirm(self, sender_id: int, stage_type: str, params: dict) -> None:
        s = self._tg
        default_params = self.STAGE_PARAMS.get(stage_type, [])
        lines = [f"\u2699 <b>New stage: <code>{html.escape(stage_type)}</code></b>\n"]
        if default_params:
            for i, (pname, default) in enumerate(default_params):
                cur = params.get(pname, default)
                lines.append(f"{i + 1}. <code>{html.escape(pname)}</code> = <code>{html.escape(str(cur))}</code>")
        else:
            lines.append("  <i>(no params)</i>")
        text = "\n".join(lines)
        buttons: list[list[tuple[str, str, str]]] = []
        row: list[tuple[str, str, str]] = []
        for i in range(len(default_params)):
            row.append(("inline", str(i + 1), f"pl_param:{i}"))
            if len(row) == 5:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([("inline", "\u2705 CONFIRM", "cfg_done")])
        buttons.append([("inline", "\u2190 Back", "cfg_back"), ("inline", "\u2716 Cancel", "cfg_cancel")])
        run_async(s, async_send_buttons(s, sender_id, text, buttons, parse_mode="html"))

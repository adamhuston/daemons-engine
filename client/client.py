# client_flet/client.py
import json

import flet as ft
import websockets


WS_URL = "ws://127.0.0.1:8000/ws/game"


def main(page: ft.Page):
    page.title = "Dungeon Flet Stub"
    page.vertical_alignment = ft.MainAxisAlignment.START
    
    # Load custom fonts
    page.fonts = {
        "IM Fell English": "fonts/IM_Fell_English/IMFellEnglish-Regular.ttf",
        "IM Fell English Italic": "fonts/IM_Fell_English/IMFellEnglish-Italic.ttf",
        "Staatliches": "fonts/Staatliches/Staatliches-Regular.ttf",
    }
    
    # Set default font for the page (optional)
    page.theme = ft.Theme(font_family="IM Fell English")

    # UI controls - Column for colored log lines
    log_column = ft.Column([], scroll=ft.ScrollMode.AUTO, auto_scroll=True)
    output_view = ft.Container(
        content=log_column,
        expand=True,
        bgcolor=ft.Colors.BLACK,
        padding=10,
    )

    player_id_field = ft.TextField(
        label="Player ID (from /players)",
        width=400,
    )

    connect_button = ft.ElevatedButton("Connect", icon=ft.Icons.LOGIN)
    
    # HP status display
    hp_status = ft.Text(
        value="HP: --/--",
        color=ft.Colors.GREEN,
        weight=ft.FontWeight.BOLD,
        size=14,
        font_family="Staatliches",
    )
    
    command_field = ft.TextField(
        label="Command",
        hint_text='Type commands like "look", "north", or \'say hello\'',
        expand=True,
    )
    send_button = ft.ElevatedButton("Send", icon=ft.Icons.SEND)

    status_text = ft.Text(value="Not connected", color=ft.Colors.GREY)

    input_row = ft.Row([command_field, send_button])
    top_row = ft.Row([player_id_field, connect_button])
    status_row = ft.Row([status_text, hp_status], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    page.add(top_row, status_row, output_view, input_row)

    state: dict[str, object | None] = {
        "ws": None,
        "connected": False,
        "current_health": None,
        "max_health": None,
    }

    def parse_markdown_spans(text: str) -> list[ft.TextSpan]:
        """
        Parse simple markdown formatting in text and return TextSpans.
        Supports: **bold**, *italic*
        """
        spans = []
        i = 0
        current_text = ""
        
        while i < len(text):
            # Check for **bold**
            if i < len(text) - 1 and text[i:i+2] == '**':
                if current_text:
                    spans.append(ft.TextSpan(current_text))
                    current_text = ""
                # Find closing **
                end = text.find('**', i + 2)
                if end != -1:
                    bold_text = text[i+2:end]
                    spans.append(ft.TextSpan(bold_text, ft.TextStyle(weight=ft.FontWeight.BOLD)))
                    i = end + 2
                    continue
                else:
                    current_text += text[i]
                    i += 1
            # Check for *italic*
            elif text[i] == '*':
                if current_text:
                    spans.append(ft.TextSpan(current_text))
                    current_text = ""
                # Find closing *
                end = text.find('*', i + 1)
                if end != -1:
                    italic_text = text[i+1:end]
                    spans.append(ft.TextSpan(italic_text, ft.TextStyle(italic=True)))
                    i = end + 1
                    continue
                else:
                    current_text += text[i]
                    i += 1
            else:
                current_text += text[i]
                i += 1
        
        if current_text:
            spans.append(ft.TextSpan(current_text))
        
        return spans if spans else [ft.TextSpan(text)]

    def append_line(line: str, color: str = ft.Colors.WHITE) -> None:
        print(line)  # also to console
        
        # Split multi-line messages and format each line
        lines = line.split('\n')
        for single_line in lines:
            # Parse markdown formatting in the line
            spans = parse_markdown_spans(single_line)
            
            log_column.controls.append(
                ft.Text(
                    spans=spans,
                    selectable=True, 
                    color=color, 
                    size=12,
                    font_family="IM Fell English",  # Use the custom font
                )
            )
        page.update()

    async def connect_ws(player_id: str) -> None:
        if state["connected"]:
            append_line("[system] Already connected.")
            return

        url = f"{WS_URL}?player_id={player_id}"
        append_line(f"[system] Connecting to {url} ...")
        status_text.value = "Connecting..."
        page.update()

        try:
            ws = await websockets.connect(url)
        except Exception as e:
            append_line(f"[error] Could not connect: {e!r}")
            status_text.value = "Not connected"
            page.update()
            return

        state["ws"] = ws
        state["connected"] = True
        status_text.value = "Connected"
        append_line("[system] Connected. Sending 'look'...")
        page.update()

        # Auto-send look
        try:
            await ws.send(json.dumps({"type": "command", "text": "look"}))
        except Exception as e:
            append_line(f"[error] Failed to send initial 'look' command: {e!r}")

        try:
            async for raw in ws:
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    append_line(f"[error] Invalid JSON: {raw}", ft.Colors.RED)
                    continue

                ev_type = ev.get("type")
                text = ev.get("text")
                payload = ev.get("payload")

                if ev_type == "message" and text:
                    append_line(text)
                elif ev_type == "stat_update" and payload:
                    # Update HP display if health stats are in payload
                    if "current_health" in payload:
                        state["current_health"] = payload["current_health"]
                    if "max_health" in payload:
                        state["max_health"] = payload["max_health"]
                    
                    # Update HP status display
                    if state["current_health"] is not None and state["max_health"] is not None:
                        current = state["current_health"]
                        maximum = state["max_health"]
                        hp_status.value = f"HP: {current}/{maximum}"
                        
                        # Color code based on health percentage
                        health_pct = current / maximum if maximum > 0 else 0
                        if health_pct > 0.6:
                            hp_status.color = ft.Colors.GREEN
                        elif health_pct > 0.3:
                            hp_status.color = ft.Colors.YELLOW
                        else:
                            hp_status.color = ft.Colors.RED
                        
                        page.update()
                elif ev_type == "respawn_countdown":
                    # Respawn countdown is handled via message events, ignore the data event
                    pass
                else:
                    # Unknown event type - show for debugging
                    append_line(f"[event] {ev}", ft.Colors.GREY_700)
        except Exception as e:
            append_line(f"[error] WebSocket closed: {e!r}")
        finally:
            state["connected"] = False
            state["ws"] = None
            status_text.value = "Disconnected"
            append_line("[system] Disconnected.")
            page.update()

    async def send_command(cmd: str) -> None:
        ws = state["ws"]
        if not state["connected"] or ws is None:
            append_line("[system] Not connected.")
            return

        cmd = cmd.strip()
        if not cmd:
            return

        try:
            await ws.send(json.dumps({"type": "command", "text": cmd}))
        except Exception as e:
            append_line(f"[error] Failed to send: {e!r}", ft.Colors.RED)
        finally:
            command_field.value = ""
            command_field.focus()
            page.update()

    def connect_click(e: ft.ControlEvent) -> None:
        player_id = player_id_field.value.strip()
        if not player_id:
            append_line("[system] Enter a player ID from /players.")
            return

        page.run_task(connect_ws, player_id)

    def send_command_click(e: ft.ControlEvent) -> None:
        cmd = command_field.value
        page.run_task(send_command, cmd)

    def command_submit(e: ft.ControlEvent) -> None:
        cmd = command_field.value
        page.run_task(send_command, cmd)

    connect_button.on_click = connect_click
    send_button.on_click = send_command_click
    command_field.on_submit = command_submit

    command_field.focus()
    page.update()


if __name__ == "__main__":
    ft.app(target=main)

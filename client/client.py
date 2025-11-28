# client_flet/client.py
import json

import flet as ft
import websockets


WS_URL = "ws://127.0.0.1:8000/ws/game"


def main(page: ft.Page):
    page.title = "Dungeon Flet Stub"
    page.vertical_alignment = ft.MainAxisAlignment.START

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
    command_field = ft.TextField(
        label="Command",
        hint_text='Type commands like "look", "north", or \'say hello\'',
        expand=True,
    )
    send_button = ft.ElevatedButton("Send", icon=ft.Icons.SEND)

    status_text = ft.Text(value="Not connected", color=ft.Colors.GREY)

    input_row = ft.Row([command_field, send_button])
    top_row = ft.Row([player_id_field, connect_button])

    page.add(top_row, status_text, output_view, input_row)

    state: dict[str, object | None] = {
        "ws": None,
        "connected": False,
    }

    def append_line(line: str, color: str = ft.Colors.WHITE) -> None:
        print(line)  # also to console
        log_column.controls.append(
            ft.Text(line, selectable=True, color=color, size=12)
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
                append_line(f"[raw] {raw}", ft.Colors.GREY_700)
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    append_line(f"[error] Invalid JSON: {raw}", ft.Colors.RED)
                    continue

                ev_type = ev.get("type")
                text = ev.get("text")

                if ev_type == "message" and text:
                    append_line(text)
                else:
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
            append_line(f"[system] >> {cmd}", ft.Colors.GREY_700)
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

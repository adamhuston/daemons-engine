# client_flet/client.py
import json

import flet as ft
import httpx
import websockets

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws/game"
WS_AUTH_URL = "ws://127.0.0.1:8000/ws/game/auth"


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
    page.theme = ft.Theme(font_family="Consolas")

    # UI controls - Column for colored log lines
    log_column = ft.Column([], scroll=ft.ScrollMode.AUTO, auto_scroll=True)
    output_view = ft.Container(
        content=log_column,
        expand=True,
        bgcolor=ft.Colors.BLACK,
        padding=10,
    )

    # Auth mode toggle
    auth_mode = ft.Dropdown(
        label="Connection Mode",
        width=200,
        options=[
            ft.dropdown.Option("authenticated", "Authenticated (New)"),
            ft.dropdown.Option("legacy", "Legacy (player_id)"),
        ],
        value="authenticated",
    )

    # Legacy mode fields
    player_id_field = ft.TextField(
        label="Player ID (from /players)",
        width=400,
        visible=False,
    )

    # Auth mode fields
    username_field = ft.TextField(
        label="Username",
        width=200,
    )
    password_field = ft.TextField(
        label="Password",
        width=200,
        password=True,
        can_reveal_password=True,
    )

    login_button = ft.ElevatedButton("Login", icon=ft.Icons.LOGIN)
    register_button = ft.ElevatedButton("Register", icon=ft.Icons.PERSON_ADD)
    connect_button = ft.ElevatedButton(
        "Connect", icon=ft.Icons.PLAY_ARROW, disabled=True
    )

    # HP status display
    hp_status = ft.Text(
        value="HP: --/--",
        color=ft.Colors.GREEN,
        weight=ft.FontWeight.BOLD,
        size=14,
        font_family="Staatliches",
    )

    # User info display
    user_info = ft.Text(
        value="Not logged in",
        color=ft.Colors.GREY,
        size=12,
    )

    command_field = ft.TextField(
        label="Command",
        hint_text='Type commands like "look", "north", or \'say hello\'',
        expand=True,
    )
    send_button = ft.ElevatedButton("Send", icon=ft.Icons.SEND)

    status_text = ft.Text(value="Not connected", color=ft.Colors.GREY)

    input_row = ft.Row([command_field, send_button])
    auth_row = ft.Row([username_field, password_field, login_button, register_button])
    legacy_row = ft.Row([player_id_field, connect_button])
    mode_row = ft.Row([auth_mode, connect_button])
    status_row = ft.Row(
        [status_text, user_info, hp_status],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    page.add(mode_row, auth_row, legacy_row, status_row, output_view, input_row)

    state: dict[str, object | None] = {
        "ws": None,
        "connected": False,
        "current_health": None,
        "max_health": None,
        "access_token": None,
        "refresh_token": None,
        "user_id": None,
        "username": None,
        "role": None,
        "in_game": False,  # True once we're past character selection and in the game world
    }

    def update_mode_visibility(e=None):
        """Update UI based on connection mode."""
        is_auth = auth_mode.value == "authenticated"
        auth_row.visible = is_auth
        legacy_row.visible = not is_auth

        # Enable connect button based on mode
        if is_auth:
            connect_button.disabled = state["access_token"] is None
        else:
            connect_button.disabled = False
        page.update()

    auth_mode.on_change = update_mode_visibility
    update_mode_visibility()  # Initial setup

    async def do_login(username: str, password: str) -> bool:
        """Attempt to login and get access token."""
        append_line(f"[auth] Logging in as {username}...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/auth/login",
                    json={"username": username, "password": password},
                )

                if response.status_code == 200:
                    data = response.json()
                    state["access_token"] = data["access_token"]
                    state["refresh_token"] = data["refresh_token"]
                    state["user_id"] = data["user_id"]
                    state["username"] = data["username"]
                    state["role"] = data["role"]

                    user_info.value = (
                        f"Logged in as: {data['username']} ({data['role']})"
                    )
                    user_info.color = ft.Colors.GREEN
                    connect_button.disabled = False
                    append_line(
                        f"[auth] Login successful! Role: {data['role']}",
                        ft.Colors.GREEN,
                    )

                    page.update()

                    # Auto-connect to WebSocket after login
                    await connect_ws_auth()

                    return True
                else:
                    error = response.json().get("detail", "Login failed")
                    append_line(f"[auth] Login failed: {error}", ft.Colors.RED)
                    return False
        except Exception as e:
            append_line(f"[auth] Error: {e!r}", ft.Colors.RED)
            return False

    async def do_register(username: str, password: str) -> bool:
        """Register a new account."""
        append_line(f"[auth] Registering account: {username}...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/auth/register",
                    json={"username": username, "password": password},
                )

                if response.status_code == 200:
                    data = response.json()
                    append_line(
                        f"[auth] Account created! User ID: {data['user_id']}",
                        ft.Colors.GREEN,
                    )
                    append_line("[auth] Now logging in...", ft.Colors.GREY)
                    # Auto-login after registration
                    return await do_login(username, password)
                else:
                    error = response.json().get("detail", "Registration failed")
                    append_line(f"[auth] Registration failed: {error}", ft.Colors.RED)
                    return False
        except Exception as e:
            append_line(f"[auth] Error: {e!r}", ft.Colors.RED)
            return False

    # ---------- WebSocket Connection ----------

    async def connect_ws_auth() -> None:
        """Connect using authenticated WebSocket endpoint."""
        if state["connected"]:
            append_line("[system] Already connected.")
            return

        if not state["access_token"]:
            append_line("[system] Please login first.")
            return

        url = f"{WS_AUTH_URL}?token={state['access_token']}"
        append_line("[system] Connecting with authentication...")
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
        state["in_game"] = False  # Will become True when we get auth_success
        status_text.value = "Connected"
        page.update()

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

                if ev_type == "auth_success":
                    state["in_game"] = True
                    status_text.value = "Connected (In Game)"
                    append_line(
                        f"[auth] Connected as player {ev.get('player_id')}",
                        ft.Colors.GREEN,
                    )
                    page.update()
                elif ev_type == "character_menu":
                    # Server-side character selection menu
                    state["in_game"] = False
                    status_text.value = "Connected (Character Select)"
                    if text:
                        append_line(text, ft.Colors.CYAN)
                    page.update()
                elif ev_type == "error":
                    append_line(f"[error] {text}", ft.Colors.RED)
                elif ev_type == "message" and text:
                    append_line(text)
                elif ev_type == "stat_update" and payload:
                    if "current_health" in payload:
                        state["current_health"] = payload["current_health"]
                    if "max_health" in payload:
                        state["max_health"] = payload["max_health"]

                    if (
                        state["current_health"] is not None
                        and state["max_health"] is not None
                    ):
                        current = state["current_health"]
                        maximum = state["max_health"]
                        hp_status.value = f"HP: {current}/{maximum}"

                        health_pct = current / maximum if maximum > 0 else 0
                        if health_pct > 0.6:
                            hp_status.color = ft.Colors.GREEN
                        elif health_pct > 0.3:
                            hp_status.color = ft.Colors.YELLOW
                        else:
                            hp_status.color = ft.Colors.RED

                        page.update()
                elif ev_type == "quit":
                    # Graceful disconnect - server handles returning to character selection
                    # The server will send a new character_menu after quit
                    append_line(
                        "[system] Returning to character selection...", ft.Colors.CYAN
                    )
                    state["in_game"] = False
                    hp_status.value = "HP: --/--"
                    hp_status.color = ft.Colors.GREEN
                    status_text.value = "Connected (Character Select)"
                    page.update()
                elif ev_type == "respawn_countdown":
                    # Silently ignore - respawn info comes via message events
                    pass
                else:
                    append_line(f"[event] {ev}", ft.Colors.GREY_700)
        except Exception as e:
            append_line(f"[error] WebSocket closed: {e!r}")
        finally:
            state["connected"] = False
            state["ws"] = None
            state["in_game"] = False
            status_text.value = "Disconnected"
            append_line("[system] Disconnected.")
            page.update()

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
            if i < len(text) - 1 and text[i : i + 2] == "**":
                if current_text:
                    spans.append(ft.TextSpan(current_text))
                    current_text = ""
                # Find closing **
                end = text.find("**", i + 2)
                if end != -1:
                    bold_text = text[i + 2 : end]
                    spans.append(
                        ft.TextSpan(bold_text, ft.TextStyle(weight=ft.FontWeight.BOLD))
                    )
                    i = end + 2
                    continue
                else:
                    current_text += text[i]
                    i += 1
            # Check for *italic*
            elif text[i] == "*":
                if current_text:
                    spans.append(ft.TextSpan(current_text))
                    current_text = ""
                # Find closing *
                end = text.find("*", i + 1)
                if end != -1:
                    italic_text = text[i + 1 : end]
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
        lines = line.split("\n")
        for single_line in lines:
            # Parse markdown formatting in the line
            spans = parse_markdown_spans(single_line)

            log_column.controls.append(
                ft.Text(
                    spans=spans,
                    selectable=True,
                    color=color,
                    size=12,
                    font_family="Consolas",  # Option to use a custom font
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
        append_line("[system] Connected.")
        page.update()

        # Server sends initial room description via register_player, no need to send look

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
                    if (
                        state["current_health"] is not None
                        and state["max_health"] is not None
                    ):
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
                elif ev_type in ("npc_state", "room_state"):
                    # Internal state updates - silently ignore
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
        cmd = cmd.strip()
        if not cmd:
            return

        # Clear input field first
        command_field.value = ""
        command_field.focus()
        page.update()

        # All commands are sent to the server (both in-game and character selection)
        ws = state["ws"]
        if not state["connected"] or ws is None:
            append_line("[system] Not connected.")
            return

        try:
            await ws.send(json.dumps({"type": "command", "text": cmd}))
        except Exception as e:
            append_line(f"[error] Failed to send: {e!r}", ft.Colors.RED)

    def login_click(e: ft.ControlEvent) -> None:
        username = username_field.value.strip()
        password = password_field.value
        if not username or not password:
            append_line("[system] Enter username and password.")
            return
        page.run_task(do_login, username, password)

    def register_click(e: ft.ControlEvent) -> None:
        username = username_field.value.strip()
        password = password_field.value
        if not username or not password:
            append_line("[system] Enter username and password.")
            return
        if len(password) < 8:
            append_line("[system] Password must be at least 8 characters.")
            return
        page.run_task(do_register, username, password)

    def connect_click(e: ft.ControlEvent) -> None:
        if auth_mode.value == "authenticated":
            page.run_task(connect_ws_auth)
        else:
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

    login_button.on_click = login_click
    register_button.on_click = register_click
    connect_button.on_click = connect_click
    send_button.on_click = send_command_click
    command_field.on_submit = command_submit

    command_field.focus()
    page.update()


if __name__ == "__main__":
    ft.app(target=main)

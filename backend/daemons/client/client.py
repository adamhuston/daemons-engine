# Daemons reference client
import json
from pathlib import Path

import flet as ft
import httpx
import websockets

# Get the fonts directory relative to this module
_FONTS_DIR = Path(__file__).parent / "fonts"


def create_main(host: str = "127.0.0.1", port: int = 8000):
    """Create a main function with custom host/port."""
    base_url = f"http://{host}:{port}"
    ws_auth_url = f"ws://{host}:{port}/ws/game/auth"

    def main(page: ft.Page):
        page.title = "Dungeon Flet Stub"
        page.vertical_alignment = ft.MainAxisAlignment.START

        # Load custom fonts from package directory
        page.fonts = {
            "IM Fell English": str(_FONTS_DIR / "IM_Fell_English" / "IMFellEnglish-Regular.ttf"),
            "IM Fell English Italic": str(_FONTS_DIR / "IM_Fell_English" / "IMFellEnglish-Italic.ttf"),
            "Staatliches": str(_FONTS_DIR / "Staatliches" / "Staatliches-Regular.ttf"),
        }

        # Set default font for the page (optional)
        page.theme = ft.Theme(font_family="Consolas")
        page.bgcolor = ft.Colors.GREY_900
        page.scroll = None  # Disable scroll animations

        # UI controls - Column for colored log lines
        log_column = ft.Column([], scroll=ft.ScrollMode.AUTO, spacing=0, expand=True)
        output_view = ft.Container(
            content=log_column,
            expand=True,
            bgcolor=ft.Colors.GREY_900,
            padding=10,
            alignment=ft.alignment.bottom_left,
        )

        # Auth fields
        username_field = ft.TextField(
            label="Username",
            width=200,
            color=ft.Colors.WHITE,
        )
        password_field = ft.TextField(
            label="Password",
            width=200,
            password=True,
            can_reveal_password=True,
            color=ft.Colors.WHITE,
        )

        login_button = ft.ElevatedButton("Login", icon=ft.Icons.LOGIN)
        register_button = ft.ElevatedButton("Register", icon=ft.Icons.PERSON_ADD)

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
            color=ft.Colors.WHITE,
            size=12,
        )

        command_field = ft.TextField(
            label="Command",
            hint_text='Type commands like "look", "north", or \'say hello\'',
            expand=True,
            color=ft.Colors.WHITE,
        )
        send_button = ft.ElevatedButton("Send", icon=ft.Icons.SEND)

        status_text = ft.Text(value="Not connected", color=ft.Colors.WHITE)

        input_row = ft.Row([command_field, send_button])
        auth_row = ft.Row(
            [username_field, password_field, login_button, register_button]
        )
        status_row = ft.Row(
            [status_text, user_info, hp_status],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        output_row = ft.Row([output_view], expand=True)

        page.add(auth_row, status_row, output_row, input_row)

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
            "in_game": False,
        }

        async def do_login(username: str, password: str) -> bool:
            """Attempt to login and get access token."""
            append_line(f"[auth] Logging in as {username}...")

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{base_url}/auth/login",
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
                        f"{base_url}/auth/register",
                        json={"username": username, "password": password},
                    )

                    if response.status_code == 200:
                        data = response.json()
                        append_line(
                            f"[auth] Account created! User ID: {data['user_id']}",
                            ft.Colors.GREEN,
                        )
                        append_line("[auth] Now logging in...", ft.Colors.WHITE)
                        # Auto-login after registration
                        return await do_login(username, password)
                    else:
                        error = response.json().get("detail", "Registration failed")
                        append_line(
                            f"[auth] Registration failed: {error}", ft.Colors.RED
                        )
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

            url = f"{ws_auth_url}?token={state['access_token']}"
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
            state["in_game"] = False
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
                        if "health" in payload:
                            state["current_health"] = payload["health"]
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
                        append_line(
                            "[system] Returning to character selection...",
                            ft.Colors.CYAN,
                        )
                        state["in_game"] = False
                        hp_status.value = "HP: --/--"
                        hp_status.color = ft.Colors.GREEN
                        status_text.value = "Connected (Character Select)"
                        page.update()
                    elif ev_type == "respawn_countdown":
                        pass
                    elif ev_type in (
                        "cooldown_update",
                        "ability_cast_complete",
                        "resource_update",
                    ):
                        pass
                    else:
                        append_line(f"[event] {ev}", ft.Colors.GREY_300)
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
            """Parse simple markdown formatting in text and return TextSpans."""
            spans = []
            i = 0
            current_text = ""

            while i < len(text):
                if i < len(text) - 1 and text[i : i + 2] == "**":
                    if current_text:
                        spans.append(ft.TextSpan(current_text))
                        current_text = ""
                    end = text.find("**", i + 2)
                    if end != -1:
                        bold_text = text[i + 2 : end]
                        spans.append(
                            ft.TextSpan(
                                bold_text, ft.TextStyle(weight=ft.FontWeight.BOLD)
                            )
                        )
                        i = end + 2
                        continue
                    else:
                        current_text += text[i]
                        i += 1
                elif text[i] == "*":
                    if current_text:
                        spans.append(ft.TextSpan(current_text))
                        current_text = ""
                    end = text.find("*", i + 1)
                    if end != -1:
                        italic_text = text[i + 1 : end]
                        spans.append(
                            ft.TextSpan(italic_text, ft.TextStyle(italic=True))
                        )
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
            print(line)

            lines = line.split("\n")
            for single_line in lines:
                spans = parse_markdown_spans(single_line)

                log_column.controls.append(
                    ft.Text(
                        spans=spans,
                        selectable=True,
                        color=color,
                        size=12,
                        font_family="Consolas",
                    )
                )
            log_column.scroll_to(offset=-1, duration=50)
            page.update()

        async def send_command(cmd: str) -> None:
            cmd = cmd.strip()
            if not cmd:
                return

            command_field.value = ""
            command_field.focus()
            page.update()

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

        def connect_click(e: ft.ControlEvent) -> None:  # noqa: F841
            page.run_task(connect_ws_auth)

        def send_command_click(e: ft.ControlEvent) -> None:
            cmd = command_field.value
            page.run_task(send_command, cmd)

        def command_submit(e: ft.ControlEvent) -> None:
            cmd = command_field.value
            page.run_task(send_command, cmd)

        login_button.on_click = login_click
        register_button.on_click = register_click
        send_button.on_click = send_command_click
        command_field.on_submit = command_submit

        command_field.focus()
        page.update()

    return main


def run(host: str = "127.0.0.1", port: int = 8000):
    """Run the Flet client with the specified host and port."""
    main_func = create_main(host, port)
    ft.app(target=main_func)


if __name__ == "__main__":
    ft.app(target=create_main())

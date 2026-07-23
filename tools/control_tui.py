"""Textual control panel for Astrogato Vector with Podman."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, RichLog, Static

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGE_NAME = "astrogato-vector:local"
CONTAINER_NAME = "astrogato-vector"
HOST_PORT = 8501
CONTAINER_PORT = 8501
APP_URL = f"http://localhost:{HOST_PORT}/"


@dataclass(frozen=True)
class CommandSpec:
    title: str
    argv: tuple[str, ...]
    allow_failure: bool = False


@dataclass(frozen=True)
class StatusInfo:
    label: str
    color: str
    url: str | None = None


class AstrogatoVectorTUI(App[None]):
    """Local operations TUI for Podman build, run, browse and shutdown."""

    CSS = """
    Screen {
        background: #071017;
        color: #e6eef6;
    }

    Header {
        background: #0f2137;
        color: #f5f7fb;
    }

    #title {
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: #10243c;
        color: #ffffff;
    }

    #status {
        height: 3;
        padding: 1 2;
        background: #071017;
        border-top: solid #263847;
        border-bottom: solid #263847;
    }

    #body {
        height: 1fr;
    }

    #actions {
        width: 30;
        min-width: 26;
        padding: 2 2;
        border-right: solid #263847;
        background: #0b1620;
    }

    #actions Button {
        width: 100%;
        height: 3;
        margin-bottom: 1;
        text-style: bold;
    }

    #start-podman {
        background: #238bd0;
    }

    #build {
        background: #ffb13b;
        color: #08111a;
    }

    #run {
        background: #4bc96f;
        color: #08111a;
    }

    #browser {
        background: #238bd0;
    }

    #stop {
        background: #c43865;
    }

    #quit {
        background: #24394c;
    }

    #log-panel {
        width: 1fr;
        padding: 2 2;
    }

    #log-title {
        height: 2;
        text-style: bold;
    }

    RichLog {
        height: 1fr;
        background: #02070c;
        border: round #263847;
        padding: 1 2;
    }
    """

    BINDINGS = [
        ("q", "quit", "Cerrar"),
        ("r", "refresh_status", "Refrescar"),
        ("p", "toggle_dark", "Palette"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.busy = False
        self.active_process: asyncio.subprocess.Process | None = None
        self.container_log_process: asyncio.subprocess.Process | None = None
        self.container_log_task: asyncio.Task[None] | None = None
        self.current_url = APP_URL

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Astrogato Vector TUI", id="title")
        yield Static("Estado: verificando...", id="status")
        with Horizontal(id="body"):
            with Vertical(id="actions"):
                yield Button("Arrancar Podman", id="start-podman", variant="primary")
                yield Button("Construir imagen", id="build", variant="warning")
                yield Button("Levantar servidor", id="run", variant="success")
                yield Button("Abrir navegador", id="browser", variant="primary")
                yield Button("Apagar", id="stop", variant="error")
                yield Button("Cerrar", id="quit", variant="default")
            with Vertical(id="log-panel"):
                yield Static("Logs", id="log-title")
                yield RichLog(id="logs", markup=False, wrap=True, auto_scroll=True)
        yield Footer()

    async def on_mount(self) -> None:
        self.title = "Astrogato Vector TUI"
        self.sub_title = APP_URL
        self.log_line("TUI lista para operar Astrogato Vector.", "cyan")
        self.log_line(f"Raiz del proyecto: {PROJECT_ROOT}", "white")
        self.log_line(f"URL local: {APP_URL}", "white")
        self.set_interval(3.0, self.refresh_status)
        await self.refresh_status()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "start-podman":
            self.run_worker(self.start_podman(), exclusive=False)
        elif button_id == "build":
            self.run_worker(self.build_image(), exclusive=False)
        elif button_id == "run":
            self.run_worker(self.run_server(), exclusive=False)
        elif button_id == "browser":
            await self.open_browser()
        elif button_id == "stop":
            self.run_worker(self.stop_server(), exclusive=False)
        elif button_id == "quit":
            await self.action_quit()

    async def start_podman(self) -> None:
        await self.run_sequence(
            "Arrancar Podman",
            [CommandSpec("Arrancar maquina Podman", ("podman", "machine", "start"), allow_failure=True)],
        )
        if podman_is_ready():
            self.log_line("Podman esta disponible.", "green")
        else:
            self.log_line("Podman aun no responde. Revisa Docker/Podman Desktop o vuelve a intentar.", "red")
        await self.refresh_status()

    async def build_image(self) -> None:
        await self.run_sequence(
            "Construir Astrogato Vector",
            [
                CommandSpec(
                    "Construir imagen local",
                    ("podman", "build", "-t", IMAGE_NAME, "-f", "Dockerfile", "."),
                )
            ],
        )

    async def run_server(self) -> None:
        env_args = env_file_args()
        if env_args:
            self.log_line("Usando variables de .env para el contenedor.", "green")
        else:
            self.log_line("No encontre .env; el contenedor arrancara sin secretos locales.", "yellow")

        await self.run_sequence(
            "Levantar servidor",
            [
                CommandSpec(
                    "Liberar contenedor anterior",
                    ("podman", "rm", "-f", "--ignore", CONTAINER_NAME),
                    allow_failure=True,
                ),
                CommandSpec(
                    "Iniciar contenedor",
                    (
                        "podman",
                        "run",
                        "-d",
                        "--name",
                        CONTAINER_NAME,
                        "-p",
                        f"{HOST_PORT}:{CONTAINER_PORT}",
                        *env_args,
                        IMAGE_NAME,
                    ),
                ),
            ],
        )
        if container_is_running():
            await self.start_container_logs()
            url = await wait_for_reachable_url()
            if url is None:
                self.log_line("El contenedor esta arriba, pero aun no encuentro una URL alcanzable.", "yellow")
            else:
                self.current_url = url
                self.sub_title = url
                self.log_line(f"Servidor disponible en {url}", "green")
        await self.refresh_status()

    async def stop_server(self) -> None:
        await self.stop_container_logs()
        await self.run_sequence(
            "Apagar servidor",
            [
                CommandSpec(
                    "Detener y remover contenedor",
                    ("podman", "rm", "-f", "--ignore", CONTAINER_NAME),
                    allow_failure=True,
                )
            ],
        )

    async def run_sequence(self, title: str, commands: Iterable[CommandSpec]) -> None:
        if self.busy:
            self.log_line("Ya hay una operacion en curso.", "yellow")
            return

        self.busy = True
        self.set_action_buttons_disabled(True)
        self.log_line(f"Iniciando: {title}", "cyan")
        try:
            for command in commands:
                return_code = await self.run_command(command)
                if return_code != 0 and not command.allow_failure:
                    self.log_line(f"Operacion detenida por error en: {command.title}", "red")
                    return
            self.log_line(f"{title} terminado.", "green")
        finally:
            self.busy = False
            self.active_process = None
            self.set_action_buttons_disabled(False)
            await self.refresh_status()

    async def run_command(self, command: CommandSpec) -> int:
        self.log_line(f"$ {' '.join(command.argv)}", "bright_cyan")
        try:
            process = await asyncio.create_subprocess_exec(
                *command.argv,
                cwd=PROJECT_ROOT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError:
            self.log_line(f"No se encontro el comando: {command.argv[0]}", "red")
            return 127

        self.active_process = process
        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode(errors="replace").rstrip()
            if line:
                self.log_line(line, "white")

        return_code = await process.wait()
        color = "yellow" if command.allow_failure and return_code != 0 else ("green" if return_code == 0 else "red")
        self.log_line(f"Salida: {return_code}", color)
        return return_code

    async def start_container_logs(self) -> None:
        await self.stop_container_logs()
        self.log_line("Conectando logs del contenedor...", "cyan")
        try:
            process = await asyncio.create_subprocess_exec(
                "podman",
                "logs",
                "--follow",
                "--tail",
                "80",
                CONTAINER_NAME,
                cwd=PROJECT_ROOT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError:
            self.log_line("No se encontro podman para leer logs.", "red")
            return

        self.container_log_process = process
        self.container_log_task = asyncio.create_task(self.stream_container_logs(process))

    async def stream_container_logs(self, process: asyncio.subprocess.Process) -> None:
        if process.stdout is None:
            return
        try:
            async for raw_line in process.stdout:
                line = raw_line.decode(errors="replace").rstrip()
                if line:
                    self.log_line(f"[contenedor] {line}", "white")
            return_code = await process.wait()
            if self.container_log_process is process:
                self.log_line(f"Lectura de logs terminada. Salida: {return_code}", "yellow")
        except asyncio.CancelledError:
            raise
        finally:
            if self.container_log_process is process:
                self.container_log_process = None

    async def stop_container_logs(self) -> None:
        task = self.container_log_task
        process = self.container_log_process
        self.container_log_task = None
        self.container_log_process = None

        if process is not None and process.returncode is None:
            process.terminate()
            with suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=2)
            if process.returncode is None:
                process.kill()
                await process.wait()

        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def open_browser(self) -> None:
        url = await asyncio.to_thread(discover_reachable_url)
        if url is None:
            url = self.current_url
            self.log_line(f"No confirme healthcheck; intento abrir {url}", "yellow")
        else:
            self.current_url = url
            self.sub_title = url

        opened = webbrowser.open(url, new=2)
        if opened:
            self.log_line(f"Navegador abierto en {url}", "green")
        else:
            self.log_line(f"No pude abrir el navegador automaticamente. URL: {url}", "red")

    async def refresh_status(self) -> None:
        info = await asyncio.to_thread(read_status)
        status = self.query_one("#status", Static)
        if info.url is not None:
            self.current_url = info.url
            self.sub_title = info.url
        text = Text()
        text.append("Estado: ", style="bold white")
        text.append(info.label, style=f"bold {info.color}")
        text.append(f"  |  URL util: {self.current_url}  |  Imagen: {IMAGE_NAME}", style="white")
        status.update(text)

    async def action_refresh_status(self) -> None:
        await self.refresh_status()
        self.log_line("Estado actualizado.", "cyan")

    async def action_quit(self) -> None:
        await self.stop_container_logs()
        await self.terminate_active_process()
        self.exit()

    async def terminate_active_process(self) -> None:
        process = self.active_process
        if process is None or process.returncode is not None:
            return
        self.log_line("Cerrando operacion en curso...", "yellow")
        process.terminate()
        with suppress(TimeoutError):
            await asyncio.wait_for(process.wait(), timeout=3)
        if process.returncode is None:
            process.kill()
            await process.wait()

    def set_action_buttons_disabled(self, disabled: bool) -> None:
        for button_id in ("start-podman", "build", "run", "stop"):
            self.query_one(f"#{button_id}", Button).disabled = disabled

    def log_line(self, message: str, color: str = "white") -> None:
        logs = self.query_one("#logs", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")
        text = Text()
        text.append(timestamp, style="bold green")
        text.append("  ")
        text.append(message, style=color)
        logs.write(text)


def env_file_args() -> tuple[str, ...]:
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return ()
    return ("--env-file", ".env")


def podman_is_ready() -> bool:
    if shutil.which("podman") is None:
        return False
    result = run_capture(("podman", "info", "--format", "{{.Host.Os}}"), timeout=5)
    return result.returncode == 0


def container_is_running() -> bool:
    result = run_capture(
        ("podman", "inspect", "--format", "{{.State.Running}}", CONTAINER_NAME),
        timeout=5,
    )
    return result.returncode == 0 and result.stdout.strip().casefold() == "true"


def read_status() -> StatusInfo:
    if shutil.which("podman") is None:
        return StatusInfo("Podman no encontrado", "red")
    if not podman_is_ready():
        return StatusInfo("Podman no conectado", "red")

    state = container_state()
    if state == "running":
        url = discover_reachable_url()
        if url is not None:
            return StatusInfo("Servidor encendido", "green", url)
        return StatusInfo("Contenedor corriendo / Streamlit arrancando", "yellow")
    if state:
        return StatusInfo(f"Contenedor {state}", "yellow")
    return StatusInfo("Podman listo / servidor apagado", "cyan")


def container_state() -> str | None:
    result = run_capture(
        ("podman", "inspect", "--format", "{{.State.Status}}", CONTAINER_NAME),
        timeout=5,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


async def wait_for_reachable_url(timeout: float = 12.0) -> str | None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        url = await asyncio.to_thread(discover_reachable_url)
        if url is not None:
            return url
        await asyncio.sleep(0.5)
    return None


def discover_reachable_url() -> str | None:
    candidates = [APP_URL, *streamlit_network_urls_from_logs()]
    seen: set[str] = set()
    for url in candidates:
        normalized = normalize_base_url(url)
        if normalized in seen:
            continue
        seen.add(normalized)
        if streamlit_health_is_ok(normalized):
            return normalized
    return None


def streamlit_network_urls_from_logs() -> list[str]:
    result = run_capture(("podman", "logs", "--tail", "120", CONTAINER_NAME), timeout=5)
    if result.returncode != 0:
        return []

    urls: list[str] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("Network URL:"):
            continue
        _, value = stripped.split(":", maxsplit=1)
        url = value.strip()
        if url:
            urls.append(url)
    return urls


def normalize_base_url(url: str) -> str:
    return url if url.endswith("/") else f"{url}/"


def streamlit_health_is_ok(base_url: str) -> bool:
    health_url = f"{normalize_base_url(base_url)}_stcore/health"
    try:
        with urllib.request.urlopen(health_url, timeout=1.0) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def run_capture(argv: tuple[str, ...], timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 1, "", str(exc))


def smoke_test() -> int:
    required = [
        PROJECT_ROOT / "app.py",
        PROJECT_ROOT / "requirements.txt",
        PROJECT_ROOT / "Dockerfile",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        for path in missing:
            print(f"ERROR: falta {path}")
        return 1

    print("Smoke TUI OK")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Proyecto: {PROJECT_ROOT}")
    print(f"URL: {APP_URL}")
    print(f"Imagen: {IMAGE_NAME}")
    print(f"Contenedor: {CONTAINER_NAME}")
    if shutil.which("podman") is None:
        print("WARN: podman no esta en PATH")
    else:
        print("OK: podman esta en PATH")

    try:
        asyncio.run(textual_smoke_test())
    except Exception as exc:
        print(f"ERROR: textual headless - {exc}")
        return 1

    print("OK: textual headless")
    return 0


async def textual_smoke_test() -> None:
    app = AstrogatoVectorTUI()
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause(0.1)
        app.query_one("#status", Static)
        app.query_one("#logs", RichLog)
        assert len(list(app.query(Button))) == 6


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Valida imports y archivos basicos sin abrir la TUI.",
    )
    args = parser.parse_args()
    if args.smoke_test:
        return smoke_test()
    AstrogatoVectorTUI().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

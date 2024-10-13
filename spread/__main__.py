import inspect
import logging
import pathlib
import sys
from typing import Annotated, Optional

import typer

from loguru import logger
from paramiko.ssh_exception import SSHException
from rich.logging import RichHandler
from rich.progress import track, Progress, SpinnerColumn, TextColumn

from .pushing import RemoteServer
from .structures import Settings, ServerPushScripts

app = typer.Typer()

settings = Settings()

logger.remove()
logger.add(
    RichHandler(),
    level="INFO",
    format="{message}",
    diagnose=False,
    backtrace=False
)


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


def config_path_validate(value: pathlib.Path):
    if value is None and settings.config_path is None:
        raise typer.BadParameter("Missing config path")
    if value is None:
        return value
    if not value.is_file():
        raise typer.BadParameter("Non-exist config file")
    return value

def use_variant(scripts: ServerPushScripts, variant: str):
    if scripts.before_push is not None:
        scripts.before_push = scripts.before_push.with_name(f"{variant}-{scripts.before_push.name}")
    if scripts.after_push is not None:
        scripts.after_push = scripts.after_push.with_name(f'{variant}-{scripts.after_push.name}')

@app.command()
def push(
        servers: Annotated[list[str], typer.Argument(help="servers to publish the config")] = None,
        config_path: Annotated[
            Optional[pathlib.Path],
            typer.Option(
                "-c",
                "--config",
                "--config-path",
                help="config file path",
                callback=config_path_validate
            )
        ] = None,
        scripts_variant: Annotated[
            Optional[str],
            typer.Option(
                "-v",
                "--variant",
                help="script variant"
            )
        ] = None
):
    if scripts_variant is not None:
        for server in settings.servers.values():
            scripts = server.scripts.model_copy()
            use_variant(scripts, scripts_variant)
            server.scripts = scripts
        use_variant(settings.scripts, scripts_variant)

    targets = set()
    if servers is None:
        servers = settings.servers.keys()
    for server in servers:
        try:
            targets.add(settings.servers[server])
        except KeyError:
            raise TypeError(f"server `{server}` does not exist in config")

    config_path = config_path or settings.config_path

    if config_path is None:
        raise typer.BadParameter("No config file provided")
    if not config_path.is_file():
        raise typer.BadParameter("Non-exist config file")

    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
    ) as progress:
        with config_path.open("r", encoding='u8') as config_fp:
            successes = []
            failures = []
            for target in targets:
                if target.config_path is not None:
                    file_io = target.config_path.open("r", encoding="utf-8")
                else:
                    config_fp.seek(0)
                    file_io = config_fp
                logger.info(f"connecting to server `{target.name}`")
                task_id = progress.add_task(description=f"Pushing to {target.name}...", total=None)
                server = RemoteServer(target)
                try:
                    server.connect()
                    server.push_config(file_io, settings.target_path)
                    progress.remove_task(task_id)
                    successes.append(target.name)
                except SSHException as e:
                    logger.warning(f"cannot push to `{target.name}`: {{exc}}", exc=e)
                    progress.remove_task(task_id)
                    failures.append(target.name)
                    continue
            logger.info("successfully pushed to {}", successes)
            if failures:
                logger.info("failed to push to {}", failures)


if __name__ == "__main__":
    app()

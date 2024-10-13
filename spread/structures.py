import pathlib
from typing import Optional

from pydantic import BaseModel, conint
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource, PydanticBaseSettingsSource


class ServerPushScripts(BaseModel):
    before_push: Optional[pathlib.Path] = None
    after_push: Optional[pathlib.Path] = None
    script_executor: list[str] = ['/usr/bin/bash', '-c']


class ServerConf(BaseModel):
    name: Optional[str] = None
    host: str
    port: conint(ge=100, le=25565) = 22
    user: str
    password: Optional[str] = None
    key_path: Optional[pathlib.Path] = None
    key_passphrase: Optional[str] = None
    target_path: Optional[pathlib.PurePosixPath] = None
    config_path: Optional[pathlib.Path] = None
    scripts: Optional[ServerPushScripts] = None

    def __hash__(self):
        return hash((self.name, self.host, self.user))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(toml_file="config.toml")

    servers: dict[str, ServerConf] = {}
    target_path: pathlib.PurePosixPath  # The default remote push target directory
    config_path: Optional[pathlib.Path] = None  # The local config file to push
    scripts: Optional[ServerPushScripts] = None  # The global server push config

    def __init__(self):
        super().__init__()

        for name in self.servers.keys():
            server = self.servers[name]
            server.name = name

            if server.scripts is None:
                server.scripts = self.scripts
            else:
                if server.scripts.before_push is None:
                    server.scripts.before_push = self.scripts.before_push
                if server.scripts.after_push is None:
                    server.scripts.after_push = self.scripts.after_push
                if server.scripts.script_executor is None:
                    server.scripts.script_executor = self.scripts.script_executor

    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (TomlConfigSettingsSource(settings_cls),)

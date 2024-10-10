import pathlib
from typing import Optional

from pydantic import BaseModel, conint
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource, PydanticBaseSettingsSource


class ServerConf(BaseModel):
    name: Optional[str] = None
    host: str
    port: conint(ge=100, le=25565) = 22
    user: str
    password: Optional[str] = None
    key_path: Optional[pathlib.Path] = None
    key_passphrase: Optional[str] = None
    target_path: Optional[pathlib.PurePosixPath] = None

    def __hash__(self):
        return hash((self.name, self.host, self.user))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(toml_file="config.toml")

    servers: dict[str, ServerConf] = {}
    target_path: pathlib.PurePosixPath # The default remote push target directory
    config_path: Optional[pathlib.Path] = None # The local config file to push

    def __init__(self):
        super().__init__()

        for name in self.servers.keys():
            server = self.servers[name]
            server.name = name

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

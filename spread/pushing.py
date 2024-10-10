import pathlib
import random
import string
from typing import Optional, Tuple
from typing import IO

from loguru import logger
from fabric import Connection
from paramiko.pkey import PKey
from paramiko.ssh_exception import SSHException, PasswordRequiredException, AuthenticationException

from .structures import ServerConf

class RemoteServer:
    def __init__(self, server_conf: ServerConf):
        self.server_conf = server_conf
        self.connection: Optional[Connection] = None

    def connect(self):
        if self.connection is not None:
            raise RuntimeError("re-connect on a connected remote")
        server = self.server_conf
        try_next = True
        if server.key_path is not None:
            try:
                conn = connection_with_private_key(
                    (server.host, server.port),
                    server.user, server.key_path.open("r"), server.key_passphrase
                )
                conn.open()
            except AuthenticationException:
                logger.warning("failed to authenticate with private key")
                try_next = True
            except Exception:
                raise
            else:
                try_next = False
                self.connection = conn
        if try_next is True and server.password is not None:
            try:
                conn = connect_with_password(
                    (server.host, server.port),
                    server.user,
                    server.password
                )
                conn.open()
            except AuthenticationException:
                log.warning("failed to authenticate with password")
                try_next = True
            except Exception:
                raise
            else:
                try_next = False
                self.connection = conn
        if try_next is True:
            raise Exception("all authentication attempts failed")

    def ensure_connected(self):
        if self.connection is None:
            self.connect()

    def push_config(self, config_io: IO[str], default_target: pathlib.PurePosixPath):
        self.ensure_connected()
        logger.info(f"pushing config to server `{self.server_conf.name}`")
        if self.server_conf.target_path is not None:
            default_target = self.server_conf.target_path
        random_char = ''.join(random.choices(string.ascii_letters, k=4))
        tmp_path = pathlib.PurePosixPath("/tmp") / default_target.with_suffix(f".tmp{random_char}")
        self.connection.put(
            config_io,
            remote=str(tmp_path)
        )
        self.connection.run(f"sudo mv {str(tmp_path)} {str(default_target)}")


def connection_with_private_key(
        addr_info: Tuple[str, int],
        user: str,
        fp: IO[str],
        key_password: Optional[str] = None
) -> Connection:
    try:
        pkey = PKey.from_private_key(fp, key_password)
    except SSHException as e:
        raise ValueError(f"invalid key file: {e}") from e
    except PasswordRequiredException as e:
        raise ValueError("password is required") from e
    except IOError as e:
        raise Exception(f"error loading private key: {e}") from e

    return Connection(addr_info[0], user, addr_info[1], connect_kwargs={
        "pkey": pkey
    })


def connect_with_password(
        addr_info: Tuple[str, int],
        user: str,
        password: str
) -> Connection:
    return Connection(addr_info[0], user, addr_info[1], connect_kwargs={
        "password": password
    })

import pathlib
import random
import shlex
import string
from typing import IO
from typing import Optional, Tuple, Literal

from fabric import Connection
from loguru import logger
from paramiko.ssh_exception import SSHException, PasswordRequiredException, AuthenticationException

from .helpers import key_from_io
from .structures import ServerConf, ServerPushScripts


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
                    server.user, server.key_path.expanduser().open("rb"), server.key_passphrase
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
                logger.warning("failed to authenticate with password")
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

    @classmethod
    def try_run(cls, conn: Connection, scripts: Optional[ServerPushScripts], type: Literal['before', 'after']) -> bool:
        if scripts is None:
            return True

        executor = scripts.script_executor

        x_cmd = None

        match type:
            case 'before':
                if scripts.before_push is not None:
                    x_cmd = shlex.join([*executor, scripts.before_push.read_text("u8")])
            case 'after':
                if scripts.after_push is not None:
                    x_cmd = shlex.join([*executor, scripts.after_push.read_text("u8")])
            case invalid:
                raise ValueError(f"expect `type` is 'before' or 'after', received '{invalid}'")

        if x_cmd:
            result = conn.run(x_cmd)
            return result and result.ok

        return True

    def push_config(self, config_io: IO[str], default_target: pathlib.PurePosixPath):
        self.ensure_connected()

        logger.info(f"pushing config to server `{self.server_conf.name}`")

        if self.server_conf.target_path is not None:
            default_target = self.server_conf.target_path
        random_char = ''.join(random.choices(string.hexdigits, k=6))

        if not type(self).try_run(self.connection, self.server_conf.scripts, "before"):
            raise RuntimeError("cannot run push scripts `before`")

        tmp_path = pathlib.PurePosixPath("/tmp") / default_target.with_suffix(f".tmp{random_char}")

        self.connection.put(
            config_io,
            remote=str(tmp_path)
        )

        result = self.connection.sudo(f"mv {str(tmp_path)} {str(default_target)}")

        if result and not result.ok:
            raise RuntimeError(f"cannot move config to target directory: {result.stderr}")

        if not type(self).try_run(self.connection, self.server_conf.scripts, "after"):
            raise RuntimeError("cannot run push scripts `after`")


def connection_with_private_key(
        addr_info: Tuple[str, int],
        user: str,
        fp: IO[bytes],
        key_password: Optional[str] = None
) -> Connection:
    try:
        pkey = key_from_io(fp, key_password)
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

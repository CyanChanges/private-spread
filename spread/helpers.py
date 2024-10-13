from io import StringIO
from typing import IO

from cryptography.hazmat.primitives import serialization, asymmetric
from paramiko.pkey import PKey


def key_from_io(io: IO[bytes], passphrase=None) -> PKey:
    # Lazy import to avoid circular import issues
    from paramiko import DSSKey, RSAKey, Ed25519Key, ECDSAKey

    # Sort out cert vs key, i.e. it is 'legal' to hand this kind of API
    # /either/ the key /or/ the cert, when there is a key/cert pair.

    data = io.read()

    # Like OpenSSH, try modern/OpenSSH-specific key load first
    try:
        loaded = serialization.load_ssh_private_key(
            data=data, password=passphrase
        )
    # Then fall back to assuming legacy PEM type
    except ValueError:
        loaded = serialization.load_pem_private_key(
            data=data, password=passphrase
        )
    # TO_DO Python 3.10: match statement? (NOTE: we cannot use a dict
    # because the results from the loader are literal backend, eg openssl,
    # private classes, so isinstance tests work but exact 'x class is y'
    # tests will not work)
    # TO_DO: leverage already-parsed/math'd obj to avoid duplicate cpu
    # cycles? seemingly requires most of our key subclasses to be rewritten
    # to be cryptography-object-forward. this is still likely faster than
    # the old SSHClient code that just tried instantiating every class!
    key_class = None
    if isinstance(loaded, asymmetric.dsa.DSAPrivateKey):
        key_class = DSSKey
    elif isinstance(loaded, asymmetric.rsa.RSAPrivateKey):
        key_class = RSAKey
    elif isinstance(loaded, asymmetric.ed25519.Ed25519PrivateKey):
        key_class = Ed25519Key
    elif isinstance(loaded, asymmetric.ec.EllipticCurvePrivateKey):
        key_class = ECDSAKey
    else:
        raise ValueError("unknown key type")
    key = key_class.from_private_key(StringIO(data.decode('u8')), password=passphrase)
    return key

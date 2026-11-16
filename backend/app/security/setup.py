"""Issue a single-use recorder setup or password reset link on the server."""

from argparse import ArgumentParser
from urllib.parse import urlsplit

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.connection import create_sqlite_engine, start_write
from app.db.models import RecorderAccount, RecorderSession, utc_now
from app.security.recorder import SETUP_TTL, new_token, token_digest


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="e.g. https://preg.example.test")
    parser.add_argument("--reset", action="store_true", help="Revoke sessions and reset the password")
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if url.scheme not in {"http", "https"} or not url.hostname or url.path not in {"", "/"} or url.query or url.fragment:
        parser.error("Provide the origin of the recorder site")

    engine = create_sqlite_engine(Settings().database_path)
    token = new_token()
    with Session(engine) as db:
        start_write(db)
        account = db.get(RecorderAccount, 1)
        if account is None:
            account = RecorderAccount(id=1)
            db.add(account)
        if account.password_hash and not args.reset:
            parser.error("Recorder is already configured. Use --reset to replace the password.")
        if args.reset:
            account.password_hash = None
            db.execute(delete(RecorderSession))
        account.setup_hash = token_digest(token)
        account.setup_expires_at = utc_now() + SETUP_TTL
        db.commit()
    print(f"{args.base_url.rstrip('/')}/#setup={token}")


if __name__ == "__main__":
    main()

from db.base import Base
from db.session import engine


def init_db() -> None:
    import entities.chat_message  # noqa: F401
    import entities.chat_session  # noqa: F401
    import entities.user  # noqa: F401

    Base.metadata.create_all(bind=engine)
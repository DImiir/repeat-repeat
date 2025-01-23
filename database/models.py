from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db_session import SqlAlchemyBase


class UserORM(SqlAlchemyBase):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int]
    username: Mapped[str]

    dictionary: Mapped[list["DictionaryORM"]] = relationship(back_populates="user")
    statistics: Mapped[list["ResultsORM"]] = relationship(back_populates="user")


class DictionaryORM(SqlAlchemyBase):
    __tablename__ = 'words'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    language: Mapped[str]
    word: Mapped[str]
    translated_word: Mapped[str]

    user: Mapped["UserORM"] = relationship(back_populates="dictionary")


class ResultsORM(SqlAlchemyBase):
    __tablename__ = 'results'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    language: Mapped[str]
    type_of_tests: Mapped[int]
    result: Mapped[float]
    number_of_attempts: Mapped[int]

    user: Mapped["UserORM"] = relationship(back_populates="statistics")


class PhraseInfoORM(SqlAlchemyBase):
    __tablename__ = 'phrases'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phrase: Mapped[str]
    group: Mapped[str]



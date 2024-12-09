from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


DATABASE_URL = "sqlite:///db.sql"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class BlacklistDescription(Base):
    __tablename__ = "blacklist_description"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, unique=True, index=True)

class BlacklistTitle(Base):
    __tablename__ = "blacklist_title"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, unique=True, index=True)

class BlacklistLinks(Base):
    __tablename__ = "blacklist_links"
    id = Column(Integer, primary_key=True, index=True)
    link = Column(String, unique=True, index=True)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_all_blacklist_data(db: Session) -> dict:
    """Retrieve all blacklist data as a dictionary."""
    return {
        "descriptions": [desc.description for desc in db.query(BlacklistDescription).all()],
        "titles": [title.title for title in db.query(BlacklistTitle).all()],
        "links": [link.link for link in db.query(BlacklistLinks).all()],
    }

from sqlalchemy import Column, Integer, String
from app.db.session import Base
target_metadata = Base.metadata

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)  # nullable True si inscription par téléphone possible
    phone = Column(String, unique=True, nullable=True, index=True)  # téléphone optionnel, unique
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    role = Column(String, default="user")  

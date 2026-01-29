from sqlalchemy import Column, Integer, String , ForeignKey,Text,DateTime
from sqlalchemy import func
from database import Base  

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    password = Column(String(200))

class Chat_history(Base):
    __tablename__ ='ChatHistory'
    id=Column(Integer, primary_key=True, index=True)
    user_id =Column(Integer , ForeignKey("users.id"), nullable=True)
    question = Column(Text,nullable = False)
    answer = Column(Text, nullable=False)
    source = Column(String(20), default='general')
    created_at = Column(DateTime(timezone=True),server_default = func.now())

    

    

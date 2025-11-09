from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey
from typing import Optional
 
 
class Base(DeclarativeBase):
    pass
 
 #user database model
class UserDB(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    student_id: Mapped[str] = mapped_column(unique=True, nullable=False)
    projects: Mapped[list["ProjectDB"]] = relationship(back_populates="owner", cascade="all,delete-orphan")
 
 #project database model
class ProjectDB(Base):
    __tablename__ = "projects"
    project_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # <- Optional
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    owner: Mapped["UserDB"] = relationship(back_populates="projects")
 
 
# B) Independent table
class CourseDB(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(nullable=False) # required field
    credits: Mapped[int] = mapped_column(nullable=False) # required field
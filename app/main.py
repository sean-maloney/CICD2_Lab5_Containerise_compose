from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from .database import engine, SessionLocal
from .models import Base, UserDB, CourseDB, ProjectDB
from .schemas import (
UserCreate, UserRead, UserUpdate, ProjectUpdate,
CourseCreate, CourseRead,
ProjectCreate, ProjectRead,
ProjectReadWithOwner, ProjectCreateForUser
)
 
app = FastAPI()
Base.metadata.create_all(bind=engine)
 
def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()
 
def commit_or_rollback(db: Session, error_msg: str):
  try:
    db.commit()
  except IntegrityError:
    db.rollback()
    raise HTTPException(status_code=409, detail=error_msg)
 
  #checks health returns if ok
@app.get("/health")
def health():
  return {"status": "ok"}
 
# CORS (add this block)
app.add_middleware(
CORSMiddleware,
    allow_origins=["*"], # dev-friendly; tighten in prod
    allow_methods=["*"],
    allow_headers=["*"],
)
 
#Replacing @app.on_event("startup")
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield
    #Shutdown
    #Optionally close pools, flush queses, etc
    #SessionLocal.close_all()
 
def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()
 
#tests if we can connect to database, if not retry
def commit_or_rollback(db: Session, error_msg: str):
  try:
    db.commit()
  except IntegrityError:
    db.rollback()
    raise HTTPException(status_code=409, detail=error_msg)
 
 #checks health returns if ok
@app.get("/health")
def health():
  return {"status": "ok"}
 
#Courses create
@app.post("/api/courses", response_model=CourseRead, status_code=201, summary="You could adddetails")
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
  db_course = CourseDB(**course.model_dump())
  db.add(db_course)
  commit_or_rollback(db, "Course already exists")
  db.refresh(db_course)
  return db_course
 
 #get courses
@app.get("/api/courses", response_model=list[CourseRead])
def list_courses(limit: int = 10, offset: int = 0, db: Session = Depends(get_db)):
  stmt = select(CourseDB).order_by(CourseDB.id).limit(limit).offset(offset)
  return db.execute(stmt).scalars().all()
 
#Projects make
@app.post("/api/projects", response_model=ProjectRead, status_code=201)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    user = db.get(UserDB, project.owner_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
 
    proj = ProjectDB(
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
    )
    db.add(proj)
    try:
        db.commit()
        db.refresh(proj)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Project creation failed")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected: {e!s}")
 
 
    # Convert ORM -> Pydantic explicitly (sometimes fixes silent 500s)
    return ProjectRead.model_validate(proj)
 
#Put to update the projects info
@app.put("/api/projects/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, updated: ProjectCreate, db: Session = Depends(get_db)):
    project = db.query(ProjectDB).filter(ProjectDB.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
 
    project.name = updated.name
    project.description = updated.description
    project.owner_id = updated.owner_id
 
    try:
        db.commit()
        db.refresh(project)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Project already exists or owner invalid")
    return project
 
#patch to update the projects information for only 1 variable
@app.patch("/api/projects/{project_id}", response_model=ProjectRead)
def patch_project(project_id: int, updated: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(ProjectDB).filter(ProjectDB.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
 
    changes = updated.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(project, field, value)
 
    try:
        db.commit()
        db.refresh(project)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Project already exists or owner invalid")
    return project
 
 
 
# LIST
@app.get("/api/projects", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)):
    stmt = select(ProjectDB).order_by(ProjectDB.project_id)  # not ProjectDB.id
    return db.execute(stmt).scalars().all()
 
# GET ONE (with owner)
@app.get("/api/projects/{project_id}", response_model=ProjectReadWithOwner)
def get_project_with_owner(project_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(ProjectDB)
        .where(ProjectDB.project_id == project_id)           # not ProjectDB.id
        .options(selectinload(ProjectDB.owner))
    )
    proj = db.execute(stmt).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj
 
 
#Nested Routes
@app.get("/api/users/{user_id}/projects", response_model=list[ProjectRead])
def get_user_projects(user_id: int, db: Session = Depends(get_db)):
  stmt = select(ProjectDB).where(ProjectDB.owner_id == user_id)
  #space it out for debugging
  result = db.execute(stmt)
  rows = result.scalars().all()
  return rows
  #return db.execute(stmt).scalars().all()
 
@app.post("/api/users/{user_id}/projects", response_model=ProjectRead, status_code=201)
def create_user_project(user_id: int, project: ProjectCreateForUser, db: Session =
Depends(get_db)):
  user = db.get(UserDB, user_id)
  if not user:
    raise HTTPException(status_code=404, detail="User not found")
 
  proj = ProjectDB(
    name=project.name,
    description=project.description, # <-- set it
    owner_id=user_id
  )
  db.add(proj)
  commit_or_rollback(db, "Project creation failed")
  db.refresh(proj)
  return proj
 
#Users
@app.get("/api/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)):
  stmt = select(UserDB).order_by(UserDB.id)
  #Useful for debugging
  result = db.execute(stmt)
  users = result.scalars().all()
  return users
  #return list(db.execute(stmt).scalars())
 
@app.get("/api/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
  user = db.get(UserDB, user_id)
  if not user:
    raise HTTPException(status_code=404, detail="User not found")
  return user
 
@app.post("/api/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def add_user(payload: UserCreate, db: Session = Depends(get_db)):
  user = UserDB(**payload.model_dump())
  db.add(user)
  try:
    db.commit()
    db.refresh(user)
  except IntegrityError:
    db.rollback()
    raise HTTPException(status_code=409, detail="User already exists")
  return user
 
#Updates users and shows an error if user already exists
@app.put("/api/users/{student_id}", response_model=UserRead)
def update_user(student_id: str, updated_user: UserCreate, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.student_id == student_id).first()
 
    if not user:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")
 
    user.name = updated_user.name
    user.email = updated_user.email
    user.age = updated_user.age
    user.student_id = updated_user.student_id
 
    try:
      db.commit()
      db.refresh(user)
    except IntegrityError:
      db.rollback()
      raise HTTPException(status_code=409, detail="User already exists")
    return user
 
#PATCH for users this patch only updates when one variable is passed
@app.patch("/api/users/{student_id}", response_model=UserRead)
def update_user(student_id: str, updated_user: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.student_id == student_id).first()
 
    if not user:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")
 
    updates = updated_user.model_dump(exclude_unset=True, exclude_none=True)
 
    for key, value in updates.items():
      setattr(user, key, value)
 
    try:
      db.commit()
      db.refresh(user)
    except IntegrityError:
      db.rollback()
      raise HTTPException(status_code=409, detail="User already exists")
    return user
 
 
 
 
# DELETE a user (triggers ORM cascade -> deletes their projects too)
@app.delete("/api/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db)) -> Response:
  user = db.get(UserDB, user_id)
  if not user:
    raise HTTPException(status_code=404, detail="User not found")
  db.delete(user) # <-- triggers cascade="all, delete-orphan" on projects
  db.commit()
  return Response(status_code=status.HTTP_204_NO_CONTENT)
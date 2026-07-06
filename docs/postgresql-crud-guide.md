# PostgreSQL CRUD Guide for LexAI Backend

This project uses **SQLModel** (SQLAlchemy + Pydantic) with **PostgreSQL 17**
running in Docker. This guide covers how to create, read, update, and delete
records using the patterns already established in the codebase.

---

## 1. Database Connection

The database is configured in `db/session.py`:

```python
from sqlmodel import SQLModel, Session, create_engine
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")   # postgresql://postgres:postgres@localhost:5432/litigation

engine = create_engine(DATABASE_URL, echo=True)   # echo=True = SQL logging

def get_session():
    with Session(engine) as session:
        yield session
```

The session is injected into routes via FastAPI's `Depends`:

```python
@router.get("/cases/")
def list_cases(session: Session = Depends(get_session)):
    ...
```

---

## 2. Defining a Model (Table)

Models live in `db/models/`. Example: `db/models/case.py`:

```python
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class Case(SQLModel, table=True):
    __tablename__ = "cases"

    case_id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    case_name: str = Field(index=True)
    claim_type: Optional[str] = Field(default="")
    current_stage: Optional[str] = Field(default="draft")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

**Key points:**
- `table=True` makes it a database table (not just a Pydantic model)
- `primary_key=True` marks the auto-increment ID
- `foreign_key="users.id"` sets up a FK constraint
- `index=True` speeds up WHERE/ORDER BY on that column
- `Optional[str]` with a default means the column is nullable with a default value

---

## 3. CREATE (INSERT)

```python
from sqlmodel import Session
from db.models.case import Case

def create_case(session: Session, user_id: int, name: str) -> Case:
    case = Case(
        user_id=user_id,
        case_name=name,
        claim_type="Breach of Contract",
        current_stage="Discovery",
    )
    session.add(case)       # Stage the insert
    session.commit()        # Execute it
    session.refresh(case)   # Populate auto-generated fields (case_id, timestamps)
    return case
```

**With user input (as done in `routes/cases.py`):**

```python
@router.post("/cases/", status_code=201)
async def create_case(
    request: Request,
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),
):
    payload = await request.json()
    case = Case(
        user_id=user_id,
        case_name=payload.get("caseName"),
        claim_type=payload.get("claimType", ""),
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case
```

---

## 4. READ (SELECT)

### Get all records

```python
from sqlmodel import select

stmt = select(Case).where(Case.user_id == user_id).order_by(Case.updated_at.desc())
cases = session.exec(stmt).all()
```

### Get single record by primary key

```python
case = session.get(Case, case_id)
```

### Get single record by filter

```python
stmt = select(Case).where(Case.case_name == "Smith v. Acme").where(Case.user_id == user_id)
case = session.exec(stmt).first()   # Returns None if not found
```

### Count records

```python
from sqlalchemy import func

count = session.exec(
    select(func.count()).where(Case.user_id == user_id)
).one()
```

### Pagination

```python
stmt = select(Case).where(Case.user_id == user_id).offset(0).limit(20)
page = session.exec(stmt).all()
```

### Joins

```python
stmt = (
    select(Case, User)
    .join(User, Case.user_id == User.id)
    .where(Case.case_id == 123)
)
result = session.exec(stmt).first()  # returns (Case, User) tuple
```

---

## 5. UPDATE

### Update specific fields (PATCH pattern)

```python
case = session.get(Case, case_id)
if not case:
    raise HTTPException(status_code=404)

# Update only the fields that were provided
if "caseName" in payload:
    case.case_name = payload["caseName"]
if "claimType" in payload:
    case.claim_type = payload["claimType"]

case.updated_at = datetime.utcnow()
session.add(case)
session.commit()
session.refresh(case)
```

### Bulk update

```python
stmt = (
    update(Case)
    .where(Case.user_id == user_id)
    .values(current_stage="Archived")
)
session.exec(stmt)
session.commit()
```

---

## 6. DELETE

```python
case = session.get(Case, case_id)
if not case:
    raise HTTPException(status_code=404)

session.delete(case)
session.commit()
# Returns 204 No Content
```

### Bulk delete

```python
stmt = delete(Case).where(Case.user_id == user_id)
session.exec(stmt)
session.commit()
```

---

## 7. Raw SQL (when needed)

```python
from sqlmodel import text

# SELECT
result = session.exec(text("SELECT * FROM cases WHERE user_id = :uid"), {"uid": 1})
rows = result.all()

# DDL (ALTER TABLE, CREATE INDEX, etc.)
session.exec(text("CREATE INDEX IF NOT EXISTS idx_cases_name ON cases(case_name)"))
session.commit()
```

---

## 8. Migrations (Alembic)

This project uses Alembic for schema migrations. The config is in `alembic.ini`.

### Create a migration after changing a model

```bash
cd D:\Internship\backend
alembic revision --autogenerate -m "description of change"
```

### Apply migrations

```bash
alembic upgrade head
```

### Roll back one migration

```bash
alembic downgrade -1
```

### Check current state

```bash
alembic current
alembic history
```

---

## 9. Common Patterns in This Project

### Auth-protected CRUD (user-scoped)

```python
@router.get("/items/")
def list_items(
    session: Session = Depends(get_session),
    user_id: int = Depends(get_current_user),   # from JWT
):
    stmt = select(Item).where(Item.user_id == user_id)
    return session.exec(stmt).all()
```

### CamelCase JSON → snake_case DB mapping

The frontend uses camelCase. Map in your route:

```python
field_map = {
    "caseName": "case_name",
    "claimType": "claim_type",
    "createdAt": "created_at",
}
for json_key, db_field in field_map.items():
    if json_key in payload:
        setattr(case, db_field, payload[json_key])
```

### Transaction safety

```python
try:
    session.add(record)
    session.commit()
except Exception:
    session.rollback()
    raise
```

---

## 10. Quick Reference

| Operation | Code |
|-----------|------|
| **Create** | `session.add(obj)` → `session.commit()` → `session.refresh(obj)` |
| **Read all** | `session.exec(select(Model).where(...)).all()` |
| **Read one** | `session.get(Model, id)` or `session.exec(select(Model).where(...)).first()` |
| **Update** | `session.get(Model, id)` → modify attrs → `session.add(obj)` → `session.commit()` |
| **Delete** | `session.delete(obj)` → `session.commit()` |
| **Count** | `session.exec(select(func.count()).where(...)).one()` |
| **Raw SQL** | `session.exec(text("SELECT ..."))` |
| **Rollback** | `session.rollback()` |
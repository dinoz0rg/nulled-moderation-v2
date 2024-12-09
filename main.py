from fastapi import FastAPI, Form, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import get_db, BlacklistDescription, BlacklistTitle, BlacklistLinks
from nulled import monitor_forum
import threading
import uvicorn
from typing import Union
from datetime import datetime, timezone
from pydantic import BaseModel


class TableManager:
    """Handles CRUD operations for tables."""

    TABLE_MAP = {
        "description": BlacklistDescription,
        "title": BlacklistTitle,
        "links": BlacklistLinks,
    }

    def __init__(self, db: Session):
        self.db = db

    def get_all(self, table_name: str):
        """Retrieve all entries for a specified table."""
        table_model = self._get_table_model(table_name)
        return self.db.query(table_model).all()

    def add_entry(self, table_name: str, value: str):
        """Add a new entry to a specified table and return its ID."""
        table_model = self._get_table_model(table_name)
        new_entry = table_model(**{table_model.__table__.columns.keys()[1]: value})
        try:
            self.db.add(new_entry)
            self.db.commit()
            self.db.refresh(new_entry)
            return new_entry.id
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(status_code=400, detail=f"{table_name.capitalize()} already exists.")

    def edit_entry(self, table_name: str, id: Union[int, str], value: str):
        """Edit an existing entry or create a new one if id is 'new'."""
        table_model = self._get_table_model(table_name)

        if id == "new":
            self.add_entry(table_name, value)
            return {"status": "success", "message": "New entry added."}

        entry = self.db.query(table_model).filter(table_model.id == id).first()  # type: ignore
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found.")

        setattr(entry, table_model.__table__.columns.keys()[1], value)
        self.db.commit()
        return {"status": "success", "message": "Entry updated."}

    def _get_table_model(self, table_name: str):
        """Validate and retrieve the table model."""
        if table_name not in self.TABLE_MAP:
            raise HTTPException(status_code=400, detail="Invalid table name.")
        return self.TABLE_MAP[table_name]


class MonitorManager:
    """Manage the lifecycle of the monitor_forum thread."""
    def __init__(self):
        self.monitor_thread = None
        self.thread_running = False
        self.thread_lock = threading.Lock()

    def start(self, max_threads=5, page_range=3, cycle_delay=120):
        """Start the monitoring thread."""
        with self.thread_lock:
            if self.thread_running:
                raise HTTPException(status_code=400, detail="Monitor is already running.")
            self.thread_running = True
            self.monitor_thread = threading.Thread(
                target=self._run_monitor,
                args=(max_threads, page_range, cycle_delay),
                daemon=True
            )
            self.monitor_thread.start()
            return {"status": "success", "message": "Monitor started."}

    def stop(self):
        """Stop the monitoring thread."""
        with self.thread_lock:
            if not self.thread_running:
                raise HTTPException(status_code=400, detail="Monitor is not running.")
            self.thread_running = False

        if self.monitor_thread:
            self.monitor_thread.join(0)  # Ensure the thread stops cleanly
        return {"status": "success", "message": "Monitor stopped."}

    def _run_monitor(self, max_threads, page_range, cycle_delay):
        """Wrapper for monitor_forum to include a stop signal."""
        def stop_signal():
            return self.thread_running

        monitor_forum(max_threads=max_threads, page_range=page_range, cycle_delay=cycle_delay, stop_signal=stop_signal)



# Initialize FastAPI and MonitorManager
app = FastAPI()
monitor_manager = MonitorManager()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/js", StaticFiles(directory="js"), name="js")
templates = Jinja2Templates(directory="templates")
start_time = datetime.now(timezone.utc)


class HealthStatus(BaseModel):
    status: str
    duration: int


@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    """Render the management page."""
    table_manager = TableManager(db)
    data = {
        "descriptions": table_manager.get_all("description"),
        "titles": table_manager.get_all("title"),
        "links": table_manager.get_all("links"),
    }
    return templates.TemplateResponse("index.html", {"request": request, **data})


@app.get("/health", response_model=HealthStatus)
def health_check():
    """Perform a health check."""
    uptime_duration = datetime.now(timezone.utc) - start_time
    return {"status": "healthy", "duration": int(uptime_duration.total_seconds())}


@app.post("/start-monitor")
def start_monitor_endpoint(max_threads: int = 5, page_range: int = 3, cycle_delay: int = 120):
    """Endpoint to start the monitor with customizable parameters."""
    return monitor_manager.start(max_threads=max_threads, page_range=page_range, cycle_delay=cycle_delay)


@app.post("/stop-monitor")
def stop_monitor_endpoint():
    """Endpoint to stop the monitor."""
    return monitor_manager.stop()


@app.post("/edit/{table_name}/{id}")
async def edit_entry(table_name: str, id: Union[int, str], value: str = Form(...), db: Session = Depends(get_db)):
    """Edit or add table entry."""
    manager = TableManager(db)
    manager.edit_entry(table_name, id, value)
    return {"status": "success", "id": id, "value": value}


@app.post("/add/{table_name}")
async def add_entry(table_name: str, value: str = Form(...), db: Session = Depends(get_db)):
    """Add a new table entry and return its ID."""
    manager = TableManager(db)
    new_id = manager.add_entry(table_name, value)
    return {"status": "success", "id": new_id, "value": value}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
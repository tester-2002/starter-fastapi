from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

import os

app = FastAPI()

# Specify the path to the SQLite database file in the /tmp folder
db_path = os.path.join("/tmp", "database.sqlite3")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
# Session middleware for handling sessions
app.add_middleware(SessionMiddleware, secret_key="123456")

# Template setup
templates = Jinja2Templates(directory="templates")


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, nullable=False)
    vote = Column(Integer, nullable=False, default=0)


class Help(Base):
    __tablename__ = 'help'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), nullable=False)


# Create tables
Base.metadata.create_all(bind=engine)


@app.get("/")
async def home(request: Request):
    if "username" in request.session:
        username = request.session["username"]
        return templates.TemplateResponse("logged.html", {"request": request, "username": username})
    return HTMLResponse('You are not logged in | <a href="/login">Login</a>')


@app.post("/login")
async def login(username: str, request: Request):
    # Check if the user exists in the database
    user = SessionLocal().query(User).filter_by(username=username).first()

    if not user:
        # If the user does not exist, create a new user and add it to the database
        new_user = User(username=username, vote=0)
        SessionLocal().add(new_user)
        SessionLocal().commit()

    request.session["username"] = username
    return {"message": "Login successful"}


@app.get("/help_data")
async def help_data(request: Request):
    help_entries = SessionLocal().query(Help).all()
    data = [{"id": entry.id, "username": entry.username} for entry in help_entries]
    return templates.TemplateResponse("help_data.html", {"request": request, "data": data})


@app.get("/fetch_help_data")
async def fetch_help_data():
    help_entries = SessionLocal().query(Help).all()
    data = [{"id": entry.id, "username": entry.username} for entry in help_entries]
    return {"data": data}


@app.post("/help")
async def help(request: Request):
    if "username" in request.session:
        current_username = request.session["username"]
        help_entry = Help(username=current_username)
        SessionLocal().add(help_entry)
        SessionLocal().commit()
        return {"message": "Help requested successfully"}
    return {"message": "User not logged in"}


@app.delete("/delete_help_request/{help_id}")
async def delete_help_request(help_id: int):
    try:
        # Delete the help request from the database
        help_entry = SessionLocal().query(Help).get(help_id)
        if help_entry:
            SessionLocal().delete(help_entry)
            SessionLocal().commit()

            # Return success response
            return {"message": "Help request deleted successfully"}
        else:
            # Return error response if help entry is not found
            raise HTTPException(status_code=404, detail="Help request not found")
    except Exception as e:
        # Return error response if there's any issue with deletion
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/clear_all_help_requests")
async def clear_all_help_requests():
    try:
        # Clear all help requests from the database
        SessionLocal().query(Help).delete()
        SessionLocal().commit()

        # Return success response
        return {"message": "All help requests cleared successfully"}
    except Exception as e:
        # Return error response if there's any issue with clearing
        raise HTTPException(status_code=500, detail=str(e))


@app.route("/logout")
def logout(request: Request):
    request.session.pop("username", None)
    return redirect(url_for("home"))


@app.route("/graph")
def graph(request: Request):
    return templates.TemplateResponse("graph.html", {"request": request})


@app.route("/get_votes_count")
def get_votes_count():
    count_0 = SessionLocal().query(User).filter_by(vote=0).count()
    count_1 = SessionLocal().query(User).filter_by(vote=1).count()
    return {"0": count_0, "1": count_1}


# WebSocket handling
class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_message(f"Client {client_id}: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client {client_id} left the chat")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)

from typing import List
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from cuid import cuid


class Client(BaseModel):
    id: str
    username: str
    socket: WebSocket

    class Config:
        arbitrary_types_allowed = True


clients: List[Client] = []


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/{username}")
async def websocket_server(socket: WebSocket, username: str):
    await socket.accept()
    # create current client
    client = Client(id=cuid(), username=username, socket=socket)
    clients.append(client)

    print(f"Connected clients: {len(clients)}")

    # fetch current client
    await client.socket.send_json(
        {"type": "setMe", "data": client.dict(exclude={"socket"})}
    )

    # fetch connected clients
    users = []
    for c in clients:
        users.append(c.dict(exclude={"socket"}))
    await client.socket.send_json({"type": "setUsers", "data": users})

    # update connected clients user lists with new client
    for c in clients:
        await c.socket.send_json(
            {"type": "addUser", "data": client.dict(exclude={"socket"})}
        )

    try:
        while True:
            data = await socket.receive_json()
    except WebSocketDisconnect:
        # remove client from list of clients
        for i, c in enumerate(clients):
            if c.id == client.id:
                del clients[i]

        for c in clients:
            await c.socket.send_json({"type": "removeUser", "data": client.id})

        print(f"Connected clients: {len(clients)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

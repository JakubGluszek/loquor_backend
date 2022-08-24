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


async def createClient(*, socket: WebSocket, username: str) -> Client:
    client = Client(id=cuid(), username=username, socket=socket)
    clients.append(client)

    await socket.send_json({"type": "me", "data": client.dict(exclude={"socket"})})

    users = []
    for c in clients:
        users.append(c.dict(exclude={"socket"}))

    await socket.send_json({"type": "setUsers", "data": users})

    for c in clients:
        await c.socket.send_json(
            {"type": "addUser", "data": client.dict(exclude={"socket"})}
        )

    return client


@app.websocket("/{username}")
async def websocket_server(socket: WebSocket, username: str):
    await socket.accept()

    client = await createClient(socket=socket, username=username)

    try:
        while True:
            event = await socket.receive_json()
            data = event["data"]
            print(event)

            if event["type"] == "chatInvite":
                # data: {target: clientID, from: client}
                for c in clients:
                    if c.id == data["target"]:
                        await c.socket.send_json(
                            {"type": "chatInvite", "data": {"user": data["from"]}}
                        )
            elif event["type"] == "chatInviteCancel":
                # data: {target: clientID, from: client}
                for c in clients:
                    if c.id == data["target"]:
                        await c.socket.send_json(
                            {"type": "chatInviteCancel", "data": {"user": data["from"]}}
                        )
            elif event["type"] == "chatInviteRes":
                # data: {from: client, target: clientID, response: bool}
                for c in clients:
                    if c.id == data["target"]:
                        await c.socket.send_json(
                            {"type": "chatInviteRes", "data": data}
                        )
            elif event["type"] in ["ice-candidate", "offer", "answer"]:
                # data: {from: clientID, target: clientID}
                for c in clients:
                    if c.id == data["target"]:
                        await c.socket.send_json({"type": event["type"], "data": data})

    except WebSocketDisconnect:
        # remove client from list of clients
        for i, c in enumerate(clients):
            if c.id == client.id:
                del clients[i]

        # emit to other clients to remove this disconnected client
        for c in clients:
            await c.socket.send_json(
                {"type": "removeUser", "data": client.dict(exclude={"socket"})}
            )

        print(f"Connected clients: {len(clients)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

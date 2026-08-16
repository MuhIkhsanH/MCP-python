import sqlite3
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mcp.server import Server
from mcp.server.sse import SseServerTransport
import mcp.types as types

app = Server("sqlite-manager")
DB_PATH = "database.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS barang (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            stok INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="lihat_barang",
            description="Ambil semua data barang dari database SQLite",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="tambah_barang",
            description="Tambahkan barang baru ke dalam database SQLite",
            inputSchema={
                "type": "object",
                "properties": {
                    "nama": {"type": "string"},
                    "stok": {"type": "integer"}
                },
                "required": ["nama", "stok"]
            },
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if name == "lihat_barang":
        cursor.execute("SELECT * FROM barang")
        rows = cursor.fetchall()
        conn.close()
        return [types.TextContent(type="text", text=str(rows))]

    elif name == "tambah_barang":
        nama = arguments.get("nama")
        stok = arguments.get("stok")
        cursor.execute("INSERT INTO barang (nama, stok) VALUES (?, ?)", (nama, stok))
        conn.commit()
        conn.close()
        return [types.TextContent(type="text", text=f"Barang '{nama}' berhasil ditambahkan!")]

    conn.close()
    raise ValueError(f"Tool tidak ditemukan: {name}")

# Inisialisasi FastAPI & SSE Transport
fastapi_app = FastAPI()

# Tambahkan CORS Middleware agar browser mengizinkan UI port 8080 mengakses port 8000
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sse = SseServerTransport("/messages")

@fastapi_app.get("/sse")
async def handle_sse(request: Request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await app.run(
            streams[0], streams[1], app.create_initialization_options()
        )

@fastapi_app.post("/messages")
async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

if __name__ == "__main__":
    init_db()
    print("🚀 Running MCP SSE Server on http://127.0.0.1:8000/sse")
    uvicorn.run(fastapi_app, host="127.0.0.1", port=8000)

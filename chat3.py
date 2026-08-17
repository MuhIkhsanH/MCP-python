import os
import asyncio
import sqlite3

from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp.server import MCPServer
from mcp.client import Client


load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY tidak ditemukan di .env")


DB_PATH = "database.db"


# ============================================================
# DATABASE
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS barang (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL UNIQUE,
            stok INTEGER NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# MCP SERVER
# ============================================================

mcp = MCPServer("sqlite-manager")


@mcp.tool()
def lihat_barang() -> str:
    """Melihat semua barang yang tersimpan di database."""

    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, nama, stok FROM barang ORDER BY nama"
        )

        rows = cursor.fetchall()

        if not rows:
            return "Database barang masih kosong."

        return str(rows)

    finally:
        conn.close()


@mcp.tool()
def tambah_barang(nama: str, stok: int) -> str:
    """Menambahkan stok barang.

    Jika barang belum ada, barang baru dibuat.
    Jika barang sudah ada, stok ditambahkan ke stok yang sudah ada.

    Args:
        nama: Nama barang.
        stok: Jumlah stok yang ingin ditambahkan.
    """

    if stok <= 0:
        return "Jumlah stok yang ditambahkan harus lebih dari 0."

    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT stok FROM barang WHERE nama = ?",
            (nama,)
        )

        existing = cursor.fetchone()

        if existing:
            stok_lama = existing[0]
            stok_baru = stok_lama + stok

            cursor.execute(
                "UPDATE barang SET stok = ? WHERE nama = ?",
                (stok_baru, nama)
            )

            conn.commit()

            return (
                f"Barang '{nama}' sudah ada. "
                f"Stok bertambah dari {stok_lama} menjadi {stok_baru}."
            )

        cursor.execute(
            "INSERT INTO barang (nama, stok) VALUES (?, ?)",
            (nama, stok)
        )

        conn.commit()

        return (
            f"Barang '{nama}' berhasil ditambahkan "
            f"dengan stok {stok}."
        )

    finally:
        conn.close()


@mcp.tool()
def update_barang(nama: str, stok: int) -> str:
    """Mengubah stok barang menjadi jumlah tertentu.

    Args:
        nama: Nama barang.
        stok: Stok baru.
    """

    if stok < 0:
        return "Stok tidak boleh negatif."

    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT stok FROM barang WHERE nama = ?",
            (nama,)
        )

        existing = cursor.fetchone()

        if not existing:
            return f"Barang '{nama}' tidak ditemukan."

        stok_lama = existing[0]

        cursor.execute(
            "UPDATE barang SET stok = ? WHERE nama = ?",
            (stok, nama)
        )

        conn.commit()

        return (
            f"Stok '{nama}' berhasil diubah "
            f"dari {stok_lama} menjadi {stok}."
        )

    finally:
        conn.close()


@mcp.tool()
def hapus_barang(nama: str) -> str:
    """Menghapus barang berdasarkan nama.

    Args:
        nama: Nama barang yang ingin dihapus.
    """

    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT stok FROM barang WHERE nama = ?",
            (nama,)
        )

        existing = cursor.fetchone()

        if not existing:
            return f"Barang '{nama}' tidak ditemukan."

        cursor.execute(
            "DELETE FROM barang WHERE nama = ?",
            (nama,)
        )

        conn.commit()

        return f"Barang '{nama}' berhasil dihapus."

    finally:
        conn.close()


# ============================================================
# GEMINI
# ============================================================

gemini = genai.Client(api_key=API_KEY)


gemini_tools = [
    types.Tool(
        function_declarations=[

            types.FunctionDeclaration(
                name="lihat_barang",
                description=(
                    "Melihat semua barang yang tersimpan "
                    "di database SQLite."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={}
                )
            ),

            types.FunctionDeclaration(
                name="tambah_barang",
                description=(
                    "Menambahkan stok barang. "
                    "Jika barang sudah ada, tambahkan stok "
                    "ke stok yang sudah ada. Jangan membuat "
                    "barang duplikat."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "nama": types.Schema(
                            type="STRING",
                            description="Nama barang"
                        ),
                        "stok": types.Schema(
                            type="INTEGER",
                            description=(
                                "Jumlah stok yang ingin ditambahkan"
                            )
                        )
                    },
                    required=["nama", "stok"]
                )
            ),

            types.FunctionDeclaration(
                name="update_barang",
                description=(
                    "Mengubah stok barang menjadi jumlah tertentu. "
                    "Gunakan ini ketika pengguna mengatakan "
                    "stok harus menjadi jumlah tertentu."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "nama": types.Schema(
                            type="STRING",
                            description="Nama barang"
                        ),
                        "stok": types.Schema(
                            type="INTEGER",
                            description="Stok baru"
                        )
                    },
                    required=["nama", "stok"]
                )
            ),

            types.FunctionDeclaration(
                name="hapus_barang",
                description=(
                    "Menghapus barang berdasarkan nama."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "nama": types.Schema(
                            type="STRING",
                            description="Nama barang yang akan dihapus"
                        )
                    },
                    required=["nama"]
                )
            )
        ]
    )
]


# ============================================================
# MCP TOOL EXECUTION
# ============================================================

async def execute_tool(mcp_client, name, arguments):

    print(f"\n[MCP] Tool: {name}")
    print(f"[MCP] Arguments: {arguments}")

    result = await mcp_client.call_tool(
        name,
        arguments
    )

    texts = []

    for content in result.content:
        if hasattr(content, "text"):
            texts.append(content.text)

    output = "\n".join(texts)

    print(f"[MCP] Result: {output}\n")

    return output


# ============================================================
# GEMINI
# ============================================================

async def ask_gemini(mcp_client, history):

    while True:

        response = gemini.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=history,
            config=types.GenerateContentConfig(
                tools=gemini_tools,
                system_instruction="""
Kamu adalah asisten pengelola database barang.

Aturan database:

1. Nama barang bersifat unik.
2. Jangan pernah membuat barang duplikat.
3. Jika pengguna mengatakan "tambahkan", gunakan tambah_barang.
4. tambah_barang akan otomatis menambahkan stok ke barang
   yang sudah ada.
5. Jika pengguna mengatakan stok harus menjadi jumlah tertentu,
   gunakan update_barang.
6. Jika pengguna meminta menghapus barang, gunakan hapus_barang.
7. Jika pengguna hanya ingin melihat barang, gunakan lihat_barang.
8. Jangan mengarang isi database.
9. Gunakan tool untuk mendapatkan data database.
10. Setelah tool selesai, jelaskan hasilnya secara singkat
    kepada pengguna.
"""
            )
        )

        if not response.function_calls:

            history.append(
                response.candidates[0].content
            )

            return response.text

        history.append(
            response.candidates[0].content
        )

        tool_responses = []

        for function_call in response.function_calls:

            name = function_call.name
            arguments = dict(function_call.args)

            result = await execute_tool(
                mcp_client,
                name,
                arguments
            )

            tool_responses.append(
                types.Part.from_function_response(
                    name=name,
                    response={
                        "result": result
                    }
                )
            )

        history.append(
            types.Content(
                role="tool",
                parts=tool_responses
            )
        )


# ============================================================
# MAIN
# ============================================================

async def main():

    init_db()

    print("=" * 50)
    print(" Gemini 3.1 Flash-Lite + MCP + SQLite")
    print("=" * 50)
    print("Ketik exit untuk keluar.")
    print()

    history = []

    async with Client(mcp) as mcp_client:

        tools = await mcp_client.list_tools()

        print("MCP Tools:")

        for tool in tools.tools:
            print(f"  - {tool.name}")

        print()

        while True:

            try:
                user_input = input("You: ")

            except KeyboardInterrupt:
                print("\nBye!")
                break

            if user_input.lower() == "exit":
                print("Bye!")
                break

            if not user_input.strip():
                continue

            history.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=user_input
                        )
                    ]
                )
            )

            try:

                answer = await ask_gemini(
                    mcp_client,
                    history
                )

                print(f"Gemini: {answer}\n")

            except Exception as e:

                print(f"\nERROR: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())

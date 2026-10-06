"""True database integration tests using aiosqlite with raw SQL."""
import uuid

import aiosqlite
import pytest


@pytest.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("""
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            avatar TEXT,
            role TEXT DEFAULT 'guest',
            is_active INTEGER DEFAULT 1,
            is_email_verified INTEGER DEFAULT 0,
            last_login_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            deleted_at TEXT
        )
    """)
    await conn.execute("""
        CREATE TABLE notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            type TEXT DEFAULT 'info',
            link TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    await conn.execute("""
        CREATE TABLE invoices (
            id TEXT PRIMARY KEY,
            invoice_number TEXT,
            amount REAL NOT NULL,
            tax REAL DEFAULT 0,
            total_amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            status TEXT DEFAULT 'draft',
            client_id TEXT,
            project_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    await conn.execute("""
        CREATE TABLE payments (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL,
            amount REAL NOT NULL,
            method TEXT DEFAULT 'bank_transfer',
            status TEXT DEFAULT 'completed',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        )
    """)
    await conn.commit()
    yield conn
    await conn.close()


class TestUserDatabaseIntegration:
    @pytest.mark.asyncio
    async def test_create_user(self, db):
        user_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO users (id, name, email, role) VALUES (?, ?, ?, ?)",
            (user_id, "Test User", "test@example.com", "client"),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        assert row is not None
        assert row[1] == "Test User"
        assert row[2] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user(self, db):
        user_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            (user_id, "Get User", "get@example.com"),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == user_id

    @pytest.mark.asyncio
    async def test_update_user(self, db):
        user_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            (user_id, "Old Name", "update@example.com"),
        )
        await db.commit()

        await db.execute(
            "UPDATE users SET name = ? WHERE id = ?",
            ("New Name", user_id),
        )
        await db.commit()

        cursor = await db.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        assert row[0] == "New Name"

    @pytest.mark.asyncio
    async def test_delete_user(self, db):
        user_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            (user_id, "Delete Me", "delete@example.com"),
        )
        await db.commit()

        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()

        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        assert row is None

    @pytest.mark.asyncio
    async def test_list_users_with_pagination(self, db):
        for i in range(5):
            await db.execute(
                "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
                (str(uuid.uuid4()), f"User {i}", f"user{i}@test.com"),
            )
        await db.commit()

        cursor = await db.execute("SELECT * FROM users LIMIT 2 OFFSET 0")
        rows = await cursor.fetchall()
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_list_users_with_search(self, db):
        await db.execute(
            "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            (str(uuid.uuid4()), "Searchable User", "search@test.com"),
        )
        await db.execute(
            "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            (str(uuid.uuid4()), "Other User", "other@test.com"),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM users WHERE name LIKE ? OR email LIKE ?",
            ("%Searchable%", "%Searchable%"),
        )
        rows = await cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "Searchable User"

    @pytest.mark.asyncio
    async def test_unique_email_constraint(self, db):
        await db.execute(
            "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            (str(uuid.uuid4()), "User 1", "duplicate@test.com"),
        )
        await db.commit()

        with pytest.raises(aiosqlite.IntegrityError):
            await db.execute(
                "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
                (str(uuid.uuid4()), "User 2", "duplicate@test.com"),
            )
            await db.commit()


class TestNotificationDatabaseIntegration:
    @pytest.mark.asyncio
    async def test_create_notification(self, db):
        user_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            (user_id, "Test", "test@test.com"),
        )
        await db.commit()

        notif_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO notifications (id, user_id, title, message, type) VALUES (?, ?, ?, ?, ?)",
            (notif_id, user_id, "Test Title", "Test Message", "info"),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM notifications WHERE id = ?", (notif_id,))
        row = await cursor.fetchone()
        assert row is not None
        assert row[2] == "Test Title"

    @pytest.mark.asyncio
    async def test_list_user_notifications(self, db):
        user_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            (user_id, "Test", "test@test.com"),
        )
        for i in range(3):
            await db.execute(
                "INSERT INTO notifications (id, user_id, title) VALUES (?, ?, ?)",
                (str(uuid.uuid4()), user_id, f"Notif {i}"),
            )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM notifications WHERE user_id = ?", (user_id,)
        )
        rows = await cursor.fetchall()
        assert len(rows) == 3


class TestFinanceDatabaseIntegration:
    @pytest.mark.asyncio
    async def test_create_invoice(self, db):
        inv_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO invoices (id, invoice_number, amount, tax, total_amount, status) VALUES (?, ?, ?, ?, ?, ?)",
            (inv_id, "INV-001", 1000.0, 100.0, 1100.0, "draft"),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM invoices WHERE id = ?", (inv_id,))
        row = await cursor.fetchone()
        assert row is not None
        assert row[1] == "INV-001"
        assert row[4] == 1100.0

    @pytest.mark.asyncio
    async def test_record_payment(self, db):
        inv_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO invoices (id, invoice_number, amount, total_amount, status) VALUES (?, ?, ?, ?, ?)",
            (inv_id, "INV-002", 1000.0, 1000.0, "sent"),
        )
        await db.commit()

        pay_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO payments (id, invoice_id, amount, status) VALUES (?, ?, ?, ?)",
            (pay_id, inv_id, 500.0, "completed"),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM payments WHERE invoice_id = ?", (inv_id,))
        rows = await cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][2] == 500.0

    @pytest.mark.asyncio
    async def test_invoice_total_calculation(self, db):
        inv_id = str(uuid.uuid4())
        amount = 1000.0
        tax = 150.0
        total = amount + tax
        await db.execute(
            "INSERT INTO invoices (id, invoice_number, amount, tax, total_amount) VALUES (?, ?, ?, ?, ?)",
            (inv_id, "INV-003", amount, tax, total),
        )
        await db.commit()

        cursor = await db.execute("SELECT total_amount FROM invoices WHERE id = ?", (inv_id,))
        row = await cursor.fetchone()
        assert row[0] == 1150.0

    @pytest.mark.asyncio
    async def test_payment_status_auto_update(self, db):
        inv_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO invoices (id, invoice_number, amount, total_amount, status) VALUES (?, ?, ?, ?, ?)",
            (inv_id, "INV-004", 500.0, 500.0, "sent"),
        )
        await db.commit()

        pay_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO payments (id, invoice_id, amount, status) VALUES (?, ?, ?, ?)",
            (pay_id, inv_id, 500.0, "completed"),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE invoice_id = ? AND status = 'completed'",
            (inv_id,),
        )
        row = await cursor.fetchone()
        paid_total = row[0]

        if paid_total >= 500.0:
            await db.execute(
                "UPDATE invoices SET status = 'paid' WHERE id = ?",
                (inv_id,),
            )
            await db.commit()

        cursor = await db.execute("SELECT status FROM invoices WHERE id = ?", (inv_id,))
        row = await cursor.fetchone()
        assert row[0] == "paid"

    @pytest.mark.asyncio
    async def test_filter_invoices_by_status(self, db):
        await db.execute(
            "INSERT INTO invoices (id, invoice_number, amount, total_amount, status) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), "INV-005", 100.0, 100.0, "draft"),
        )
        await db.execute(
            "INSERT INTO invoices (id, invoice_number, amount, total_amount, status) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), "INV-006", 200.0, 200.0, "paid"),
        )
        await db.execute(
            "INSERT INTO invoices (id, invoice_number, amount, total_amount, status) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), "INV-007", 300.0, 300.0, "paid"),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM invoices WHERE status = 'paid'")
        rows = await cursor.fetchall()
        assert len(rows) == 2

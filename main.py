from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os


app = Flask(__name__)
app.secret_key = os.urandom(24)

# SQLite Database Setup
conn = sqlite3.connect("groups.db")
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        creator_id INTEGER NOT NULL,
        FOREIGN KEY (creator_id) REFERENCES users(id)
    )
"""
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        user_id INTEGER,  -- Add this line to include user_id column
        FOREIGN KEY (group_id) REFERENCES groups(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
"""
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        user_id INTEGER,
        name TEXT NOT NULL,
        amount REAL NOT NULL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES groups(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
"""
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS transaction_splits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id INTEGER,
        user_id INTEGER,
        amount REAL NOT NULL,
        FOREIGN KEY (transaction_id) REFERENCES transactions(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
"""
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
"""
)
conn.close()


@app.route("/add_transaction/<int:group_id>", methods=["POST"])
def add_transaction(group_id):
    # Check if the user is logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Get transaction details from the form
    transaction_name = request.form.get("transaction_name")
    amount = float(request.form.get("amount"))
    user_id = session["user_id"]

    # Add the transaction to the database
    conn = sqlite3.connect("groups.db")
    conn.execute(
        "INSERT INTO transactions (group_id, user_id, name, amount) VALUES (?, ?, ?, ?)",
        (group_id, user_id, transaction_name, amount),
    )
    transaction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Get the group members
    cursor = conn.execute(
        "SELECT u.id, u.username FROM members m JOIN users u ON m.user_id = u.id WHERE m.group_id = ?",
        (group_id,),
    )
    group_members = cursor.fetchall()

    selected_members = request.form.getlist("split_members")
    print(
        "Selected Members:", selected_members
    )  # Add this line to print selected members

    # Split the amount equally among selected group members
    split_amount = amount / (
        len(selected_members) + 1
    )  # Including the user who added the transaction

    for member_id in selected_members:
        conn.execute(
            "INSERT INTO transaction_splits (transaction_id, user_id, amount) VALUES (?, ?, ?)",
            (transaction_id, member_id, split_amount),
        )

    conn.commit()
    conn.close()
    return redirect(url_for("group", group_id=group_id))


@app.route("/split_transaction/<int:transaction_id>/<int:group_id>", methods=["POST"])
def split_transaction(transaction_id, group_id):
    # Check if the user is logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Get selected members for splitting
    selected_members = request.form.getlist("split_members")

    # Split the transaction amount among selected group members
    conn = sqlite3.connect("groups.db")
    transaction = conn.execute(
        "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
    ).fetchone()
    split_amount = transaction["amount"] / (
        len(selected_members) + 1
    )  # Including the user who added the transaction

    for member_id in selected_members:
        conn.execute(
            "INSERT INTO transaction_splits (transaction_id, user_id, amount) VALUES (?, ?, ?)",
            (transaction_id, member_id, split_amount),
        )

    conn.commit()
    conn.close()
    return redirect(url_for("group", group_id=group_id))


# @app.route("/register", methods=["GET", "POST"])
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        # dob = request.form.get("dob")

        # Check if the username already exists
        conn = sqlite3.connect("groups.db")
        cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            return "Username already exists. Please choose another username."

        # Add the new user to the database
        conn.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, password)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Check if the username and password match
        conn = sqlite3.connect("groups.db")
        cursor = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password),
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            # Set a session variable to indicate that the user is logged in
            session["user_id"] = user[0]
            return redirect(url_for("index"))
        else:
            return "Invalid username or password. Please try again."

    return render_template("login.html")

@app.route("/")
def landing():
    return render_template("landing.html")

# Routes
@app.route("/index")
def index():
    # Check if the user is logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Display existing groups
    conn = sqlite3.connect("groups.db")
    cursor = conn.execute("SELECT id, name FROM groups")
    groups = cursor.fetchall()
    conn.close()
    return render_template("index.html", groups=groups,is_group_visible=is_group_visible)


@app.route("/create_group", methods=["POST"])
def create_group():
    # Create a new group
    group_name = request.form.get("group_name")
    conn = sqlite3.connect("groups.db")

    # Check if the user is logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    creator_id = session["user_id"]  # Get the ID of the current user

    # Insert the new group with the creator_id
    conn.execute(
        "INSERT INTO groups (name, creator_id) VALUES (?, ?)", (group_name, creator_id)
    )

    # Add the creator as a member of the group
    group_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO members (group_id, user_id) VALUES (?, ?)", (group_id, creator_id)
    )

    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("landing"))


@app.route("/group/<int:group_id>")
def group(group_id):
    # Check if the user is logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Check if the user is a member of the group or the group creator
    user_id = session["user_id"]

    conn = sqlite3.connect("groups.db")
    cursor = conn.execute(
        "SELECT * FROM members WHERE group_id = ? AND user_id = ?", (group_id, user_id)
    )
    is_member = cursor.fetchone()

    if not is_member:
        # Check if the user is the creator of the group
        cursor = conn.execute(
            "SELECT * FROM groups WHERE id = ? AND creator_id = ?", (group_id, user_id)
        )
        is_creator = cursor.fetchone()

        if not is_creator:
            return "You do not have access to this group."

    # Fetch transactions for the group
    cursor = conn.execute("SELECT * FROM transactions WHERE group_id = ?", (group_id,))
    transactions = cursor.fetchall()

    # Fetch members for the group
    cursor = conn.execute(
        "SELECT u.id, u.username FROM members m JOIN users u ON m.user_id = u.id WHERE m.group_id = ?",
        (group_id,),
    )
    group_members = cursor.fetchall()
    total_owe = calculate_total_owe(group_id, user_id)
    total_receive = calculate_total_receive(group_id, user_id)
    conn.close()
    return render_template(
        "group.html",
        group_id=group_id,
        transactions=transactions,
        user_id=user_id,
        group_members=group_members,
        get_split_details=get_split_details,
        get_username=get_username,
        lenoffun=lenoffun,
        total_owe=total_owe,
        total_receive=total_receive,
    )


# Modify this helper function in your Flask app
def calculate_total_owe(group_id, user_id):
    conn = sqlite3.connect("groups.db")
    cursor = conn.execute(
        """
        SELECT SUM(amount) FROM transaction_splits
        WHERE user_id = ? AND transaction_id IN
            (SELECT id FROM transactions WHERE group_id = ?)
        """,
        (user_id, group_id),
    )
    total_owe = cursor.fetchone()[0] or 0
    conn.close()
    return total_owe


# Modify this helper function in your Flask app
def calculate_total_receive(group_id, user_id):
    conn = sqlite3.connect("groups.db")
    cursor = conn.execute(
        """
        SELECT SUM(amount) FROM transaction_splits
        WHERE user_id != ? AND transaction_id IN
            (SELECT id FROM transactions WHERE group_id = ?)
        """,
        (user_id, group_id),
    )
    total_receive = cursor.fetchone()[0] or 0
    conn.close()
    return total_receive


@app.route("/add_member/<int:group_id>", methods=["POST"])
def add_member(group_id):
    # Check if the user is logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Check if the user is the creator of the group
    user_id = session["user_id"]
    conn = sqlite3.connect("groups.db")
    cursor = conn.execute(
        "SELECT * FROM groups WHERE id = ? AND creator_id = ?", (group_id, user_id)
    )
    is_creator = cursor.fetchone()

    if not is_creator:
        return "You do not have permission to add members to this group."

    # Add a member to the group if they don't already exist
    username = request.form.get("username")

    # Check if the user exists in the database
    cursor = conn.execute(
        "SELECT * FROM users u WHERE u.username = ? AND NOT EXISTS (SELECT 1 FROM members m WHERE m.group_id = ? AND m.user_id = u.id)",
        (username, group_id),
    )
    user = cursor.fetchone()

    if not user:
        return "User either does not exist or is already a member of the group."

    # Add the member to the group
    conn.execute(
        "INSERT INTO members (group_id, user_id) VALUES (?, ?)", (group_id, user[0])
    )
    conn.commit()
    conn.close()
    return redirect(url_for("group", group_id=group_id))


@app.route("/delete_transaction/<int:group_id>/<int:transaction_id>")
def delete_transaction(group_id, transaction_id):
    # Check if the user is logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Check if the user is the creator of the transaction
    conn = sqlite3.connect("groups.db")
    cursor = conn.execute(
        "SELECT * FROM transactions WHERE id = ? AND user_id = ?",
        (transaction_id, session["user_id"]),
    )
    transaction = cursor.fetchone()

    if not transaction:
        return "You do not have permission to delete this transaction."

    # Delete the transaction and associated splits
    conn.execute(
        "DELETE FROM transaction_splits WHERE transaction_id = ?", (transaction_id,)
    )
    conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("group", group_id=group_id))


# Add these functions to your Flask app
def get_split_details(transaction_id):
    conn = sqlite3.connect("groups.db")
    cursor = conn.execute(
        "SELECT user_id, amount FROM transaction_splits WHERE transaction_id = ?",
        (transaction_id,),
    )
    split_details = cursor.fetchall()
    conn.close()
    return split_details
def is_group_visible(group_id):
    if "user_id" not in session:
        return False

    user_id = session["user_id"]
    conn = sqlite3.connect("groups.db")
    cursor = conn.execute(
        "SELECT * FROM members WHERE group_id = ? AND (user_id = ?)",
        (group_id, user_id),
    )
    is_member_or_creator = cursor.fetchone()
    conn.close()

    return bool(is_member_or_creator)


def get_username(user_id):
    conn = sqlite3.connect("groups.db")
    cursor = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    username = cursor.fetchone()[0]
    conn.close()
    return username


def lenoffun(a):
    return len(a)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)

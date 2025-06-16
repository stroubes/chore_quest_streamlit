import streamlit as st
import sqlite3
from datetime import datetime, timedelta

st.set_page_config(page_title="Chore Quest", layout="wide", initial_sidebar_state="collapsed")

DB_FILE = "chores.db"

# ---------- DB SETUP ----------
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS kids (id INTEGER PRIMARY KEY, name TEXT, points INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS chores (
            id INTEGER PRIMARY KEY,
            kid_id INTEGER,
            name TEXT,
            is_completed INTEGER DEFAULT 0,
            is_approved INTEGER DEFAULT 0,
            points INTEGER DEFAULT 10,
            day TEXT DEFAULT 'Any',
            recurrence TEXT DEFAULT 'Daily',
            start_date TEXT DEFAULT '',
            interval_days INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY,
            kid_id INTEGER,
            name TEXT,
            cost INTEGER,
            is_claimed INTEGER DEFAULT 0,
            is_approved INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS chore_history (
            id INTEGER PRIMARY KEY,
            kid_id INTEGER,
            chore_name TEXT,
            completed_at TEXT,
            points INTEGER
        )""")


        # Initial Data
        c.execute("SELECT COUNT(*) FROM kids")
        if c.fetchone()[0] == 0:
            c.executemany("INSERT INTO kids (name, points) VALUES (?, ?)", [
                ("Charles", 100), ("Carys", 50), ("Wynne", 75),
            ])
            conn.commit()

        c.execute("SELECT id, name FROM kids")
        kid_ids = {name: kid_id for kid_id, name in c.fetchall()}

        c.execute("SELECT COUNT(*) FROM chores")
        if c.fetchone()[0] == 0:
            next_monday = (datetime.today() + timedelta(days=(7 - datetime.today().weekday()) % 7)).date()
            c.executemany("""INSERT INTO chores (kid_id, name, recurrence, day, start_date, interval_days, points)
                            VALUES (?, ?, ?, ?, ?, ?, ?)""", [
                (kid_ids["Carys"], "Feed the Dogs", "Daily", "Any", '', 0, 10),
                (kid_ids["Wynne"], "Feed the Cats", "Daily", "Any", '', 0, 10),
                (kid_ids["Charles"], "Take out Recycling", "Bi-weekly", "Monday", next_monday.strftime("%Y-%m-%d"), 14, 20),
            ])
            conn.commit()

        c.execute("SELECT COUNT(*) FROM rewards")
        if c.fetchone()[0] == 0:
            rewards = [("30 mins iPad", 50), ("Pick Dinner", 40), ("Sleepover", 100)]
            for name in kid_ids:
                for reward_name, cost in rewards:
                    c.execute("INSERT INTO rewards (kid_id, name, cost) VALUES (?, ?, ?)",
                              (kid_ids[name], reward_name, cost))
            conn.commit()

# ---------- HELPER FUNCTIONS ----------
def get_kids_with_chores():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM kids")
        kids = c.fetchall()
        data = {}
        for kid_id, name, points in kids:
            c.execute("SELECT * FROM chores WHERE kid_id=?", (kid_id,))
            chores = [dict(zip([d[0] for d in c.description], row)) for row in c.fetchall()]
            c.execute("SELECT * FROM rewards WHERE kid_id=?", (kid_id,))
            rewards = [dict(zip([d[0] for d in c.description], row)) for row in c.fetchall()]
            data[name] = {"id": kid_id, "points": points, "chores": chores, "rewards": rewards}
        return data

def mark_chore_complete(cid):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT kid_id, name, points FROM chores WHERE id=?", (cid,))
        result = c.fetchone()
        if result:
            kid_id, name, points = result
            completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("INSERT INTO chore_history (kid_id, chore_name, completed_at, points) VALUES (?, ?, ?, ?)",
                      (kid_id, name, completed_at, points))
            c.execute("UPDATE chores SET is_completed=1 WHERE id=?", (cid,))
            conn.commit()


def claim_reward(rid, cost, kid_id):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT points FROM kids WHERE id=?", (kid_id,))
        points = c.fetchone()[0]
        if points >= cost:
            c.execute("UPDATE kids SET points = points - ? WHERE id=?", (cost, kid_id))
            c.execute("UPDATE rewards SET is_claimed=1 WHERE id=?", (rid,))
            conn.commit()
            return True
        else:
            return False

# ---------- INIT ----------
init_db()
if "parent_auth" not in st.session_state:
    st.session_state["parent_auth"] = False

# ---------- UI ----------
st.title("🏡 Chore Quest")
nav = st.radio("Choose View", ["Child View", "Parent Admin"], horizontal=True)

# ---------- PARENT ADMIN ----------
if nav == "Parent Admin":
    if not st.session_state["parent_auth"]:
        pin = st.text_input("Enter Parent PIN:", type="password")
        if pin == "1234":
            st.session_state["parent_auth"] = True
            st.rerun()
        elif pin:
            st.warning("Incorrect PIN")
            st.stop()
    else:
        if st.button("Logout"):
            st.session_state["parent_auth"] = False
            st.rerun()

        st.header("🧑‍💼 Parent Admin Panel")

        # Approve Completed Chores
        with st.expander("🧾 Approve Completed Chores", expanded=True):
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("""SELECT chores.id, kids.name, chores.name, chores.points, kids.id
                             FROM chores JOIN kids ON chores.kid_id = kids.id
                             WHERE is_completed=1 AND is_approved=0""")
                for cid, kid_name, chore_name, points, kid_id in c.fetchall():
                    st.markdown(f"**{kid_name}** — 📌 _{chore_name}_ — 💯 {points} pts")
                    col1, col2 = st.columns(2)
                    if col1.button("✅ Approve", key=f"approve_{cid}"):
                        c.execute("UPDATE chores SET is_approved=1 WHERE id=?", (cid,))
                        c.execute("UPDATE kids SET points = points + ? WHERE id=?", (points, kid_id))
                        conn.commit()
                        st.rerun()
                    if col2.button("❌ Reject", key=f"reject_{cid}"):
                        c.execute("UPDATE chores SET is_completed=0 WHERE id=?", (cid,))
                        conn.commit()
                        st.rerun()

        # Approve Reward Claims
        with st.expander("🎁 Approve Reward Claims", expanded=True):
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("""SELECT rewards.id, kids.name, rewards.name, rewards.cost, kids.id
                             FROM rewards JOIN kids ON rewards.kid_id = kids.id
                             WHERE is_claimed=1 AND is_approved=0""")
                for rid, kid_name, reward_name, cost, kid_id in c.fetchall():
                    st.markdown(f"**{kid_name}** — 🎁 _{reward_name}_ — 💰 {cost} pts")
                    col1, col2 = st.columns(2)
                    if col1.button("✅ Approve", key=f"reward_approve_{rid}"):
                        c.execute("UPDATE rewards SET is_approved=1 WHERE id=?", (rid,))
                        conn.commit()
                        st.rerun()
                    if col2.button("❌ Reject", key=f"reward_reject_{rid}"):
                        c.execute("UPDATE rewards SET is_claimed=0 WHERE id=?", (rid,))
                        c.execute("UPDATE kids SET points = points + ? WHERE id=?", (cost, kid_id))
                        conn.commit()
                        st.rerun()

        # Add Chores
        with st.expander("➕ Add Chore"):
            kids = get_kids_with_chores()
            selected_kid = st.selectbox("Assign to", list(kids.keys()))
            chore_desc = st.text_input("Chore Description")
            chore_points = st.number_input("Points", min_value=1, value=10)
            chore_day = st.selectbox("Day", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
            recurrence = st.selectbox("Recurrence", ["Daily", "Weekly", "Bi-weekly", "Monthly", "Custom"])
            start_date = st.date_input("Start Date", value=datetime.today())
            interval = st.number_input("Repeat every X days", min_value=1, value=3)
            if st.button("📌 Create Chore"):
                with sqlite3.connect(DB_FILE) as conn:
                    conn.execute("""INSERT INTO chores (kid_id, name, points, day, recurrence, start_date, interval_days)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                 (kids[selected_kid]["id"], chore_desc, chore_points, chore_day, recurrence,
                                  start_date.strftime("%Y-%m-%d") if recurrence == "Custom" else '',
                                  interval if recurrence == "Custom" else 0))
                    conn.commit()
                st.success("Chore added!")
                st.rerun()

        # Add Rewards
        with st.expander("🎯 Add Reward"):
            reward_kid = st.selectbox("Reward For", list(kids.keys()), key="reward_kid")
            reward_name = st.text_input("Reward Name", key="reward_name")
            reward_cost = st.number_input("Reward Cost", min_value=1, value=50, step=5)
            if st.button("🎁 Add Reward"):
                with sqlite3.connect(DB_FILE) as conn:
                    conn.execute("INSERT INTO rewards (kid_id, name, cost) VALUES (?, ?, ?)",
                                 (kids[reward_kid]["id"], reward_name, reward_cost))
                    conn.commit()
                st.success("Reward added!")
                st.rerun()

# ---------- CHILD VIEW ----------
# ---------- CHILD VIEW ----------
else:
    st.header("🧒 Chore Board")
    kids = get_kids_with_chores()
    kid_names = list(kids.keys())

    cols = st.columns(len(kid_names))

    for i, name in enumerate(kid_names):
        data = kids[name]
        with cols[i]:
            st.markdown(f"### ⭐ {name}")
            st.markdown(f"**Points:** {data['points']}")

            # --- XP ---
            xp = data["points"] % 100
            st.progress(xp, text=f"{xp}/100 XP")

            # --- Streak (mock based on distinct dates in history) ---
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(DISTINCT DATE(completed_at)) FROM chore_history WHERE kid_id = ?", (data["id"],))
                streak_count = c.fetchone()[0]
            st.markdown(f"🔥 **Streak:** {streak_count} days")

            # --- Chores ---
            st.markdown("#### 🧹 Chores")
            chores_rendered = False
            for chore in data["chores"]:
                if not chore["is_completed"]:
                    chores_rendered = True
                    if st.button(f"✅ {chore['name']} ({chore['points']} pts)", key=f"done_{chore['id']}"):
                        mark_chore_complete(chore["id"])
                        st.rerun()
            if not chores_rendered:
                st.success("🎉 All chores done!")

            # --- Rewards ---
            st.markdown("#### 🎁 Rewards")
            for reward in data["rewards"]:
                if not reward["is_claimed"]:
                    if st.button(f"🎁 {reward['name']} — {reward['cost']} pts", key=f"claim_{reward['id']}"):
                        success = claim_reward(reward["id"], reward["cost"], data["id"])
                        if not success:
                            st.warning("Not enough points!")
                        st.rerun()

            # --- History ---
                        # --- History ---
            with st.expander("📜 View Chore History"):
                with sqlite3.connect(DB_FILE) as conn:
                    c = conn.cursor()
                    c.execute("""
                        SELECT chore_name, completed_at, points
                        FROM chore_history
                        WHERE kid_id = ?
                        ORDER BY completed_at DESC
                        LIMIT 10
                    """, (data["id"],))
                    rows = c.fetchall()
                    if rows:
                        for name_, date, pts in rows:
                            st.markdown(f"- ✅ _{name_}_ on `{date[:10]}` • 💯 {pts} pts")
                    else:
                        st.markdown("_No completed chores yet_")

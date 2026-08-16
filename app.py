import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar

# --- CONFIGURATION & USER GOALS ---
st.set_page_config(page_title="Squad Accountability Challenge", page_icon="🔥", layout="centered")

PARTICIPANTS = {
    "Alice": "Read 20 pages & Drink 2L water",
    "Bob": "Workout for 45 mins",
    "Charlie": "Code for 1 hour outside work",
    "David": "10,000 steps & 8 hours sleep"
}

# --- GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data() -> pd.DataFrame:
    try:
        df = conn.read(ttl=0)
        if df.empty or 'date' not in df.columns or 'user' not in df.columns:
            return pd.DataFrame(columns=["date", "user"])
        df['date'] = pd.to_datetime(df['date']).dt.date
        return df
    except Exception:
        return pd.DataFrame(columns=["date", "user"])

def save_checkin(user: str, checkin_date: date):
    df = load_data()
    # Avoid duplicate records for the same day
    exists = not df[(df['user'] == user) & (df['date'] == checkin_date)].empty
    if not exists:
        new_row = pd.DataFrame([{"date": checkin_date.isoformat(), "user": user}])
        df['date'] = df['date'].astype(str)
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(data=updated_df)
        st.cache_data.clear()

# --- STREAK & STATS CALCULATION ---
def calculate_user_stats(user: str, df: pd.DataFrame, today: date):
    user_dates = set(df[df['user'] == user]['date'])
    total_active = len(user_dates)
    
    # Calculate unbroken streak
    streak = 0
    # Check if checked in today; if not, check backwards from yesterday
    current_check = today if today in user_dates else (today - timedelta(days=1))
    
    while current_check in user_dates:
        streak += 1
        current_check -= timedelta(days=1)
        
    return {
        "user": user,
        "goal": PARTICIPANTS[user],
        "streak": streak,
        "total_days": total_active,
        "checked_in_today": today in user_dates
    }

# --- DIALOGS (POPUPS) ---
@st.dialog("Daily Check-In")
def checkin_dialog(user: str, today: date, already_done: bool):
    st.subheader(f"👋 Hey {user}!")
    st.info(f"**Today's Goal:** {PARTICIPANTS[user]}")
    
    if already_done:
        st.success("✅ You have already completed your check-in for today!")
        if st.button("Close Window", use_container_width=True):
            st.rerun()
    else:
        st.write("Did you crush your goal today?")
        if st.button("🔥 Mark Complete for Today", type="primary", use_container_width=True):
            save_checkin(user, today)
            st.success("Recorded! Keep the streak alive!")
            st.rerun()

@st.dialog("Activity Calendar")
def calendar_dialog(user: str, df: pd.DataFrame, today: date):
    st.subheader(f"📅 Progress for {user}")
    st.caption(f"Goal: {PARTICIPANTS[user]}")
    
    user_dates = set(df[df['user'] == user]['date'])
    
    # Render current month view
    cal = calendar.Calendar(firstweekday=0) # Monday first
    month_days = cal.monthdatescalendar(today.year, today.month)
    
    st.write(f"### {today.strftime('%B %Y')}")
    
    # Header row
    days_header = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    cols = st.columns(7)
    for i, d in enumerate(days_header):
        cols[i].caption(f"**{d}**")
        
    # Calendar grid
    for week in month_days:
        cols = st.columns(7)
        for i, d in enumerate(week):
            if d.month != today.month:
                cols[i].write("") # Blank out adjacent month days
            else:
                if d in user_dates:
                    cols[i].markdown(f"**{d.day}**\n\n🟢")
                elif d > today:
                    cols[i].markdown(f"{d.day}\n\n⚪")
                elif d == today:
                    cols[i].markdown(f"**{d.day}**\n\n⏳")
                else:
                    cols[i].markdown(f"{d.day}\n\n🔴")
                    
    st.caption("Legend: 🟢 Completed | 🔴 Missed | ⏳ Pending Today | ⚪ Future")

# --- MAIN APP FLOW ---
def main():
    today = date.today()
    
    # 1. Gatekeeper / Login
    if "authenticated_user" not in st.session_state:
        st.session_state.authenticated_user = None

    if not st.session_state.authenticated_user:
        st.title("🔒 Squad Challenge Login")
        st.write("Select your name to enter the dashboard:")
        
        selected_user = st.selectbox("Choose Profile", ["-- Select Name --"] + list(PARTICIPANTS.keys()))
        
        if st.button("Enter Dashboard", type="primary", use_container_width=True):
            if selected_user != "-- Select Name --":
                st.session_state.authenticated_user = selected_user
                st.session_state.show_checkin_popup = True
                st.rerun()
            else:
                st.warning("Please choose your name from the list.")
        return

    # --- AUTHENTICATED VIEW ---
    current_user = st.session_state.authenticated_user
    data = load_data()
    
    # Top navbar
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.title("🏆 Challenge Leaderboard")
        st.caption(f"Logged in as **{current_user}** | {today.strftime('%A, %B %d, %Y')}")
    with top_col2:
        if st.button("Log out", use_container_width=True):
            st.session_state.authenticated_user = None
            st.rerun()

    # Trigger automatic popup after login if not checked in
    if st.session_state.get("show_checkin_popup", False):
        st.session_state.show_checkin_popup = False
        user_done_today = not data[(data['user'] == current_user) & (data['date'] == today)].empty
        checkin_dialog(current_user, today, user_done_today)

    # 2. Leaderboard Table
    stats = [calculate_user_stats(u, data, today) for u in PARTICIPANTS.keys()]
    # Sort: Descending by unbroken streak, tie-break with total days
    stats_sorted = sorted(stats, key=lambda x: (x["streak"], x["total_days"]), reverse=True)

    st.write("---")
    
    # Badges for podium
    rank_icons = ["🥇", "🥈", "🥉", "4️⃣"]

    for idx, stat in enumerate(stats_sorted):
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 4, 3, 2])
            
            icon = rank_icons[idx] if idx < len(rank_icons) else f"{idx+1}."
            col1.markdown(f"### {icon}")
            
            col2.markdown(f"**{stat['user']}**\n\n_{stat['goal']}_")
            
            today_status = "✅ Done" if stat["checked_in_today"] else "⏳ Pending"
            col3.markdown(f"🔥 **{stat['streak']} Day Streak**\n\nTotal: {stat['total_days']} active | Today: {today_status}")
            
            if col4.button("📅 History", key=f"hist_{stat['user']}", use_container_width=True):
                calendar_dialog(stat['user'], data, today)
                
            st.divider()

    # Manual trigger for check-in button if they want to re-open it
    st.button("Open Daily Check-in Window", on_click=lambda: checkin_dialog(
        current_user, today, not data[(data['user'] == current_user) & (data['date'] == today)].empty
    ))

if __name__ == "__main__":
    main()

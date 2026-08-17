import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar

# --- CONFIGURATION (Wide layout for better space utilization) ---
st.set_page_config(page_title="أهل البكور", page_icon="🔥", layout="wide")

# --- CUSTOM CSS (Tighten whitespace & padding) ---
st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            max-width: 1200px !important;
        }
        div[data-testid="stVerticalBlock"] > div {
            gap: 0.4rem !important;
        }
        hr {
            margin-top: 0.6rem !important;
            margin-bottom: 0.6rem !important;
        }
        .side-text-box {
            background-color: rgba(128, 128, 128, 0.08);
            border-left: 3px solid #ff4b4b;
            padding: 10px 14px;
            border-radius: 4px;
            font-size: 0.9rem;
        }
    </style>
""", unsafe_allow_html=True)

# --- PARTICIPANTS ET OBJECTIFS ---
PARTICIPANTS = {
    "Amina": "Se réveiller avec l'adhan ou à 6 heures au plus tard",
    "Fatima": "Se réveiller avec l'adhan ou à 6 heures au plus tard",
    "Lamiae": "Se réveiller avec l'adhan ou à 6 heures au plus tard",
    "Oumaima": "Se réveiller avec l'adhan ou à 6 heures au plus tard"
}

MAX_PAUSE_DAYS = 10
START_DATE = date(2026, 8, 17)

# --- CONNEXION GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data() -> pd.DataFrame:
    try:
        df = conn.read(ttl=0)
        expected_cols = ["date", "user", "status"]
        if df.empty or not all(col in df.columns for col in expected_cols):
            return pd.DataFrame(columns=expected_cols)
        df['date'] = pd.to_datetime(df['date']).dt.date
        return df
    except Exception:
        return pd.DataFrame(columns=["date", "user", "status"])

def save_entry(user: str, entry_date: date, status: str):
    df = load_data()
    df = df[~((df['user'] == user) & (df['date'] == entry_date))]
    new_row = pd.DataFrame([{"date": entry_date.isoformat(), "user": user, "status": status}])
    df['date'] = df['date'].astype(str)
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(data=updated_df)
    st.cache_data.clear()

def compute_user_metrics(user: str, df: pd.DataFrame, today: date):
    user_records = df[df['user'] == user].set_index('date')['status'].to_dict()
    
    curr = START_DATE
    streak = 0
    savers_bank = 0
    active_days_count = 0
    consecutive_success_counter = 0
    total_paused_days = sum(1 for status in user_records.values() if status == "paused")

    while curr < today:
        status = user_records.get(curr)
        if status == "completed":
            streak += 1
            active_days_count += 1
            consecutive_success_counter += 1
            if consecutive_success_counter == 7:
                savers_bank += 1
                consecutive_success_counter = 0
        elif status == "paused":
            pass
        else:
            if savers_bank > 0:
                savers_bank -= 1
                consecutive_success_counter = 0
            else:
                streak = 0
                consecutive_success_counter = 0
        curr += timedelta(days=1)

    today_status = user_records.get(today)
    if today_status == "completed":
        streak += 1
        active_days_count += 1
        consecutive_success_counter += 1
        if consecutive_success_counter == 7:
            savers_bank += 1
            consecutive_success_counter = 0

    return {
        "user": user,
        "goal": PARTICIPANTS[user],
        "streak": streak,
        "savers": savers_bank,
        "total_active": active_days_count,
        "paused_count": total_paused_days,
        "today_status": today_status,
        "history": user_records
    }

@st.dialog("Validation Quotidienne")
def checkin_dialog(user: str, today: date, metrics: dict):
    st.subheader(f"👋 Bonjour {user} !")
    st.info(f"🎯 **Objectif :** {metrics['goal']}")
    
    status = metrics["today_status"]
    
    if status == "completed":
        st.success("✅ Journée déjà validée !")
        if st.button("Fermer", use_container_width=True):
            st.rerun()
    elif status == "paused":
        st.warning("⏸️ Journée actuellement en pause.")
        if st.button("Reprendre et Valider Aujourd'hui", type="primary", use_container_width=True):
            save_entry(user, today, "completed")
            st.rerun()
    else:
        st.write("Avez-vous complété votre engagement aujourd'hui ?")
        col_ok, col_pause = st.columns(2)
        with col_ok:
            if st.button("🔥 Marquer comme fait", type="primary", use_container_width=True):
                save_entry(user, today, "completed")
                st.rerun()
        with col_pause:
            remaining_pauses = MAX_PAUSE_DAYS - metrics["paused_count"]
            if remaining_pauses > 0:
                if st.button(f"⏸️ Pause ({remaining_pauses} restants)", use_container_width=True):
                    save_entry(user, today, "paused")
                    st.rerun()
            else:
                st.error("Quota de pause atteint (10/10).")

@st.dialog("Calendrier d'Activité")
def calendar_dialog(user: str, metrics: dict, today: date):
    st.subheader(f"📅 Historique de {user}")
    st.caption(f"🎯 Objectif : {metrics['goal']}")
    
    user_history = metrics["history"]
    cal = calendar.Calendar(firstweekday=0)  # Lundi en premier
    month_days = cal.monthdatescalendar(today.year, today.month)
    
    mois_fr = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    st.write(f"### {mois_fr[today.month - 1]} {today.year}")
    
    # CSS Grid styles for strict 7-column layout on all screen sizes
    grid_css = """
    <style>
        .cal-grid {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 4px;
            width: 100%;
            margin-bottom: 12px;
        }
        .cal-header {
            font-weight: 700;
            font-size: 0.75rem;
            text-align: center;
            color: #888;
            padding: 4px 0;
        }
        .cal-cell {
            aspect-ratio: 1 / 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            line-height: 1.1;
        }
        .cell-empty { background: transparent; }
        .cell-completed { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
        .cell-paused { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
        .cell-missed { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
        .cell-today { background: #e0f2fe; color: #075985; border: 1px dashed #0284c7; }
        .cell-future { background: rgba(128,128,128,0.06); color: #9ca3af; }
        .cal-badge { font-size: 0.7rem; }
    </style>
    """
    
    # Build HTML grid
    headers = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    html_items = [f'<div class="cal-header">{h}</div>' for h in headers]
    
    for week in month_days:
        for d in week:
            if d.month != today.month:
                html_items.append('<div class="cal-cell cell-empty"></div>')
            else:
                status = user_history.get(d)
                day_num = d.day
                
                if status == "completed":
                    cls = "cell-completed"
                    icon = "🟢"
                elif status == "paused":
                    cls = "cell-paused"
                    icon = "⏸️"
                elif d > today:
                    cls = "cell-future"
                    icon = ""
                elif d == today:
                    cls = "cell-today"
                    icon = "⏳"
                else:
                    cls = "cell-missed"
                    icon = "🔴"
                    
                html_items.append(f'<div class="cal-cell {cls}">{day_num}<span class="cal-badge">{icon}</span></div>')
                
    st.markdown(grid_css + f'<div class="cal-grid">{"".join(html_items)}</div>', unsafe_allow_html=True)
    st.caption("🟢 Validé &nbsp;|&nbsp; 🔴 Manqué &nbsp;|&nbsp; ⏸️ Pause &nbsp;|&nbsp; ⏳ En attente &nbsp;|&nbsp; ⚪ Futur")
    
# --- APPLICATION ---
def main():
    today = date.today()
    
    if "authenticated_user" not in st.session_state:
        st.session_state.authenticated_user = None

    if not st.session_state.authenticated_user:
        st.title("🔒 Connexion au Défi")
        col_l1, col_l2 = st.columns([2, 1])
        with col_l1:
            selected_user = st.selectbox("Choisir votre profil", ["-- Choisir votre nom --"] + list(PARTICIPANTS.keys()))
            if st.button("Accéder au tableau de bord", type="primary", use_container_width=True):
                if selected_user != "-- Choisir votre nom --":
                    st.session_state.authenticated_user = selected_user
                    st.session_state.show_checkin_popup = True
                    st.rerun()
                else:
                    st.warning("Veuillez sélectionner votre nom.")
        return

    current_user = st.session_state.authenticated_user
    data = load_data()
    all_metrics = {u: compute_user_metrics(u, data, today) for u in PARTICIPANTS.keys()}
    current_metrics = all_metrics[current_user]

    # --- TOP HEADER WITH SIDE TEXT ---
    title_col, side_text_col, logout_col = st.columns([3, 4, 1.2], vertical_alignment="center")
    
    with title_col:
        st.title("🏆 Défi")
        st.caption(f"Connecté : **{current_user}** | {today.strftime('%d/%m/%Y')}")
        
    with side_text_col:
        st.markdown(
            """
            <div class="side-text-box">
                📌 <b>Règles rapides :</b> 7 jours d'affilée = 🛡️ 1 Bouclier gagné.<br>
                Les pauses (max 10) gèlent votre série sans la casser. Validation avant minuit !
            </div>
            """, 
            unsafe_allow_html=True
        )

    with logout_col:
        if st.button("Se déconnecter", use_container_width=True):
            st.session_state.authenticated_user = None
            st.rerun()
        if st.button("📝 Check-in", use_container_width=True, type="secondary"):
            checkin_dialog(current_user, today, current_metrics)

    if st.session_state.get("show_checkin_popup", False):
        st.session_state.show_checkin_popup = False
        checkin_dialog(current_user, today, current_metrics)

    st.divider()

    # --- LEADERBOARD ---
    sorted_users = sorted(all_metrics.values(), key=lambda x: (x["streak"], x["total_active"]), reverse=True)
    rank_icons = ["🥇", "🥈", "🥉", "4️⃣"]

    for idx, stat in enumerate(sorted_users):
        row_col1, row_col2, row_col3, row_col4 = st.columns([0.6, 3.5, 3.5, 1.4], vertical_alignment="center")
        
        icon = rank_icons[idx] if idx < len(rank_icons) else f"{idx+1}."
        row_col1.markdown(f"### {icon}")
        
        row_col2.markdown(f"**{stat['user']}**  \n<small>{stat['goal']}</small>", unsafe_allow_html=True)
        
        status_labels = {
            "completed": "<span style='color:green;'>✅ Validé</span>",
            "paused": "<span style='color:orange;'>⏸️ En pause</span>",
            None: "<span style='color:gray;'>⏳ En attente</span>"
        }
        today_label = status_labels.get(stat["today_status"], "<span style='color:gray;'>⏳ En attente</span>")
        
        row_col3.markdown(
            f"🔥 <b>{stat['streak']} j</b> &nbsp;|&nbsp; 🛡️ <b>{stat['savers']}</b> &nbsp;|&nbsp; "
            f"Total: {stat['total_active']} j &nbsp;|&nbsp; Aujourd'hui: {today_label}",
            unsafe_allow_html=True
        )
        
        if row_col4.button("📅 Historique", key=f"hist_{stat['user']}", use_container_width=True):
            calendar_dialog(stat['user'], stat, today)
            
        st.divider()

if __name__ == "__main__":
    main()

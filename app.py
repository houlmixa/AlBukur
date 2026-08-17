import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Défi Squad - Suivi d'Habitudes", page_icon="🔥", layout="centered")

# --- PARTICIPANTS ET OBJECTIFS ---
PARTICIPANTS = {
    "Alice": "Lire 20 pages & Boire 2L d'eau",
    "Bob": "Séance de sport (45 min)",
    "Charlie": "Coder 1h hors travail",
    "David": "10 000 pas & 8h de sommeil"
}

MAX_PAUSE_DAYS = 10
START_DATE = date(2026, 8, 1)  # Définissez ici la date de lancement du défi

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
    # Supprimer toute entrée existante pour ce jour/utilisateur avant de réécrire
    df = df[~((df['user'] == user) & (df['date'] == entry_date))]
    
    new_row = pd.DataFrame([{"date": entry_date.isoformat(), "user": user, "status": status}])
    df['date'] = df['date'].astype(str)
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(data=updated_df)
    st.cache_data.clear()

# --- MOTEUR DE CALCUL (SÉRIE, BOUCLIERS, PAUSES) ---
def compute_user_metrics(user: str, df: pd.DataFrame, today: date):
    user_records = df[df['user'] == user].set_index('date')['status'].to_dict()
    
    # Remplir automatiquement les jours passés manqués avec des boucliers si disponibles
    # Chronologie du début jusqu'à hier
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
            # Le mode pause gèle la série sans la briser
            pass
        else:
            # Jour manqué : tenter d'utiliser un bouclier
            if savers_bank > 0:
                savers_bank -= 1
                consecutive_success_counter = 0
                # La série est préservée
            else:
                streak = 0
                consecutive_success_counter = 0
        curr += timedelta(days=1)

    # Évaluation de la journée en cours
    today_status = user_records.get(today)
    if today_status == "completed":
        streak += 1
        active_days_count += 1
        consecutive_success_counter += 1
        if consecutive_success_counter == 7:
            savers_bank += 1
            consecutive_success_counter = 0
    elif today_status == "paused":
        pass

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

# --- FENÊTRES MODALES (DIALOGS) ---
@st.dialog("Validation Quotidienne")
def checkin_dialog(user: str, today: date, metrics: dict):
    st.subheader(f"👋 Bonjour {user} !")
    st.info(f"🎯 **Objectif du jour :** {metrics['goal']}")
    
    status = metrics["today_status"]
    
    if status == "completed":
        st.success("✅ Vous avez déjà validé votre journée aujourd'hui !")
        if st.button("Fermer", use_container_width=True):
            st.rerun()
    elif status == "paused":
        st.warning("⏸️ Votre défi est actuellement en pause pour aujourd'hui.")
        if st.button("Reprendre et Valider Aujourd'hui", type="primary", use_container_width=True):
            save_entry(user, today, "completed")
            st.success("Défi validé !")
            st.rerun()
    else:
        st.write("Avez-vous complété votre engagement aujourd'hui ?")
        
        col_ok, col_pause = st.columns(2)
        with col_ok:
            if st.button("🔥 Marquer comme fait", type="primary", use_container_width=True):
                save_entry(user, today, "completed")
                st.success("Objectif enregistré !")
                st.rerun()
                
        with col_pause:
            remaining_pauses = MAX_PAUSE_DAYS - metrics["paused_count"]
            if remaining_pauses > 0:
                if st.button(f"⏸️ Mettre en pause ({remaining_pauses} restants)", use_container_width=True):
                    save_entry(user, today, "paused")
                    st.info("Journée mise en pause. Votre série est gelée.")
                    st.rerun()
            else:
                st.error("Quota max de pauses atteint (10/10).")

@st.dialog("Calendrier d'Activité")
def calendar_dialog(user: str, metrics: dict, today: date):
    st.subheader(f"📅 Historique de {user}")
    st.caption(f"🎯 Objectif : {metrics['goal']}")
    
    user_history = metrics["history"]
    
    cal = calendar.Calendar(firstweekday=0)  # Lundi en premier
    month_days = cal.monthdatescalendar(today.year, today.month)
    
    mois_fr = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    st.write(f"### {mois_fr[today.month - 1]} {today.year}")
    
    headers = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    cols = st.columns(7)
    for i, h in enumerate(headers):
        cols[i].caption(f"**{h}**")
        
    for week in month_days:
        cols = st.columns(7)
        for i, d in enumerate(week):
            if d.month != today.month:
                cols[i].write("")
            else:
                status = user_history.get(d)
                if status == "completed":
                    cols[i].markdown(f"**{d.day}**\n\n🟢")
                elif status == "paused":
                    cols[i].markdown(f"**{d.day}**\n\n⏸️")
                elif d > today:
                    cols[i].markdown(f"{d.day}\n\n⚪")
                elif d == today:
                    cols[i].markdown(f"**{d.day}**\n\n⏳")
                else:
                    cols[i].markdown(f"{d.day}\n\n🔴")
                    
    st.caption("Légende : 🟢 Validé | 🔴 Manqué | ⏸️ Pause | ⏳ En attente | ⚪ Futur")

# --- APPLICATION PRINCIPALE ---
def main():
    today = date.today()
    
    # 1. Écran de connexion
    if "authenticated_user" not in st.session_state:
        st.session_state.authenticated_user = None

    if not st.session_state.authenticated_user:
        st.title("🔒 Connexion au Défi")
        st.write("Sélectionnez votre profil pour accéder au tableau de bord :")
        
        selected_user = st.selectbox("Choisir un profil", ["-- Choisir un nom --"] + list(PARTICIPANTS.keys()))
        
        if st.button("Accéder au tableau de bord", type="primary", use_container_width=True):
            if selected_user != "-- Choisir un nom --":
                st.session_state.authenticated_user = selected_user
                st.session_state.show_checkin_popup = True
                st.rerun()
            else:
                st.warning("Veuillez sélectionner votre nom dans la liste.")
        return

    # 2. Vue Authentifiée
    current_user = st.session_state.authenticated_user
    data = load_data()
    
    # Calcul des métriques pour tous les membres
    all_metrics = {u: compute_user_metrics(u, data, today) for u in PARTICIPANTS.keys()}
    current_metrics = all_metrics[current_user]

    # En-tête
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.title("🏆 Classement du Défi")
        st.caption(f"Connecté en tant que **{current_user}** | {today.strftime('%d/%m/%Y')}")
    with top_col2:
        if st.button("Se déconnecter", use_container_width=True):
            st.session_state.authenticated_user = None
            st.rerun()

    # Déclenchement automatique de la boîte de dialogue après connexion
    if st.session_state.get("show_checkin_popup", False):
        st.session_state.show_checkin_popup = False
        checkin_dialog(current_user, today, current_metrics)

    # 3. Tableau des scores
    # Tri par série ininterrompue décroissante, puis par total de jours actifs
    sorted_users = sorted(all_metrics.values(), key=lambda x: (x["streak"], x["total_active"]), reverse=True)

    st.write("---")
    rank_icons = ["🥇", "🥈", "🥉", "4️⃣"]

    for idx, stat in enumerate(sorted_users):
        with st.container():
            col_rank, col_info, col_stats, col_btn = st.columns([1, 4, 3, 2])
            
            icon = rank_icons[idx] if idx < len(rank_icons) else f"{idx+1}."
            col_rank.markdown(f"### {icon}")
            
            col_info.markdown(f"**{stat['user']}**\n\n_{stat['goal']}_")
            
            # Statut du jour
            status_labels = {
                "completed": "✅ Validé",
                "paused": "⏸️ En pause",
                None: "⏳ En attente"
            }
            today_label = status_labels.get(stat["today_status"], "⏳ En attente")
            
            col_stats.markdown(
                f"🔥 **Série : {stat['streak']} j** | 🛡️ **{stat['savers']}**\n\n"
                f"Actif : {stat['total_active']} j | Pauses : {stat['paused_count']}/{MAX_PAUSE_DAYS} | Aujourd'hui : {today_label}"
            )
            
            if col_btn.button("📅 Historique", key=f"hist_{stat['user']}", use_container_width=True):
                calendar_dialog(stat['user'], stat, today)
                
            st.divider()

    # Bouton manuel pour rouvrir la modal de check-in
    st.button("📝 Ouvrir le panneau de validation du jour", on_click=lambda: checkin_dialog(
        current_user, today, current_metrics
    ))

if __name__ == "__main__":
    main()

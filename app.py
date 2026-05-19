import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- 1. DATENBANK SETUP (Google Sheets) ---
# Verbindung zu Google Sheets herstellen
conn = st.connection("gsheets", type=GSheetsConnection)

# Daten laden. ttl=0 (Time-To-Live) sorgt dafür, dass die App bei 
# jedem Laden die frischen Daten zieht und nicht aus dem Zwischenspeicher.
try:
    df = conn.read(ttl=0)
except Exception as e:
    st.error("Fehler beim Verbinden mit dem Google Sheet. Sind die Secrets korrekt?")
    st.stop()

# --- 2. HILFSFUNKTIONEN ---
def get_hydrant(h_id):
    # Den passenden Hydranten im DataFrame suchen (als String vergleichen)
    treffer = df[df['id'].astype(str) == str(h_id)]
    if not treffer.empty:
        return treffer.iloc[0]
    return None

def update_hydrant(h_id, neuer_status, neue_bemerkung):
    # Die Zeile mit der passenden ID finden
    idx = df.index[df['id'].astype(str) == str(h_id)].tolist()
    if idx:
        df.at[idx[0], 'status'] = neuer_status
        df.at[idx[0], 'bemerkung'] = neue_bemerkung
        # Das komplette, aktualisierte Datenpaket zurück in Google Sheets schreiben
        conn.update(data=df)

# --- 3. STREAMLIT APP LOGIK ---
st.set_page_config(page_title="Hydranten-Verwaltung", page_icon="🚒")
st.title("🚒 Feuerwehr Hydranten-Verwaltung")

# Prüfen, ob eine ID per URL übergeben wurde (für den QR-Code)
query_params = st.query_params
hydrant_id_aus_url = query_params.get("id")

if hydrant_id_aus_url:
    # --- MODUS 1: EINZELANSICHT (via QR-Code) ---
    st.subheader(f"Hydrant {hydrant_id_aus_url} bearbeiten")
    
    hydrant_daten = get_hydrant(hydrant_id_aus_url)
    
    if hydrant_daten is not None:
        st.write(f"**Standort:** {hydrant_daten['ort']}")
        
        with st.form("edit_form"):
            status_liste = ["Einsatzbereit", "Defekt", "Eingeschränkt", "Prüfung fällig"]
            aktueller_status = str(hydrant_daten['status'])
            
            if aktueller_status not in status_liste:
                aktueller_status = "Einsatzbereit"
                
            neu_status = st.selectbox("Status", status_liste, index=status_liste.index(aktueller_status))
            
            # Leere Felder (NaN) aus Google Sheets abfangen
            aktuelle_bemerkung = hydrant_daten['bemerkung']
            if pd.isna(aktuelle_bemerkung):
                aktuelle_bemerkung = ""
                
            neu_bemerkung = st.text_area("Bemerkung", value=str(aktuelle_bemerkung))
            submit = st.form_submit_button("Änderungen speichern")
            
            if submit:
                update_hydrant(hydrant_id_aus_url, neu_status, neu_bemerkung)
                st.success("✅ Daten wurden erfolgreich in Google Sheets gespeichert!")
                # App neu laden, um Änderungen sofort zu zeigen
                st.rerun() 
                
        if st.button("Zurück zur Übersicht"):
            st.query_params.clear()
            st.rerun()
    else:
        st.error(f"Hydrant mit der ID {hydrant_id_aus_url} wurde in der Tabelle nicht gefunden.")

else:
    # --- MODUS 2: ÜBERSICHT ALLER HYDRANTEN ---
    st.subheader("Alle Hydranten in der Übersicht")
    
    # Tabelle anzeigen (ID-Spalte ohne Kommazahlen darstellen)
    if not df.empty:
        anzeige_df = df.copy()
        anzeige_df['id'] = anzeige_df['id'].astype(str)
        st.dataframe(anzeige_df, use_container_width=True, hide_index=True)
    else:
        st.info("Die Tabelle ist noch leer. Trage Hydranten ins Google Sheet ein!")
    
    st.info("💡 Tipp: Scanne einen Hydranten-QR-Code oder hänge `/?id=1` an die URL an.")
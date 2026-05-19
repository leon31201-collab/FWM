import streamlit as st
import pandas as pd
from urllib.parse import urlparse, parse_qs
from streamlit_gsheets import GSheetsConnection

try:
    import cv2
    import numpy as np
    QR_SUPPORTED = True
except ImportError:
    cv2 = None
    np = None
    QR_SUPPORTED = False

# --- 1. DATENBANK SETUP (Google Sheets) ---
# Verbindung zu Google Sheets herstellen
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Sheet URL (nicht ID!)
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1JIzjxSkveLcraKzZYSWaQu77AfMGk0ghxT4yuEXZo7I/edit"
    df = conn.read(spreadsheet=SHEET_URL, ttl=0)
except Exception as e:
    st.error(f"❌ Fehler beim Lesen des Sheets:")
    st.error(f"Typ: {type(e).__name__}")
    st.error(f"Message: {str(e)}")
    import traceback
    st.error(traceback.format_exc())
    st.info("Verwende Demo-Daten...")
    # Demo-Daten für Tests ohne Google Sheets
    df = pd.DataFrame({
        'id': [1, 2, 3],
        'ort': ['Hauptstraße 10', 'Bahnhofstraße 5', 'Marktplatz 3'],
        'status': ['Einsatzbereit', 'Defekt', 'Eingeschränkt'],
        'bemerkung': ['OK', 'Wartung nötig', 'Prüfung geplant']
    })
    conn = None

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
        if conn is not None:
            conn.update(data=df)
        else:
            st.info("ℹ️ Demo-Modus: Änderungen werden nicht gespeichert. Verbinde Google Sheets für Persistenz.")


def parse_qr_payload(payload):
    try:
        parsed = urlparse(payload)
        if parsed.scheme and parsed.netloc:
            qs = parse_qs(parsed.query)
            if 'id' in qs:
                return qs['id'][0]
    except Exception:
        pass
    return payload


def decode_qr_code(image_bytes):
    if not QR_SUPPORTED:
        return None
    try:
        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        detector = cv2.QRCodeDetector()
        data, points, _ = detector.detectAndDecode(img)
        if data:
            return data
    except Exception:
        pass
    return None

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
    
    # QR-Code Reader hinzufügen
    st.markdown("### QR-Code Reader")
    if not QR_SUPPORTED:
        st.warning("QR-Code-Decoder wird nicht unterstützt. Installiere `opencv-python` und starte die App neu.")
    st.info("Nutze die Kamera oder lade ein Bild des QR-Codes hoch.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📷 Kamera**")
        camera_image = st.camera_input("QR-Code fotografieren")
        if camera_image is not None:
            qr_text = decode_qr_code(camera_image.getvalue())
            if qr_text:
                hydrant_id = parse_qr_payload(qr_text)
                st.success(f"QR-Code erkannt: `{qr_text}`")
                if st.button("Hydranten-Datensatz öffnen", key="camera_button"):
                    st.experimental_set_query_params(id=hydrant_id)
                    st.experimental_rerun()
            else:
                st.error("Kein QR-Code erkannt. Bitte erneut fotografieren.")
    
    with col2:
        st.markdown("**📁 Datei-Upload**")
        uploaded_file = st.file_uploader("QR-Code Bild hochladen", type=["png", "jpg", "jpeg"])
        if uploaded_file is not None:
            qr_text = decode_qr_code(uploaded_file.getvalue())
            if qr_text:
                hydrant_id = parse_qr_payload(qr_text)
                st.success(f"QR-Code erkannt: `{qr_text}`")
                if st.button("Hydranten-Datensatz öffnen", key="upload_button"):
                    st.experimental_set_query_params(id=hydrant_id)
                    st.experimental_rerun()
            else:
                st.error("Kein QR-Code erkannt. Bitte ein anderes Bild hochladen.")

    # Tabelle anzeigen (ID-Spalte ohne Kommazahlen darstellen)
    if not df.empty:
        anzeige_df = df.copy()
        anzeige_df['id'] = anzeige_df['id'].astype(str)
        st.dataframe(anzeige_df, use_container_width=True, hide_index=True)
    else:
        st.info("Die Tabelle ist noch leer. Trage Hydranten ins Google Sheet ein!")
    
    st.info("💡 Tipp: Scanne einen Hydranten-QR-Code oder hänge `/?id=1` an die URL an.")
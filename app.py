import streamlit as st
import pandas as pd
from urllib.parse import urlparse, parse_qs
from streamlit_gsheets import GSheetsConnection
import requests
import base64
from io import BytesIO

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

def update_hydrant(h_id, neuer_status, neue_bemerkung, neue_bild_url=""):
    # Die Zeile mit der passenden ID finden
    idx = df.index[df['id'].astype(str) == str(h_id)].tolist()
    if idx:
        df.at[idx[0], 'status'] = neuer_status
        df.at[idx[0], 'bemerkung'] = neue_bemerkung
        if 'bild_url' in df.columns:
            df.at[idx[0], 'bild_url'] = neue_bild_url
        # Das komplette, aktualisierte Datenpaket zurück in Google Sheets schreiben
        if conn is not None:
            SHEET_URL = "https://docs.google.com/spreadsheets/d/1JIzjxSkveLcraKzZYSWaQu77AfMGk0ghxT4yuEXZo7I/edit"
            conn.update(spreadsheet=SHEET_URL, data=df)
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


def upload_image_to_imgbb(image_bytes):
    """Lädt ein Bild zu ImgBB hoch und gibt den Link zurück"""
    try:
        files = {'image': image_bytes}
        response = requests.post('https://imgbb.com/api/upload?key=4a34aef16e0fa7c02a6c38a9949c2230', files=files, timeout=10)

        if response.status_code == 200:
            try:
                data = response.json()
                if data.get('success'):
                    return data['data']['url']
                else:
                    error_msg = data.get('error', {}).get('message', 'Unbekannter Fehler')
                    st.error(f"ImgBB Error: {error_msg}")
            except Exception as json_e:
                st.error(f"JSON Parse Fehler: {str(json_e)}")
                st.error(f"Response: {response.text[:200]}")
        else:
            st.error(f"HTTP {response.status_code}: {response.text[:200]}")
    except Exception as e:
        st.error(f"Upload Fehler: {type(e).__name__}: {str(e)}")
    return None
# --- 3. STREAMLIT APP LOGIK ---
st.set_page_config(page_title="Hydranten-Verwaltung", page_icon="🚒")
st.title("🚒 Feuerwehr Hydranten-Verwaltung")

# Prüfen, ob eine ID per URL übergeben wurde (für den QR-Code)
query_params = st.query_params
hydrant_id_aus_url = query_params.get("id")

if hydrant_id_aus_url:
    # --- MODUS 1: EINZELANSICHT (via QR-Code) ---
    st.subheader(f"Hydrant {hydrant_id_aus_url}")

    hydrant_daten = get_hydrant(hydrant_id_aus_url)

    if hydrant_daten is not None:
        st.write(f"**Standort:** {hydrant_daten['ort']}")

        # Bild anzeigen, wenn vorhanden
        if 'bild_url' in hydrant_daten.index:
            bild_url = hydrant_daten['bild_url']
            if pd.notna(bild_url) and bild_url.strip():
                st.image(bild_url, width=300)

        # Nur Kamera-Input für Foto
        st.markdown("### 📸 Foto hochladen")
        camera_pic = st.camera_input("Mit Kamera fotografieren")
        if camera_pic is not None:
            st.info("📤 Bild wird hochgeladen...")
            new_bild_url = upload_image_to_imgbb(camera_pic.getvalue())
            if new_bild_url:
                st.success("✅ Bild hochgeladen!")
                st.image(new_bild_url, width=200)
                update_hydrant(hydrant_id_aus_url, str(hydrant_daten['status']), str(hydrant_daten.get('bemerkung', '')), new_bild_url)
                st.rerun()

        if st.button("Zurück zur Übersicht"):
            st.query_params.clear()
            st.rerun()
    else:
        st.error(f"Hydrant mit der ID {hydrant_id_aus_url} wurde in der Tabelle nicht gefunden.")

else:
    # --- MODUS 2: ÜBERSICHT & QR-CODE SCANNER ---
    st.subheader("Hydranten-Verwaltung")

    # QR-Code Scanner oder ID eingeben
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📷 QR-Code scannen")
        if not QR_SUPPORTED:
            st.warning("QR-Code-Decoder wird nicht unterstützt. Installiere `opencv-python` und starte die App neu.")

        camera_image = st.camera_input("QR-Code fotografieren")
        if camera_image is not None:
            qr_text = decode_qr_code(camera_image.getvalue())
            if qr_text:
                hydrant_id = parse_qr_payload(qr_text)
                st.success(f"✅ QR-Code erkannt!")
                st.query_params["id"] = hydrant_id
                st.rerun()
            else:
                st.error("❌ Kein QR-Code erkannt. Bitte erneut fotografieren.")

    with col2:
        st.markdown("### 📝 Oder ID eingeben")
        hydrant_id_input = st.text_input("Hydranten-ID", placeholder="z.B. FWM_HYD_xx")
        if st.button("Öffnen"):
            if hydrant_id_input:
                st.query_params["id"] = hydrant_id_input
                st.rerun()
            else:
                st.error("Bitte eine ID eingeben.")

    # Tabelle anzeigen & bearbeiten
    st.markdown("---")
    if not df.empty:
        st.markdown("### 📊 Hydranten-Tabelle")
        edited_df = st.data_editor(df, use_container_width=True, hide_index=True, num_rows="dynamic")

        # Änderungen speichern
        if not edited_df.equals(df):
            st.info("💾 Änderungen speichern...")
            if conn is not None:
                SHEET_URL = "https://docs.google.com/spreadsheets/d/1JIzjxSkveLcraKzZYSWaQu77AfMGk0ghxT4yuEXZo7I/edit"
                conn.update(spreadsheet=SHEET_URL, data=edited_df)
                st.success("✅ Änderungen in Google Sheets gespeichert!")
            else:
                st.warning("⚠️ Demo-Modus: Änderungen werden nicht gespeichert.")
    else:
        st.info("Die Tabelle ist noch leer. Trage Hydranten ins Google Sheet ein!")

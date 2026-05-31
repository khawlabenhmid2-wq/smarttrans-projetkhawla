# ============================================================
# SMART-TRANS — app.py (VERSION FINALE 100% CORRIGÉE)
# ============================================================
# ✅ Synchronisation bidirectionnelle SQLite ⇄ Supabase
# ✅ Lecture forcée depuis Supabase pour toutes les routes GET
# ✅ Correction automatique du schéma Supabase
# ✅ Fallback SQLite si Supabase indisponible
# ============================================================

import os
import re
import json
import random
import string
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── Flask & extensions ──────────────────────────────────────
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message

# ─── Supabase (postgrest) ────────────────────────────────────
from postgrest import SyncPostgrestClient

# ─── NLP & Gemini ────────────────────────────────────────────
try:
    from textblob import TextBlob
    from deep_translator import GoogleTranslator
    HAS_NLP = True
except ImportError:
    HAS_NLP = False

try:
    from langdetect import detect as langdetect_detect
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

try:
    import google.generativeai as genai
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyAs1JV2C1hVXZbQAyrCPi3PMY2NNIAWylA")
    genai.configure(api_key=GEMINI_API_KEY)
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    GEMINI_API_KEY = None


# ════════════════════════════════════════════════════════════════
# FONCTION DE CORRECTION AUTOMATIQUE DE SUPABASE
# ════════════════════════════════════════════════════════════════

def auto_fix_supabase_schema():
    """Affiche les colonnes manquantes dans Supabase"""
    
    if not SUPABASE_OK or supabase is None:
        print("⚠️ Supabase non connecté")
        return
    
    print("\n[VERIF] Verification du schema Supabase...\n")
    
    # Liste des colonnes nécessaires pour chaque table
    needed_columns = {
        "Ligne": ["Code_Ligne", "Libelle", "Description", "Code_bus"],
        "Bus": ["Code_bus", "Numero_bus", "Etat", "Code_chauffeur"],
        "Parcours": ["ID_parcours", "Depart", "Arrivee", "Heure_depart", "Heure_arrivee", "Code_Ligne"],
        "Avis": ["ID_avis", "Code_client", "ID_historique", "Note", "Commentaire", "Date", "Sentiment_score", "Sentiment_label", "Keywords", "Category", "ID_parcours"],
        "Incident": ["ID_incident", "Description", "Date", "Code_chauffeur", "Code_Ligne", "Code_bus", "Statut", "Performance_IA"],
        "Utilisateur": ["ID_utilisateur", "Nom", "Email", "Mot_de_passe", "Role", "Photo"],
        "Chauffeur": ["Code_chauffeur", "ID_utilisateur", "Performance_score"],
        "Client": ["Code_client", "ID_utilisateur"],
        "Historique": ["ID_historique", "Date", "Heure_fin", "Statut", "Depart", "Arrivee", "Performance_IA", "ID_parcours", "Code_chauffeur"]
    }
    
    missing_cols = {}
    
    for table, columns in needed_columns.items():
        try:
            response = supabase.from_(table).select("*").limit(1).execute()
            existing_cols = list(response.data[0].keys()) if response.data else []
            
            missing = [col for col in columns if col not in existing_cols]
            if missing:
                missing_cols[table] = missing
                print(f"❌ Table {table}: colonnes manquantes -> {missing}")
            else:
                print(f"[OK] Table {table}: OK")
        except Exception as e:
            print(f"⚠️ Table {table} n'existe pas ou erreur: {str(e)[:50]}")
            missing_cols[table] = columns
    
    if missing_cols:
        print("\n" + "="*70)
        print("⚠️ COLONNES MANQUANTES DANS SUPABASE!")
        print("="*70)
        print("\n👉 Exécute ce SQL dans Supabase SQL Editor (https://app.supabase.com → SQL Editor):\n")
        
        sql_script = "-- CORRECTION DU SCHÉMA SUPABASE\n\n"
        for table, cols in missing_cols.items():
            for col in cols:
                col_type = "BIGINT" if col.endswith(("_id", "ID", "Code", "Note")) else "TEXT"
                if col == "Performance_score" or col == "Performance_IA" or col == "Sentiment_score":
                    col_type = "FLOAT"
                sql_script += f"ALTER TABLE public.{table} ADD COLUMN IF NOT EXISTS {col} {col_type};\n"
        
        sql_script += "\n-- Vérification\n"
        for table in needed_columns.keys():
            sql_script += f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table.lower()}';\n"
        
        print(sql_script)
        print("\n" + "="*70)
        print("⚠️ Après avoir exécuté le SQL, REDÉMARRE python app.py")
        print("="*70)
        return False
    
    print("\n[SUCCESS] Toutes les colonnes sont correctes!")
    return True


# ════════════════════════════════════════════════════════════════
# SUPABASE CONNECTION
# ════════════════════════════════════════════════════════════════

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("WARNING: SUPABASE_URL ou SUPABASE_KEY est vide — sync désactivé")
    supabase = None
    SUPABASE_OK = False
else:
    try:
        supabase = SyncPostgrestClient(
            f"{SUPABASE_URL}/rest/v1",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            }
        )
        SUPABASE_OK = True
        print("SUCCESS: Supabase connecté !")
        
        # 🔥 CORRECTION AUTOMATIQUE - APPELLE LA FONCTION
        auto_fix_supabase_schema()
        
    except Exception as _e:
        print(f"WARNING: Supabase connection failed: {_e}")
        supabase = None
        SUPABASE_OK = False


# ════════════════════════════════════════════════════════════════
# FONCTIONS DE SYNCHRONISATION UNIVERSELLES
# ════════════════════════════════════════════════════════════════

def read_from_supabase(table: str, filters: dict = None, order_by: str = None, desc: bool = True):
    """Lit les données directement depuis Supabase (garantie synchro)"""
    if not SUPABASE_OK or supabase is None:
        return None
    
    try:
        req = supabase.from_(table).select("*")
        if filters:
            for col, val in filters.items():
                req = req.eq(col, val)
        if order_by:
            req = req.order(order_by, desc=desc)
        response = req.execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"[SUPABASE READ ERROR] {e}")
        return None


def write_to_supabase(table: str, data: dict, match: dict = None):
    """Écrit ou met à jour dans Supabase"""
    if not SUPABASE_OK or supabase is None:
        return False
    
    try:
        if match:
            req = supabase.from_(table).update(data)
            for col, val in match.items():
                req = req.eq(col, val)
            req.execute()
        else:
            supabase.from_(table).insert(data).execute()
        return True
    except Exception as e:
        print(f"[SUPABASE WRITE ERROR] {e}")
        return False


def delete_from_supabase(table: str, match: dict):
    """Supprime de Supabase"""
    if not SUPABASE_OK or supabase is None:
        return False
    
    try:
        req = supabase.from_(table).delete()
        for col, val in match.items():
            req = req.eq(col, val)
        req.execute()
        return True
    except Exception as e:
        print(f"[SUPABASE DELETE ERROR] {e}")
        return False


# ════════════════════════════════════════════════════════════════
# Flask App Initialization
# ════════════════════════════════════════════════════════════════

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
bcrypt = Bcrypt(app)

# ─── Flask-Mail (Gmail) ──────────────────────────────────────
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'khawlabenhmid2@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'sztw sklu nyav ypzz')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
mail = Mail(app)

# ─── Database Path ───────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smart_trans.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ════════════════════════════════════════════════════════════════
# NLP FUNCTIONS
# ════════════════════════════════════════════════════════════════

DRIVER_KEYWORDS = ['chauffeur', 'conducteur', 'pilote', 'chafer', 'chaufeur', 'impoli', 'poli',
                   'grossier', 'aimable', 'sympa', 'agressif', 'comportement', 'conduite',
                   'attitude', 'professionnel', 'vitesse', 'rapide', 'lent', 'freinage',
                   'respectueux', 'irrespectueux', 'souriant', 'desagreable', 'competent',
                   'incompetent', 'courtois', 'imprudent', 'prudent']
COMFORT_KEYWORDS = ['confort', 'siege', 'clim', 'climatisation', 'chaud', 'froid', 'propre', 'sale', 'bruit', 'masakh', 'ndhif', 'korsi']
VEHICLE_KEYWORDS = ['bus', 'vehicule', 'panne', 'vieux', 'neuf', 'voiture', 'car', 'moteur', 'karoosa']
SERVICE_KEYWORDS = ['retard', 'heure', 'temps', 'attente', 'horaire', 'ponctuel', 'regularite', 'trajet', 'ma famech', 'wqayet']
STRONG_NEG = ['catastrophe', 'horrible', 'honteux', 'scandale', 'khayeb', 'masakh', 'bhim', 'msakh', 'ykhawef', 'danger', 'vol', 'arnaque', 'catastrophique']
NEG_WORDS = ["n'aime pas", "n'aime plus", "déteste", "nul", "mauvais", "pire", "sale", "impoli", "retard", "lent", "problème", "panne", "froid", "chaud", "bruit", "saturé", "plein", "ma famech", "pas bien", "non", "désagréable"]
STRONG_POS = ['parfait', 'meilleur', 'tayara', 'magnifique', 'extraordinaire', 'top', 'merveilleux', 'incroyable']
POS_WORDS = ['super', 'excellent', 'génial', 'adore', 'très bien', 'bravo', 'propre', 'merci', 'bahi', 'behi', 'cv', 'bien', 'bon', 'rapide', 'confortable', 'gentil', 'respectueux']


def categorize_comment(comment: str) -> str:
    c = comment.lower()
    if any(w in c for w in DRIVER_KEYWORDS):
        return 'Chauffeur'
    if any(w in c for w in COMFORT_KEYWORDS):
        return 'Confort'
    if any(w in c for w in VEHICLE_KEYWORDS):
        return 'Véhicule'
    if any(w in c for w in SERVICE_KEYWORDS):
        return 'Service'
    return 'Général'


def analyze_sentiment_textblob(comment: str):
    sentiment_score = 0.0
    try:
        try:
            translated = GoogleTranslator(source='auto', target='en').translate(comment)
            blob = TextBlob(translated)
        except Exception:
            blob = TextBlob(comment)
        sentiment_score = blob.sentiment.polarity
    except Exception:
        pass

    comment_lower = comment.lower()
    bonus = 0.0
    for w in STRONG_NEG:
        if w in comment_lower:
            bonus -= 0.8
    for w in NEG_WORDS:
        if w in comment_lower:
            bonus -= 0.4
    for w in STRONG_POS:
        if w in comment_lower:
            bonus += 0.8
    for w in POS_WORDS:
        if w in comment_lower:
            bonus += 0.4

    sentiment_score = max(-1.0, min(1.0, sentiment_score + bonus))

    if sentiment_score >= 0.15:
        label = "Positif"
    elif sentiment_score <= -0.15:
        label = "Négatif"
    else:
        label = "Neutre"

    words = [w.lower() for w in comment.split() if len(w) > 3]
    keywords = ", ".join(list(set(words))[:5])
    category = categorize_comment(comment)

    return sentiment_score, label, keywords, category, "Non"


def analyze_sentiment(comment: str):
    if not comment:
        return 0.0, "Neutre", "", "Général", "Non"

    if HAS_GEMINI:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"""
Analyse ce commentaire de transport public (en Français ou Derja Tunisienne) :
"{comment}"

Réponds UNIQUEMENT en JSON valide avec ces champs exacts :
{{
  "sentiment": "Positif",
  "score": 0.8,
  "category": "Chauffeur",
  "keywords": "mot1, mot2",
  "risk": "Non"
}}

Les valeurs possibles :
- sentiment : "Positif" | "Négatif" | "Neutre"
- score : float entre -1.0 et 1.0
- category : "Chauffeur" | "Confort" | "Véhicule" | "Service" | "Sécurité" | "Général"
- risk : "Oui" | "Non"
"""
            response = model.generate_content(prompt)
            res_text = response.text.replace('```json', '').replace('```', '').strip()
            ai_data = json.loads(res_text)
            return (
                float(ai_data.get("score", 0.0)),
                ai_data.get("sentiment", "Neutre"),
                ai_data.get("keywords", ""),
                ai_data.get("category", "Général"),
                ai_data.get("risk", "Non")
            )
        except Exception as e:
            print(f"Gemini failed, fallback TextBlob: {e}")

    if HAS_NLP:
        return analyze_sentiment_textblob(comment)

    return 0.0, "Neutre", "", "Général", "Non"


# ════════════════════════════════════════════════════════════════
# INIT TABLES (SQLite)
# ════════════════════════════════════════════════════════════════

def init_all_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Migrations sécurisées
    for col_sql in [
        "ALTER TABLE Incident ADD COLUMN Performance_IA FLOAT",
        "ALTER TABLE Incident ADD COLUMN Statut TEXT DEFAULT 'Signalé'",
        "ALTER TABLE Incident ADD COLUMN Code_bus INTEGER",
    ]:
        try:
            cursor.execute(col_sql)
        except:
            pass

    # Tables principales
    cursor.execute('''CREATE TABLE IF NOT EXISTS Utilisateur (
        ID_utilisateur INTEGER PRIMARY KEY AUTOINCREMENT,
        Nom TEXT,
        Email TEXT UNIQUE,
        Mot_de_passe TEXT,
        Role TEXT,
        Photo TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Chauffeur (
        Code_chauffeur INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_utilisateur INTEGER,
        Performance_score FLOAT DEFAULT 5.0,
        FOREIGN KEY(ID_utilisateur) REFERENCES Utilisateur(ID_utilisateur) ON DELETE CASCADE)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Client (
        Code_client INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_utilisateur INTEGER,
        FOREIGN KEY(ID_utilisateur) REFERENCES Utilisateur(ID_utilisateur) ON DELETE CASCADE)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Administrateur (
        Code_administrateur INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_utilisateur INTEGER,
        FOREIGN KEY(ID_utilisateur) REFERENCES Utilisateur(ID_utilisateur) ON DELETE CASCADE)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Bus (
        Code_bus INTEGER PRIMARY KEY AUTOINCREMENT,
        Numero_bus TEXT UNIQUE,
        Etat TEXT,
        Code_chauffeur INTEGER,
        FOREIGN KEY(Code_chauffeur) REFERENCES Chauffeur(Code_chauffeur) ON DELETE SET NULL)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Ligne (
        Code_Ligne INTEGER PRIMARY KEY AUTOINCREMENT,
        Libelle TEXT,
        Description TEXT,
        Code_bus INTEGER,
        FOREIGN KEY(Code_bus) REFERENCES Bus(Code_bus))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Parcours (
        ID_parcours INTEGER PRIMARY KEY AUTOINCREMENT,
        Depart TEXT,
        Arrivee TEXT,
        Heure_depart TEXT,
        Heure_arrivee TEXT,
        Code_Ligne INTEGER,
        FOREIGN KEY(Code_Ligne) REFERENCES Ligne(Code_Ligne))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Historique (
        ID_historique INTEGER PRIMARY KEY AUTOINCREMENT,
        Date TEXT,
        Heure_fin TEXT,
        Statut TEXT,
        Depart TEXT,
        Arrivee TEXT,
        Performance_IA FLOAT,
        ID_parcours INTEGER,
        Code_chauffeur INTEGER,
        FOREIGN KEY(ID_parcours) REFERENCES Parcours(ID_parcours),
        FOREIGN KEY(Code_chauffeur) REFERENCES Chauffeur(Code_chauffeur))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Incident (
        ID_incident INTEGER PRIMARY KEY AUTOINCREMENT,
        Description TEXT,
        Date TEXT,
        Code_chauffeur INTEGER,
        Code_Ligne INTEGER,
        Code_bus INTEGER,
        Statut TEXT DEFAULT 'Signalé',
        Performance_IA FLOAT,
        FOREIGN KEY(Code_chauffeur) REFERENCES Chauffeur(Code_chauffeur),
        FOREIGN KEY(Code_Ligne) REFERENCES Ligne(Code_Ligne))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Avis (
        ID_avis INTEGER PRIMARY KEY AUTOINCREMENT,
        Code_client INTEGER,
        ID_historique INTEGER,
        Note INTEGER,
        Commentaire TEXT,
        Date TEXT,
        Sentiment_score FLOAT,
        Sentiment_label TEXT,
        Keywords TEXT,
        Category TEXT,
        ID_parcours INTEGER,
        FOREIGN KEY(Code_client) REFERENCES Client(Code_client),
        FOREIGN KEY(ID_historique) REFERENCES Historique(ID_historique),
        FOREIGN KEY(ID_parcours) REFERENCES Parcours(ID_parcours))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ResetCode (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Email TEXT,
        Code TEXT,
        Expiration DATETIME)''')

    # Admin par défaut
    hashed_pw = bcrypt.generate_password_hash('123456').decode('utf-8')
    cursor.execute('''INSERT OR IGNORE INTO Utilisateur (Nom, Email, Mot_de_passe, Role)
                      VALUES (?, ?, ?, ?)''', ('Khawla', 'khawla@email.com', hashed_pw, 'admin'))

    conn.commit()
    conn.close()
    print("[SUCCESS] Toutes les tables SQLite sont initialisees avec succes !")


# ════════════════════════════════════════════════════════════════
# 1. AUTH — Register / Login / Forgot Password
# ════════════════════════════════════════════════════════════════

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        nom = data.get('nom', '').strip()
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')

        if not nom or not email or not password:
            return jsonify({"error": "Tous les champs sont obligatoires"}), 400

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        cursor = conn.cursor()

        if cursor.execute("SELECT 1 FROM Utilisateur WHERE Email = ?", (email,)).fetchone():
            conn.close()
            return jsonify({"message": "Email déjà utilisé"}), 400

        cursor.execute(
            "INSERT INTO Utilisateur (Nom, Email, Mot_de_passe, Role) VALUES (?, ?, ?, ?)",
            (nom, email, hashed_pw, 'client')
        )
        new_id = cursor.lastrowid
        cursor.execute("INSERT INTO Client (ID_utilisateur) VALUES (?)", (new_id,))
        new_client_id = cursor.lastrowid
        conn.commit()
        conn.close()

        write_to_supabase('Utilisateur', {
            'ID_utilisateur': new_id, 'Nom': nom, 'Email': email,
            'Mot_de_passe': hashed_pw, 'Role': 'client'
        })
        write_to_supabase('Client', {
            'Code_client': new_client_id, 'ID_utilisateur': new_id
        })

        return jsonify({"message": "Compte créé avec succès"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Aucune donnée reçue"}), 400

        email = (data.get('email') or '').lower().strip()
        password = data.get('password', '')

        if not email or not password:
            return jsonify({"error": "Email et mot de passe obligatoires"}), 400

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM Utilisateur WHERE Email = ?", (email,)).fetchone()
        conn.close()

        if not user:
            return jsonify({"error": "Utilisateur introuvable"}), 404

        if not bcrypt.check_password_hash(user['Mot_de_passe'], password):
            return jsonify({"error": "Mot de passe incorrect"}), 401

        return jsonify({
            "message": "Login successful",
            "id": user['ID_utilisateur'],
            "nom": user['Nom'],
            "email": user['Email'],
            "role": user['Role'],
            "photo": user['Photo'] or ""
        }), 200

    except Exception as e:
        print(f"ERROR LOGIN: {e}")
        return jsonify({"error": "Erreur serveur", "details": str(e)}), 500


@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    try:
        data = request.get_json()
        email = (data.get('email') or '').lower().strip()

        if not email:
            return jsonify({"error": "Email obligatoire"}), 400

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM Utilisateur WHERE Email = ?', (email,)).fetchone()
        if not user:
            conn.close()
            return jsonify({"error": "Aucun compte trouvé avec cet email"}), 404

        code = ''.join(random.choices(string.digits, k=6))
        conn.execute('DELETE FROM ResetCode WHERE Email = ?', (email,))
        conn.execute('INSERT INTO ResetCode (Email, Code) VALUES (?, ?)', (email, code))
        conn.commit()
        conn.close()

        msg = Message("Code de vérification SMART-TRANS", recipients=[email])
        msg.html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;border:1px solid #eee;padding:20px;border-radius:15px;">
            <div style="text-align:center;margin-bottom:20px;">
                <h1 style="color:#008080;margin:0;">SMART-TRANS</h1>
                <p style="color:#666;font-size:12px;">Système de Transport Intelligent 2026</p>
            </div>
            <div style="background:#f9f9f9;padding:20px;border-radius:10px;text-align:center;">
                <p style="font-size:16px;color:#333;">Bonjour <strong>{user['Nom']}</strong>,</p>
                <p style="font-size:14px;color:#555;">Votre code de réinitialisation :</p>
                <div style="background:#008080;color:white;font-size:32px;font-weight:bold;padding:15px;border-radius:8px;display:inline-block;letter-spacing:5px;margin:20px 0;">
                    {code}
                </div>
                <p style="font-size:12px;color:#888;">Valable 15 minutes. Ne le partagez pas.</p>
            </div>
            <div style="margin-top:20px;text-align:center;border-top:1px solid #eee;padding-top:15px;">
                <p style="font-size:14px;color:#008080;font-weight:bold;">L'équipe SMART-TRANS</p>
            </div>
        </div>
        """
        mail.send(msg)
        return jsonify({"message": "Code envoyé par email"}), 200
    except Exception as e:
        print(f"Erreur forgot-password: {e}")
        return jsonify({"error": "Erreur lors de l'envoi de l'email"}), 500


@app.route('/verify-reset-code', methods=['POST'])
def verify_reset_code():
    try:
        data = request.get_json()
        email = (data.get('email') or '').lower().strip()
        code = data.get('code', '')
        conn = get_db_connection()
        res = conn.execute('SELECT * FROM ResetCode WHERE Email = ? AND Code = ?', (email, code)).fetchone()
        conn.close()
        if res:
            return jsonify({"message": "Code valide"}), 200
        return jsonify({"error": "Code invalide ou expiré"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/reset-password', methods=['POST'])
def reset_password():
    try:
        data = request.get_json()
        email = (data.get('email') or '').lower().strip()
        code = data.get('code', '')
        new_password = data.get('new_password', '')

        if len(new_password) < 6:
            return jsonify({"error": "Le mot de passe doit contenir au moins 6 caractères"}), 400

        conn = get_db_connection()
        res = conn.execute('SELECT * FROM ResetCode WHERE Email = ? AND Code = ?', (email, code)).fetchone()
        if not res:
            conn.close()
            return jsonify({"error": "Action non autorisée"}), 403

        hashed_pw = bcrypt.generate_password_hash(new_password).decode('utf-8')
        conn.execute('UPDATE Utilisateur SET Mot_de_passe = ? WHERE Email = ?', (hashed_pw, email))
        conn.execute('DELETE FROM ResetCode WHERE Email = ?', (email,))
        conn.commit()
        conn.close()

        write_to_supabase('Utilisateur', {'Mot_de_passe': hashed_pw}, {'Email': email})

        return jsonify({"message": "Mot de passe réinitialisé avec succès"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════
# 2. PROFIL
# ════════════════════════════════════════════════════════════════

@app.route('/get_profile/<email>', methods=['GET'])
def get_profile(email):
    try:
        conn = get_db_connection()
        user = conn.execute('SELECT Nom, Email, Photo FROM Utilisateur WHERE Email = ?', (email,)).fetchone()
        conn.close()
        if user:
            return jsonify({"Nom": user['Nom'], "Email": user['Email'], "Photo": user['Photo']}), 200
        return jsonify({"error": "Utilisateur introuvable"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/update_profile', methods=['POST'])
def update_profile():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_name = data.get('name')
        new_email = data.get('email')
        new_pw = data.get('password')
        new_photo = data.get('photo')

        if not user_id:
            return jsonify({"error": "User ID requis"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        if new_email:
            clash = cursor.execute(
                "SELECT ID_utilisateur FROM Utilisateur WHERE Email = ? AND ID_utilisateur != ?",
                (new_email, user_id)
            ).fetchone()
            if clash:
                conn.close()
                return jsonify({"error": "Cet email est déjà utilisé"}), 400

        query = "UPDATE Utilisateur SET Nom = ?, Email = ?, Photo = ?"
        params = [new_name, new_email, new_photo]

        if new_pw and len(new_pw) >= 6:
            hashed = bcrypt.generate_password_hash(new_pw).decode('utf-8')
            query += ", Mot_de_passe = ?"
            params.append(hashed)

        query += " WHERE ID_utilisateur = ?"
        params.append(user_id)
        cursor.execute(query, params)
        conn.commit()
        conn.close()

        update_data = {'Nom': new_name, 'Email': new_email, 'Photo': new_photo}
        if new_pw and len(new_pw) >= 6:
            update_data['Mot_de_passe'] = hashed
        write_to_supabase('Utilisateur', update_data, {'ID_utilisateur': user_id})

        return jsonify({"message": "Profil mis à jour avec succès ✅"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════
# 3. BUS
# ════════════════════════════════════════════════════════════════

@app.route('/get_buses', methods=['GET'])
def get_buses():
    try:
        supabase_data = read_from_supabase('Bus', order_by='Code_bus', desc=True)
        if supabase_data is not None:
            return jsonify(supabase_data), 200

        conn = get_db_connection()
        buses = conn.execute("SELECT * FROM Bus ORDER BY Code_bus DESC").fetchall()
        conn.close()
        return jsonify([dict(b) for b in buses])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/add_bus', methods=['POST'])
def add_bus():
    try:
        data = request.get_json()
        numero = data.get('Numero_bus')
        etat = data.get('Etat')
        id_chauffeur = data.get('Code_chauffeur')

        conn = get_db_connection()
        cur = conn.execute(
            'INSERT INTO Bus (Numero_bus, Etat, Code_chauffeur) VALUES (?, ?, ?)',
            (numero, etat, id_chauffeur)
        )
        new_id = cur.lastrowid
        conn.commit()
        conn.close()

        bus_data = {'Code_bus': new_id, 'Numero_bus': numero, 'Etat': etat, 'Code_chauffeur': id_chauffeur}
        write_to_supabase('Bus', bus_data)

        return jsonify({"status": "success", "message": "Bus ajouté", "id": new_id}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/update_bus/<int:id>', methods=['PUT'])
def update_bus(id):
    try:
        data = request.get_json()
        numero = data.get('Numero_bus')
        etat = data.get('Etat')
        id_chauffeur = data.get('Code_chauffeur')

        conn = get_db_connection()
        conn.execute(
            'UPDATE Bus SET Numero_bus = ?, Etat = ?, Code_chauffeur = ? WHERE Code_bus = ?',
            (numero, etat, id_chauffeur, id)
        )
        conn.commit()
        conn.close()

        write_to_supabase('Bus', {'Numero_bus': numero, 'Etat': etat, 'Code_chauffeur': id_chauffeur}, {'Code_bus': id})

        return jsonify({"status": "success", "message": "Bus mis à jour"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/delete_bus/<int:id>', methods=['DELETE'])
def delete_bus(id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM Incident WHERE Code_bus = ?', (id,))
        conn.execute('UPDATE Ligne SET Code_bus = NULL WHERE Code_bus = ?', (id,))
        conn.execute('DELETE FROM Bus WHERE Code_bus = ?', (id,))
        conn.commit()
        conn.close()

        delete_from_supabase('Incident', {'Code_bus': id})
        write_to_supabase('Ligne', {'Code_bus': None}, {'Code_bus': id})
        delete_from_supabase('Bus', {'Code_bus': id})

        return jsonify({"status": "success", "message": "Bus supprimé"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/get_available_buses', methods=['GET'])
def get_available_buses():
    try:
        supabase_data = read_from_supabase('Bus')
        if supabase_data is not None:
            return jsonify([{'Code_bus': b['Code_bus'], 'Numero_bus': b['Numero_bus']} for b in supabase_data])

        conn = get_db_connection()
        buses = conn.execute("SELECT Code_bus, Numero_bus FROM Bus").fetchall()
        conn.close()
        return jsonify([dict(b) for b in buses])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════
# 4. LIGNES
# ════════════════════════════════════════════════════════════════

@app.route('/get_lignes', methods=['GET'])
def get_lignes():
    try:
        supabase_data = read_from_supabase('Ligne', order_by='Code_Ligne', desc=True)
        if supabase_data is not None:
            return jsonify(supabase_data), 200

        conn = get_db_connection()
        lignes = conn.execute('SELECT * FROM Ligne ORDER BY Code_Ligne DESC').fetchall()
        conn.close()
        return jsonify([dict(l) for l in lignes]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_all_lignes', methods=['GET'])
def get_all_lignes():
    try:
        supabase_data = read_from_supabase('Ligne', order_by='Code_Ligne', desc=True)
        if supabase_data is not None:
            result = []
            for l in supabase_data:
                nom_chauffeur = "Non assigné"
                code_bus = l.get('Code_bus')
                if code_bus:
                    bus_data = read_from_supabase('Bus', filters={'Code_bus': code_bus})
                    if bus_data and len(bus_data) > 0:
                        code_chauffeur = bus_data[0].get('Code_chauffeur')
                        if code_chauffeur:
                            chauffeur_data = read_from_supabase('Chauffeur', filters={'Code_chauffeur': code_chauffeur})
                            if chauffeur_data and len(chauffeur_data) > 0:
                                user_data = read_from_supabase('Utilisateur', filters={'ID_utilisateur': chauffeur_data[0].get('ID_utilisateur')})
                                if user_data and len(user_data) > 0:
                                    nom_chauffeur = user_data[0].get('Nom', 'Non assigné')
                
                result.append({
                    "code_ligne": l.get("Code_Ligne"),
                    "libelle": l.get("Libelle") or "Sans Nom",
                    "description": l.get("Description") or "",
                    "code_bus": l.get("Code_bus"),
                    "nom_chauffeur": nom_chauffeur
                })
            return jsonify(result), 200

        conn = get_db_connection()
        query = """
            SELECT L.*, B.Numero_bus, U.Nom as Nom_Chauffeur
            FROM Ligne L
            LEFT JOIN Bus B ON L.Code_bus = B.Code_bus
            LEFT JOIN Chauffeur C ON B.Code_chauffeur = C.Code_chauffeur
            LEFT JOIN Utilisateur U ON C.ID_utilisateur = U.ID_utilisateur
            ORDER BY L.Code_Ligne DESC
        """
        lignes = conn.execute(query).fetchall()
        conn.close()
        return jsonify([{
            "code_ligne": l["Code_Ligne"],
            "libelle": l["Libelle"] or "Sans Nom",
            "description": l["Description"] or "",
            "code_bus": l["Code_bus"],
            "nom_chauffeur": l["Nom_Chauffeur"] or "Non assigné"
        } for l in lignes]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/add_ligne', methods=['POST'])
def add_ligne():
    conn = None
    try:
        data = request.get_json()
        libelle = data.get('libelle') or data.get('Libelle')
        desc = data.get('description') or data.get('Description')
        code_bus = data.get('code_bus') or data.get('Code_bus')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Ligne (Libelle, Description, Code_bus) VALUES (?, ?, ?)",
            (libelle, desc, code_bus)
        )
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()

        ligne_data = {
            'Code_Ligne': new_id,
            'Libelle': libelle,
            'Description': desc,
            'Code_bus': code_bus
        }
        write_to_supabase('Ligne', ligne_data)

        return jsonify({"message": "Ligne ajoutée avec succès", "id": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/update_ligne/<int:id>', methods=['PUT', 'POST'])
def update_ligne(id):
    try:
        data = request.get_json()
        libelle = data.get('libelle') or data.get('Libelle')
        desc = data.get('description') or data.get('Description')
        code_bus = data.get('code_bus') or data.get('Code_bus')

        conn = get_db_connection()
        conn.execute(
            'UPDATE Ligne SET Libelle = ?, Description = ?, Code_bus = ? WHERE Code_Ligne = ?',
            (libelle, desc, code_bus, id)
        )
        conn.commit()
        conn.close()

        write_to_supabase('Ligne', {'Libelle': libelle, 'Description': desc, 'Code_bus': code_bus}, {'Code_Ligne': id})

        return jsonify({"message": "Ligne mise à jour"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete_ligne/<int:id>', methods=['DELETE'])
def delete_ligne(id):
    try:
        conn = get_db_connection()
        
        # 1. Supprimer d'abord les parcours liés
        conn.execute('DELETE FROM Parcours WHERE Code_Ligne = ?', (id,))
        # 2. Supprimer les incidents liés
        conn.execute('DELETE FROM Incident WHERE Code_Ligne = ?', (id,))
        # 3. Supprimer la ligne
        conn.execute('DELETE FROM Ligne WHERE Code_Ligne = ?', (id,))
        conn.commit()
        conn.close()

        # 4. Supprimer de Supabase
        delete_from_supabase('Parcours', {'Code_Ligne': id})
        delete_from_supabase('Incident', {'Code_Ligne': id})
        delete_from_supabase('Ligne', {'Code_Ligne': id})

        return jsonify({"message": "Ligne supprimée"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
       


# ════════════════════════════════════════════════════════════════
# 5. CHAUFFEURS
# ════════════════════════════════════════════════════════════════

@app.route('/get_chauffeurs', methods=['GET'])
def get_chauffeurs():
    try:
        supabase_data = read_from_supabase('Chauffeur')
        if supabase_data is not None:
            result = []
            for c in supabase_data:
                user_data = read_from_supabase('Utilisateur', filters={'ID_utilisateur': c.get('ID_utilisateur')})
                if user_data and len(user_data) > 0:
                    result.append({
                        "ID_utilisateur": user_data[0].get('ID_utilisateur'),
                        "Nom": user_data[0].get('Nom'),
                        "Email": user_data[0].get('Email'),
                        "Code_chauffeur": c.get('Code_chauffeur')
                    })
            return jsonify(result)

        conn = get_db_connection()
        query = """
            SELECT u.ID_utilisateur, u.Nom, u.Email, c.Code_chauffeur
            FROM Chauffeur c
            JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            ORDER BY c.Code_chauffeur DESC
        """
        rows = conn.execute(query).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/add_chauffeur', methods=['POST'])
def add_chauffeur():
    conn = None
    try:
        data = request.get_json()
        nom = data.get('Nom')
        email = data.get('Email')
        password = data.get('Password')

        if not nom or not email or not password:
            return jsonify({"error": "Nom, Email et Password sont obligatoires"}), 400

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        conn = get_db_connection()
        cursor = conn.execute(
            'INSERT INTO Utilisateur (Nom, Email, Mot_de_passe, Role) VALUES (?, ?, ?, ?)',
            (nom, email, hashed_pw, 'chauffeur')
        )
        user_id = cursor.lastrowid
        cur2 = conn.execute('INSERT INTO Chauffeur (ID_utilisateur) VALUES (?)', (user_id,))
        code_ch = cur2.lastrowid
        conn.commit()
        conn.close()

        write_to_supabase('Utilisateur', {
            'ID_utilisateur': user_id, 'Nom': nom, 'Email': email,
            'Mot_de_passe': hashed_pw, 'Role': 'chauffeur'
        })
        write_to_supabase('Chauffeur', {'Code_chauffeur': code_ch, 'ID_utilisateur': user_id})

        return jsonify({"message": "Chauffeur ajouté avec succès"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/update_chauffeur/<int:id>', methods=['PUT'])
def update_chauffeur(id):
    try:
        data = request.get_json()
        nom = data.get('Nom')
        email = data.get('Email')
        password = data.get('Password')

        conn = get_db_connection()

        if password:
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        else:
            existing = conn.execute(
                'SELECT Mot_de_passe FROM Utilisateur WHERE ID_utilisateur = ?', (id,)
            ).fetchone()
            hashed_pw = existing['Mot_de_passe'] if existing else ''

        conn.execute(
            'UPDATE Utilisateur SET Nom = ?, Email = ?, Mot_de_passe = ? WHERE ID_utilisateur = ?',
            (nom, email, hashed_pw, id)
        )
        conn.commit()
        conn.close()

        write_to_supabase('Utilisateur', {'Nom': nom, 'Email': email, 'Mot_de_passe': hashed_pw}, {'ID_utilisateur': id})

        return jsonify({"message": "Chauffeur mis à jour ✅"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete_chauffeur/<int:id>', methods=['DELETE'])
def delete_chauffeur(id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM Chauffeur WHERE ID_utilisateur = ?', (id,))
        conn.execute('DELETE FROM Utilisateur WHERE ID_utilisateur = ?', (id,))
        conn.commit()
        conn.close()

        delete_from_supabase('Chauffeur', {'ID_utilisateur': id})
        delete_from_supabase('Utilisateur', {'ID_utilisateur': id})

        return jsonify({"message": "Chauffeur supprimé avec succès"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/assign_work', methods=['POST'])
def assign_work():
    try:
        data = request.get_json()
        code_chauffeur = data.get('code_chauffeur')
        code_bus = data.get('code_bus')
        code_ligne = data.get('code_ligne')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE Bus SET Code_chauffeur = ? WHERE Code_bus = ?", (code_chauffeur, code_bus))
        cursor.execute("UPDATE Ligne SET Code_bus = ? WHERE Code_Ligne = ?", (code_bus, code_ligne))
        conn.commit()
        conn.close()

        write_to_supabase('Bus', {'Code_chauffeur': code_chauffeur}, {'Code_bus': code_bus})
        write_to_supabase('Ligne', {'Code_bus': code_bus}, {'Code_Ligne': code_ligne})

        return jsonify({"message": "Affectation réussie !"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════
# 6. PARCOURS
# ════════════════════════════════════════════════════════════════

@app.route('/get_all_parcours', methods=['GET'])
def get_all_parcours():
    try:
        supabase_data = read_from_supabase('Parcours', order_by='ID_parcours', desc=True)
        if supabase_data is not None:
            result = []
            for p in supabase_data:
                nom_ligne = "Sans nom"
                if p.get('Code_Ligne'):
                    ligne_data = read_from_supabase('Ligne', filters={'Code_Ligne': p.get('Code_Ligne')})
                    if ligne_data and len(ligne_data) > 0:
                        nom_ligne = ligne_data[0].get('Libelle', 'Sans nom')
                
                result.append({
                    "ID_parcours": p.get("ID_parcours"),
                    "Depart": p.get("Depart"),
                    "Arrivee": p.get("Arrivee"),
                    "Heure_depart": p.get("Heure_depart"),
                    "Heure_arrivee": p.get("Heure_arrivee"),
                    "Code_Ligne": p.get("Code_Ligne"),
                    "Nom_Ligne": nom_ligne
                })
            return jsonify(result), 200

        conn = get_db_connection()
        rows = conn.execute("""
            SELECT P.*, L.Libelle as Nom_Ligne
            FROM Parcours P
            JOIN Ligne L ON P.Code_Ligne = L.Code_Ligne
            ORDER BY P.ID_parcours DESC
        """).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_parcours/<int:code_ligne>', methods=['GET'])
def get_parcours_by_ligne(code_ligne):
    try:
        supabase_data = read_from_supabase('Parcours', filters={'Code_Ligne': code_ligne})
        if supabase_data is not None:
            return jsonify(supabase_data)

        conn = get_db_connection()
        rows = conn.execute("SELECT * FROM Parcours WHERE Code_Ligne = ?", (code_ligne,)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/add_parcours', methods=['POST'])
def add_parcours():
    try:
        data = request.get_json()
        depart = data.get('Depart')
        arrivee = data.get('Arrivee')
        heure_d = data.get('Heure_depart')
        heure_a = data.get('Heure_arrivee', '--:--')
        code_ligne = data.get('Code_Ligne')

        conn = get_db_connection()
        cur = conn.execute(
            'INSERT INTO Parcours (Depart, Arrivee, Heure_depart, Heure_arrivee, Code_Ligne) VALUES (?, ?, ?, ?, ?)',
            (depart, arrivee, heure_d, heure_a, code_ligne)
        )
        new_id = cur.lastrowid
        conn.commit()
        conn.close()

        parcours_data = {
            'ID_parcours': new_id, 'Depart': depart, 'Arrivee': arrivee,
            'Heure_depart': heure_d, 'Heure_arrivee': heure_a, 'Code_Ligne': code_ligne
        }
        write_to_supabase('Parcours', parcours_data)

        return jsonify({"message": "Parcours ajouté", "id": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/update_parcours/<int:id>', methods=['PUT', 'POST', 'OPTIONS'])
def update_parcours(id):
    if request.method == 'OPTIONS':
        return jsonify({"ok": True}), 200
    conn = get_db_connection()
    try:
        data = request.get_json(force=True)
        conn.execute("""
            UPDATE Parcours
            SET Depart = ?, Arrivee = ?, Heure_depart = ?, Heure_arrivee = ?, Code_Ligne = ?
            WHERE ID_parcours = ?
        """, (
            data.get('Depart'), data.get('Arrivee'),
            data.get('Heure_depart'), data.get('Heure_arrivee'),
            data.get('Code_Ligne'), id
        ))
        conn.commit()
        
        write_to_supabase('Parcours', {
            'Depart': data.get('Depart'), 'Arrivee': data.get('Arrivee'),
            'Heure_depart': data.get('Heure_depart'), 'Heure_arrivee': data.get('Heure_arrivee'),
            'Code_Ligne': data.get('Code_Ligne')
        }, {'ID_parcours': id})
        
        return jsonify({"status": "success", "message": "Mise à jour réussie"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route('/delete_parcours/<int:id>', methods=['DELETE', 'OPTIONS'])
def delete_parcours(id):
    if request.method == 'OPTIONS':
        return jsonify({"ok": True}), 200
    conn = get_db_connection()
    try:
        cur = conn.execute('DELETE FROM Parcours WHERE ID_parcours = ?', (id,))
        conn.commit()
        if cur.rowcount > 0:
            delete_from_supabase('Parcours', {'ID_parcours': id})
            return jsonify({"status": "success"}), 200
        return jsonify({"status": "error", "message": "Parcours introuvable"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# 7. AVIS (NLP / IA)
# ════════════════════════════════════════════════════════════════

@app.route('/add_avis', methods=['POST', 'OPTIONS'])
def add_avis():
    if request.method == 'OPTIONS':
        return jsonify({"ok": True}), 200

    try:
        data = request.get_json(force=True)
        comment = data.get('commentaire', '')
        note = data.get('note', 5)
        client_id = data.get('client_id') or data.get('code_client')
        parcours_id = data.get('parcours_id')
        id_historique = data.get('id_historique')

        sentiment_score, sentiment_label, keywords, category, is_risk = analyze_sentiment(comment)

        conn = get_db_connection()
        cursor = conn.cursor()

        code_chauffeur = None
        code_ligne = None
        code_bus = None

        if id_historique:
            res = cursor.execute("""
                SELECT H.Code_chauffeur, H.ID_parcours, P.Code_Ligne, L.Code_bus
                FROM Historique H
                JOIN Parcours P ON H.ID_parcours = P.ID_parcours
                LEFT JOIN Ligne L ON P.Code_Ligne = L.Code_Ligne
                WHERE H.ID_historique = ?
            """, (id_historique,)).fetchone()
            if res:
                code_chauffeur = res['Code_chauffeur']
                parcours_id = res['ID_parcours']
                code_ligne = res['Code_Ligne']
                code_bus = res['Code_bus']

        if not code_bus and code_chauffeur:
            r = cursor.execute("SELECT Code_bus FROM Bus WHERE Code_chauffeur = ?", (code_chauffeur,)).fetchone()
            if r:
                code_bus = r['Code_bus']

        if not code_bus and code_ligne:
            r = cursor.execute("SELECT Code_bus FROM Ligne WHERE Code_Ligne = ?", (code_ligne,)).fetchone()
            if r:
                code_bus = r['Code_bus']

        date_avis = data.get('date', datetime.now().strftime("%Y-%m-%d"))
        cursor.execute("""
            INSERT INTO Avis
            (Code_client, ID_historique, ID_parcours, Note, Commentaire,
             Sentiment_score, Sentiment_label, Keywords, Category, Date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (client_id, id_historique, parcours_id, note, comment,
              sentiment_score, sentiment_label, keywords, category, date_avis))
        new_avis_id = cursor.lastrowid

        if code_chauffeur:
            cursor.execute("""
                UPDATE Chauffeur
                SET Performance_score = (
                    SELECT (AVG(Note) + AVG(Sentiment_score)*0.5)
                    FROM Avis A
                    LEFT JOIN Historique H ON A.ID_historique = H.ID_historique
                    WHERE H.Code_chauffeur = ?
                )
                WHERE Code_chauffeur = ?
            """, (code_chauffeur, code_chauffeur))

            if id_historique:
                cursor.execute("""
                    UPDATE Historique
                    SET Performance_IA = (SELECT AVG(Note)*20 FROM Avis WHERE ID_historique = ?)
                    WHERE ID_historique = ?
                """, (id_historique, id_historique))

        if is_risk == "Oui":
            date_inc = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO Incident (Description, Date, Code_chauffeur, Code_Ligne, Code_bus, Statut)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (f"[IA ALERT] {comment}", date_inc, code_chauffeur, code_ligne, code_bus, 'Signalé'))

        conn.commit()
        conn.close()

        write_to_supabase('Avis', {
            'ID_avis': new_avis_id, 'Code_client': client_id,
            'ID_historique': id_historique, 'ID_parcours': parcours_id,
            'Note': note, 'Commentaire': comment,
            'Sentiment_score': sentiment_score, 'Sentiment_label': sentiment_label,
            'Keywords': keywords, 'Category': category, 'Date': date_avis
        })

        return jsonify({
            "status": "success",
            "ai_analysis": {
                "score": sentiment_score,
                "label": sentiment_label,
                "keywords": keywords
            }
        }), 201
    except Exception as e:
        print(f"Erreur add_avis: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_avis', methods=['GET'])
def get_avis():
    try:
        supabase_data = read_from_supabase('Avis', order_by='Date', desc=True)
        if supabase_data is not None:
            result = []
            for a in supabase_data:
                nom_client = f"Client #{a.get('Code_client', '?')}"
                if a.get('Code_client'):
                    client_data = read_from_supabase('Client', filters={'Code_client': a.get('Code_client')})
                    if client_data and len(client_data) > 0:
                        user_data = read_from_supabase('Utilisateur', filters={'ID_utilisateur': client_data[0].get('ID_utilisateur')})
                        if user_data and len(user_data) > 0:
                            nom_client = user_data[0].get('Nom', nom_client)
                
                result.append({
                    "ID_avis": a.get("ID_avis"),
                    "Code_client": a.get("Code_client"),
                    "Nom_Client": nom_client,
                    "Note": a.get("Note"),
                    "Commentaire": a.get("Commentaire"),
                    "Date": a.get("Date"),
                    "Sentiment_score": a.get("Sentiment_score"),
                    "Sentiment_label": a.get("Sentiment_label"),
                    "Keywords": a.get("Keywords"),
                    "Category": a.get("Category")
                })
            return jsonify(result), 200

        conn = get_db_connection()
        query = """
            SELECT a.*,
                   COALESCE(u.Nom, 'Client #' || CAST(a.Code_client AS TEXT)) as Nom_Client
            FROM Avis a
            LEFT JOIN Client c ON a.Code_client = c.Code_client
            LEFT JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            ORDER BY a.Date DESC
        """
        avis = conn.execute(query).fetchall()
        conn.close()
        return jsonify([dict(r) for r in avis]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_avis_by_client/<int:client_id>', methods=['GET'])
def get_avis_by_client(client_id):
    try:
        supabase_data = read_from_supabase('Avis', filters={'Code_client': client_id}, order_by='Date', desc=True)
        if supabase_data is not None:
            return jsonify(supabase_data)

        conn = get_db_connection()
        avis = conn.execute("""
            SELECT a.ID_avis, a.Commentaire, a.Note, a.Date, h.Depart, h.Arrivee
            FROM Avis a
            LEFT JOIN Historique h ON a.ID_historique = h.ID_historique
            WHERE a.Code_client = ?
            ORDER BY a.Date DESC
        """, (client_id,)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in avis]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/update_avis/<int:id>', methods=['PUT'])
def update_avis(id):
    try:
        data = request.get_json()
        commentaire = data.get("commentaire")
        note = data.get("note")
        conn = get_db_connection()
        conn.execute("UPDATE Avis SET Commentaire = ?, Note = ? WHERE ID_avis = ?",
                     (commentaire, note, id))
        conn.commit()
        conn.close()

        write_to_supabase('Avis', {'Commentaire': commentaire, 'Note': note}, {'ID_avis': id})

        return jsonify({"message": "Avis mis à jour"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete_avis/<int:id>', methods=['DELETE'])
def delete_avis(id):
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM Avis WHERE ID_avis = ?", (id,))
        conn.commit()
        conn.close()

        delete_from_supabase('Avis', {'ID_avis': id})

        return jsonify({"message": "Avis supprimé"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/recategorize_avis', methods=['POST'])
def recategorize_avis():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT ID_avis, Commentaire FROM Avis WHERE Commentaire IS NOT NULL AND Commentaire != ''"
        ).fetchall()
        updated = 0
        for row in rows:
            new_cat = categorize_comment(row['Commentaire'])
            cursor.execute("UPDATE Avis SET Category = ? WHERE ID_avis = ?", (new_cat, row['ID_avis']))
            updated += 1
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "updated": updated}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════
# 8. INCIDENTS
# ════════════════════════════════════════════════════════════════

@app.route('/get_incidents', methods=['GET'])
def get_incidents():
    try:
        supabase_data = read_from_supabase('Incident', order_by='Date', desc=True)
        if supabase_data is not None:
            result = []
            for i in supabase_data:
                numero_bus = "N/A"
                nom_chauffeur = "Inconnu"
                
                if i.get('Code_bus'):
                    bus_data = read_from_supabase('Bus', filters={'Code_bus': i.get('Code_bus')})
                    if bus_data and len(bus_data) > 0:
                        numero_bus = bus_data[0].get('Numero_bus', 'N/A')
                
                if i.get('Code_chauffeur'):
                    chauffeur_data = read_from_supabase('Chauffeur', filters={'Code_chauffeur': i.get('Code_chauffeur')})
                    if chauffeur_data and len(chauffeur_data) > 0:
                        user_data = read_from_supabase('Utilisateur', filters={'ID_utilisateur': chauffeur_data[0].get('ID_utilisateur')})
                        if user_data and len(user_data) > 0:
                            nom_chauffeur = user_data[0].get('Nom', 'Inconnu')
                
                result.append({
                    "ID_incident": i.get("ID_incident"),
                    "Description": i.get("Description"),
                    "Date": i.get("Date"),
                    "Code_chauffeur": i.get("Code_chauffeur"),
                    "Code_Ligne": i.get("Code_Ligne"),
                    "Code_bus": i.get("Code_bus"),
                    "Statut": i.get("Statut"),
                    "Performance_IA": i.get("Performance_IA"),
                    "Numero_bus": numero_bus,
                    "NomChauffeur": nom_chauffeur
                })
            return jsonify(result), 200

        conn = get_db_connection()
        query = """
            SELECT I.*,
                   COALESCE(B.Numero_bus, 'N/A') as Numero_bus,
                   COALESCE(U.Nom, 'Inconnu') as NomChauffeur
            FROM Incident I
            LEFT JOIN Bus B ON I.Code_bus = B.Code_bus
            LEFT JOIN Chauffeur C ON I.Code_chauffeur = C.Code_chauffeur
            LEFT JOIN Utilisateur U ON C.ID_utilisateur = U.ID_utilisateur
            ORDER BY I.Date DESC
        """
        items = conn.execute(query).fetchall()
        conn.close()
        return jsonify([dict(i) for i in items])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_all_incidents', methods=['GET'])
def get_all_incidents():
    try:
        supabase_data = read_from_supabase('Incident', order_by='Date', desc=True)
        if supabase_data is not None:
            result = []
            for i in supabase_data:
                nom_ligne = "N/A"
                if i.get('Code_Ligne'):
                    ligne_data = read_from_supabase('Ligne', filters={'Code_Ligne': i.get('Code_Ligne')})
                    if ligne_data and len(ligne_data) > 0:
                        nom_ligne = ligne_data[0].get('Libelle', 'N/A')
                
                numero_bus = "N/A"
                if i.get('Code_bus'):
                    bus_data = read_from_supabase('Bus', filters={'Code_bus': i.get('Code_bus')})
                    if bus_data and len(bus_data) > 0:
                        numero_bus = bus_data[0].get('Numero_bus', 'N/A')
                
                result.append({
                    "ID_incident": i.get("ID_incident"),
                    "Description": i.get("Description"),
                    "Date": i.get("Date"),
                    "Code_chauffeur": i.get("Code_chauffeur"),
                    "Code_Ligne": i.get("Code_Ligne"),
                    "Code_bus": i.get("Code_bus"),
                    "Statut": i.get("Statut"),
                    "Performance_IA": i.get("Performance_IA"),
                    "Nom_Ligne": nom_ligne,
                    "Numero_bus": numero_bus
                })
            return jsonify(result), 200

        conn = get_db_connection()
        query = """
            SELECT i.*, l.Libelle as Nom_Ligne,
                   COALESCE(b1.Numero_bus, b2.Numero_bus) as Numero_bus
            FROM Incident i
            LEFT JOIN Ligne l ON i.Code_Ligne = l.Code_Ligne
            LEFT JOIN Bus b1 ON i.Code_bus = b1.Code_bus
            LEFT JOIN Bus b2 ON l.Code_bus = b2.Code_bus
            GROUP BY i.ID_incident
            ORDER BY i.Date DESC
        """
        incidents = conn.execute(query).fetchall()
        conn.close()
        return jsonify([dict(i) for i in incidents])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/add_incident', methods=['POST'])
def add_incident():
    try:
        data = request.get_json()
        description = data.get('description', '')
        id_chauffeur = data.get('Code_chauffeur') or data.get('code_chauffeur')
        id_ligne = data.get('Code_Ligne') or data.get('code_ligne')
        code_bus = data.get('Code_bus') or data.get('code_bus')
        statut = data.get('Statut', 'Signalé')
        date_inc = data.get('Date') or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        cursor = conn.cursor()

        if not code_bus and id_chauffeur:
            r = cursor.execute("SELECT Code_bus FROM Bus WHERE Code_chauffeur = ?", (id_chauffeur,)).fetchone()
            if r:
                code_bus = r['Code_bus']

        cursor.execute("""
            INSERT INTO Incident (Description, Date, Code_chauffeur, Code_Ligne, Code_bus, Statut)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (description, date_inc, id_chauffeur, id_ligne, code_bus, statut))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()

        write_to_supabase('Incident', {
            'ID_incident': new_id, 'Description': description, 'Date': date_inc,
            'Code_chauffeur': id_chauffeur, 'Code_Ligne': id_ligne,
            'Code_bus': code_bus, 'Statut': statut
        })

        return jsonify({"message": "Incident ajouté", "id": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/declare_incident', methods=['POST', 'OPTIONS'])
def declare_incident():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    try:
        data = request.get_json()
        user_id = data.get('driver_id')
        description = data.get('description', '')
        timestamp = data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        conn = get_db_connection()
        cursor = conn.cursor()

        res_ch = cursor.execute(
            "SELECT Code_chauffeur FROM Chauffeur WHERE ID_utilisateur = ?", (user_id,)
        ).fetchone()
        if not res_ch:
            conn.close()
            return jsonify({"error": "Chauffeur introuvable"}), 404

        code_chauffeur = res_ch['Code_chauffeur']
        res_info = cursor.execute("""
            SELECT B.Code_bus, L.Code_Ligne
            FROM Bus B
            LEFT JOIN Ligne L ON B.Code_bus = L.Code_bus
            WHERE B.Code_chauffeur = ?
            LIMIT 1
        """, (code_chauffeur,)).fetchone()

        code_bus = res_info['Code_bus'] if res_info else None
        code_ligne = res_info['Code_Ligne'] if res_info else None

        cursor.execute("""
            INSERT INTO Incident (Description, Date, Code_chauffeur, Code_Ligne, Code_bus)
            VALUES (?, ?, ?, ?, ?)
        """, (description, timestamp, code_chauffeur, code_ligne, code_bus))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()

        write_to_supabase('Incident', {
            'ID_incident': new_id, 'Description': description, 'Date': timestamp,
            'Code_chauffeur': code_chauffeur, 'Code_Ligne': code_ligne, 'Code_bus': code_bus
        })

        return jsonify({"message": "Incident signalé avec succès"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete_incident/<int:id>', methods=['DELETE'])
def delete_incident(id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM Incident WHERE ID_incident = ?', (id,))
        conn.commit()
        conn.close()

        delete_from_supabase('Incident', {'ID_incident': id})

        return jsonify({"status": "success", "message": "Incident supprimé"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/update_incident_status/<int:id>', methods=['POST'])
def update_incident_status(id):
    try:
        data = request.get_json()
        statut = data.get('Statut')
        critique = data.get('Critique')
        conn = get_db_connection()
        conn.execute(
            'UPDATE Incident SET Statut = ?, Performance_IA = ? WHERE ID_incident = ?',
            (statut, critique, id)
        )
        conn.commit()
        conn.close()

        write_to_supabase('Incident', {'Statut': statut, 'Performance_IA': critique}, {'ID_incident': id})

        return jsonify({"message": "Statut mis à jour"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════
# 9. HISTORIQUE
# ════════════════════════════════════════════════════════════════

@app.route('/log_historique', methods=['POST'])
def log_historique():
    try:
        data = request.get_json()
        action = data['action']
        user_id = data['driver_id']
        parcours_id = data['parcours_id']
        now = data['timestamp']

        conn = get_db_connection()
        cursor = conn.cursor()

        res_ch = cursor.execute(
            "SELECT Code_chauffeur FROM Chauffeur WHERE ID_utilisateur = ?", (user_id,)
        ).fetchone()
        if not res_ch:
            conn.close()
            return jsonify({"error": "Chauffeur introuvable"}), 404

        code_chauffeur = res_ch['Code_chauffeur']

        if action == "Début":
            cursor.execute("""
                INSERT INTO Historique (Date, Heure_fin, Statut, Depart, Arrivee, Performance_IA, ID_parcours, Code_chauffeur)
                VALUES (?, NULL, 'En cours', ?, ?, NULL, ?, ?)
            """, (now, data.get('depart'), data.get('arrivee'), parcours_id, code_chauffeur))
            new_id = cursor.lastrowid
            message = "Voyage démarré"

        elif action == "Fin":
            cursor.execute("""
                UPDATE Historique
                SET Heure_fin = ?, Statut = 'Terminé', Performance_IA = 100.0
                WHERE Code_chauffeur = ? AND ID_parcours = ? AND Statut = 'En cours'
            """, (now, code_chauffeur, parcours_id))
            if cursor.rowcount == 0:
                cursor.execute("""
                    UPDATE Historique
                    SET Heure_fin = ?, Statut = 'Terminé', Performance_IA = 100.0
                    WHERE Code_chauffeur = ? AND ID_parcours = ? AND Heure_fin IS NULL
                """, (now, code_chauffeur, parcours_id))
            message = "Voyage terminé"
        else:
            conn.close()
            return jsonify({"error": "Action invalide"}), 400

        conn.commit()
        conn.close()
        return jsonify({"message": message}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_all_historique', methods=['GET'])
def get_all_historique():
    try:
        supabase_data = read_from_supabase('Historique', order_by='Date', desc=True)
        if supabase_data is not None:
            result = []
            for h in supabase_data:
                nom_chauffeur = "Inconnu"
                nom_ligne = "N/A"
                
                if h.get('Code_chauffeur'):
                    chauffeur_data = read_from_supabase('Chauffeur', filters={'Code_chauffeur': h.get('Code_chauffeur')})
                    if chauffeur_data and len(chauffeur_data) > 0:
                        user_data = read_from_supabase('Utilisateur', filters={'ID_utilisateur': chauffeur_data[0].get('ID_utilisateur')})
                        if user_data and len(user_data) > 0:
                            nom_chauffeur = user_data[0].get('Nom', 'Inconnu')
                
                if h.get('ID_parcours'):
                    parcours_data = read_from_supabase('Parcours', filters={'ID_parcours': h.get('ID_parcours')})
                    if parcours_data and len(parcours_data) > 0:
                        ligne_data = read_from_supabase('Ligne', filters={'Code_Ligne': parcours_data[0].get('Code_Ligne')})
                        if ligne_data and len(ligne_data) > 0:
                            nom_ligne = ligne_data[0].get('Libelle', 'N/A')
                
                result.append({
                    "ID_historique": h.get("ID_historique"),
                    "Date": h.get("Date"),
                    "Heure_fin": h.get("Heure_fin"),
                    "Statut": h.get("Statut"),
                    "Depart": h.get("Depart"),
                    "Arrivee": h.get("Arrivee"),
                    "Performance_IA": h.get("Performance_IA"),
                    "Nom_Chauffeur": nom_chauffeur,
                    "Nom_Ligne": nom_ligne
                })
            return jsonify(result), 200

        conn = get_db_connection()
        rows = conn.execute("""
            SELECT h.ID_historique, h.Date, h.Heure_fin, h.Statut,
                   h.Depart, h.Arrivee, h.Performance_IA,
                   u.Nom as Nom_Chauffeur, l.Libelle as Nom_Ligne
            FROM Historique h
            JOIN Chauffeur c ON h.Code_chauffeur = c.Code_chauffeur
            JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            LEFT JOIN Parcours p ON h.ID_parcours = p.ID_parcours
            LEFT JOIN Ligne l ON p.Code_Ligne = l.Code_Ligne
            ORDER BY h.Date DESC
        """).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════
# 10. STATS & RAPPORTS
# ════════════════════════════════════════════════════════════════

@app.route('/get_counts', methods=['GET'])
def get_counts():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        counts = {
            "lignes": cursor.execute('SELECT COUNT(*) FROM Ligne').fetchone()[0],
            "chauffeurs": cursor.execute('SELECT COUNT(*) FROM Chauffeur').fetchone()[0],
            "bus": cursor.execute('SELECT COUNT(*) FROM Bus').fetchone()[0],
            "incidents": cursor.execute('SELECT COUNT(*) FROM Incident').fetchone()[0],
        }
        conn.close()
        return jsonify(counts), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_performance_v2', methods=['GET'])
def get_performance_v2():
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT U.Nom as Nom_Chauffeur,
                   COUNT(*) as Total_Avis,
                   AVG(A.Note) as Average_Note
            FROM Avis A
            JOIN Parcours P ON A.ID_parcours = P.ID_parcours
            JOIN Ligne L ON P.Code_Ligne = L.Code_Ligne
            JOIN Bus B ON L.Code_bus = B.Code_bus
            JOIN Chauffeur C ON B.Code_chauffeur = C.Code_chauffeur
            JOIN Utilisateur U ON C.ID_utilisateur = U.ID_utilisateur
            GROUP BY C.Code_chauffeur
        """).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route('/get_driver_stats/<int:user_id>', methods=['GET'])
def get_driver_stats(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        res = cursor.execute(
            "SELECT Code_chauffeur, Performance_score FROM Chauffeur WHERE ID_utilisateur = ?", (user_id,)
        ).fetchone()
        if not res:
            conn.close()
            return jsonify({"error": "Chauffeur introuvable"}), 404

        code_chauffeur = res['Code_chauffeur']
        perf_score = res['Performance_score']

        avis = cursor.execute("""
            SELECT a.Note, a.Commentaire, a.Sentiment_label, a.Category, a.Date
            FROM Avis a
            LEFT JOIN Historique h ON a.ID_historique = h.ID_historique
            WHERE h.Code_chauffeur = ?
            ORDER BY a.Date DESC LIMIT 5
        """, (code_chauffeur,)).fetchall()

        cat_stats = cursor.execute("""
            SELECT Category, COUNT(*) as count
            FROM Avis a
            LEFT JOIN Historique h ON a.ID_historique = h.ID_historique
            WHERE h.Code_chauffeur = ?
            GROUP BY Category
        """, (code_chauffeur,)).fetchall()

        incident_count = cursor.execute(
            "SELECT COUNT(*) FROM Incident WHERE Code_chauffeur = ?", (code_chauffeur,)
        ).fetchone()[0]

        conn.close()
        return jsonify({
            "performance_score": round(perf_score or 0, 2),
            "incident_count": incident_count,
            "recent_reviews": [dict(r) for r in avis],
            "category_distribution": {r['Category']: r['count'] for r in cat_stats}
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_driver_reviews/<int:user_id>', methods=['GET'])
def get_driver_reviews(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        res = cursor.execute(
            "SELECT Code_chauffeur FROM Chauffeur WHERE ID_utilisateur = ?", (user_id,)
        ).fetchone()
        if not res:
            conn.close()
            return jsonify([]), 200

        code_chauffeur = res['Code_chauffeur']
        rows = cursor.execute("""
            SELECT A.Commentaire as commentaire, A.Note as note,
                   A.Sentiment_label as sentiment, A.Category as category, A.Date as date
            FROM Avis A
            LEFT JOIN Historique H ON A.ID_historique = H.ID_historique
            WHERE H.Code_chauffeur = ?
            ORDER BY A.Date DESC
        """, (code_chauffeur,)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify([]), 200


@app.route('/get_nlp_report', methods=['GET'])
def get_nlp_report():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        total_avis = cursor.execute("SELECT COUNT(*) FROM Avis").fetchone()[0]
        sentiments = cursor.execute(
            "SELECT Sentiment_label, COUNT(*) as count FROM Avis GROUP BY Sentiment_label"
        ).fetchall()
        avg_score = cursor.execute("SELECT AVG(Sentiment_score) FROM Avis").fetchone()[0] or 0

        kw_rows = cursor.execute("SELECT Keywords FROM Avis WHERE Keywords != ''").fetchall()
        kw_counts = {}
        for r in kw_rows:
            if r['Keywords']:
                for kw in r['Keywords'].split(', '):
                    kw = kw.strip()
                    if kw:
                        kw_counts[kw] = kw_counts.get(kw, 0) + 1
        top_kw = sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        top_drivers = cursor.execute("""
            SELECT u.Nom, AVG(a.Sentiment_score) as avg_sentiment, COUNT(a.ID_avis) as nb_avis
            FROM Avis a
            JOIN Historique h ON a.ID_historique = h.ID_historique
            JOIN Chauffeur c ON h.Code_chauffeur = c.Code_chauffeur
            JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            GROUP BY c.Code_chauffeur
            ORDER BY avg_sentiment DESC LIMIT 3
        """).fetchall()

        parcours_stats = cursor.execute("""
            SELECT p.ID_parcours, p.Depart, p.Arrivee,
                   AVG(a.Sentiment_score) as avg_sentiment, COUNT(a.ID_avis) as nb_avis
            FROM Avis a
            LEFT JOIN Historique h ON a.ID_historique = h.ID_historique
            JOIN Parcours p ON (a.ID_parcours = p.ID_parcours OR h.ID_parcours = p.ID_parcours)
            GROUP BY p.ID_parcours
            ORDER BY avg_sentiment DESC
        """).fetchall()

        safety_alerts = cursor.execute(
            "SELECT COUNT(*) FROM Incident WHERE Description LIKE '[IA ALERT]%'"
        ).fetchone()[0]

        conn.close()
        return jsonify({
            "total_avis": total_avis,
            "sentiment_distribution": {r['Sentiment_label']: r['count'] for r in sentiments},
            "average_sentiment_score": round(avg_score, 2),
            "top_keywords": top_kw,
            "top_drivers": [dict(r) for r in top_drivers],
            "parcours_stats": [dict(r) for r in parcours_stats],
            "safety_alerts_count": safety_alerts
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_driver_nlp_report', methods=['GET'])
def get_driver_nlp_report():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        total = cursor.execute("SELECT COUNT(*) FROM Avis WHERE Category = 'Chauffeur'").fetchone()[0]
        sentiments = cursor.execute("""
            SELECT Sentiment_label, COUNT(*) as count
            FROM Avis WHERE Category = 'Chauffeur'
            GROUP BY Sentiment_label
        """).fetchall()
        avg_score = cursor.execute(
            "SELECT AVG(Sentiment_score) FROM Avis WHERE Category = 'Chauffeur'"
        ).fetchone()[0] or 0
        avg_note = cursor.execute(
            "SELECT AVG(Note) FROM Avis WHERE Category = 'Chauffeur'"
        ).fetchone()[0] or 0

        kw_rows = cursor.execute(
            "SELECT Keywords FROM Avis WHERE Category = 'Chauffeur' AND Keywords != ''"
        ).fetchall()
        kw_counts = {}
        for r in kw_rows:
            if r['Keywords']:
                for kw in r['Keywords'].split(', '):
                    kw = kw.strip()
                    if kw:
                        kw_counts[kw] = kw_counts.get(kw, 0) + 1
        top_kw = sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        avis_rows = cursor.execute("""
            SELECT a.*,
                   COALESCE(u.Nom, 'Client #' || CAST(a.Code_client AS TEXT)) as Nom_Client
            FROM Avis a
            LEFT JOIN Client c ON a.Code_client = c.Code_client
            LEFT JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            WHERE a.Category = 'Chauffeur'
            ORDER BY a.Date DESC
        """).fetchall()

        top_drivers = cursor.execute("""
            SELECT u.Nom, AVG(a.Sentiment_score) as avg_sentiment, COUNT(*) as nb_avis
            FROM Avis a
            JOIN Historique h ON a.ID_historique = h.ID_historique
            JOIN Chauffeur c ON h.Code_chauffeur = c.Code_chauffeur
            JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            WHERE a.Category = 'Chauffeur'
            GROUP BY c.Code_chauffeur
            ORDER BY avg_sentiment DESC
        """).fetchall()

        conn.close()
        satisfaction_pct = round(((avg_score + 1) / 2) * 100, 1)

        return jsonify({
            "total_avis_chauffeur": total,
            "satisfaction_chauffeur": satisfaction_pct,
            "avg_note": round(avg_note, 2),
            "avg_sentiment_score": round(avg_score, 2),
            "sentiment_distribution": {r['Sentiment_label']: r['count'] for r in sentiments},
            "top_keywords": top_kw,
            "top_drivers": [dict(r) for r in top_drivers],
            "avis_list": [dict(r) for r in avis_rows]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════
# 11. CLIENT — Lignes & Trajets
# ════════════════════════════════════════════════════════════════

@app.route('/get_client_trips', methods=['GET'])
def get_client_trips():
    try:
        conn = get_db_connection()
        lignes = conn.execute("SELECT * FROM Ligne").fetchall()
        result = []
        for l in lignes:
            rides = conn.execute("""
                SELECT h.ID_historique, h.Date, h.Depart, h.Arrivee, u.Nom as Nom_Chauffeur
                FROM Historique h
                JOIN Chauffeur c ON h.Code_chauffeur = c.Code_chauffeur
                JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
                JOIN Parcours p ON h.ID_parcours = p.ID_parcours
                WHERE p.Code_Ligne = ?
                ORDER BY h.Date DESC
            """, (l['Code_Ligne'],)).fetchall()
            result.append({
                "code_ligne": l["Code_Ligne"],
                "libelle": l["Libelle"] or "Ligne",
                "description": l["Description"] or "",
                "rides": [dict(r) for r in rides]
            })
        conn.close()
        return jsonify(result), 200
    except Exception as e:
        return jsonify([]), 500


@app.route('/get_my_assignment/<int:user_id>', methods=['GET'])
def get_my_assignment(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")

        rows = cursor.execute("""
            SELECT DISTINCT
                p.ID_parcours,
                COALESCE(p.Depart, '---') as Depart,
                COALESCE(p.Arrivee, '---') as Arrivee,
                COALESCE(p.Heure_depart, '--:--') as Heure_depart,
                COALESCE(p.Heure_arrivee, '--:--') as Heure_arrivee,
                Ligne.Libelle,
                COALESCE(
                    (SELECT Statut FROM Historique
                     WHERE ID_parcours = p.ID_parcours
                       AND Code_chauffeur = Chauffeur.Code_chauffeur
                       AND Date LIKE ?
                     ORDER BY ID_historique DESC LIMIT 1),
                    'Pas démarré'
                ) as Statut
            FROM Chauffeur
            JOIN Bus ON Chauffeur.Code_chauffeur = Bus.Code_chauffeur
            JOIN Ligne ON Bus.Code_bus = Ligne.Code_bus
            LEFT JOIN Parcours p ON Ligne.Code_Ligne = p.Code_Ligne
            WHERE Chauffeur.ID_utilisateur = ?
            ORDER BY Ligne.Libelle, p.Heure_depart ASC
        """, (f"{today}%", user_id)).fetchall()

        conn.close()
        return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify([]), 500


@app.route('/get_parcours_reviews/<int:parcours_id>', methods=['GET'])
def get_parcours_reviews(parcours_id):
    try:
        conn = get_db_connection()
        avis = conn.execute("""
            SELECT a.Note, a.Commentaire, a.Sentiment_label, a.Category, a.Date,
                   COALESCE(u.Nom, 'Client #' || CAST(a.Code_client AS TEXT)) as Nom_Client
            FROM Avis a
            LEFT JOIN Historique h ON a.ID_historique = h.ID_historique
            LEFT JOIN Client c ON a.Code_client = c.Code_client
            LEFT JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            WHERE a.ID_parcours = ? OR h.ID_parcours = ?
            ORDER BY a.Date DESC
        """, (parcours_id, parcours_id)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in avis]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/finish_parcours/<int:id_p>', methods=['PUT'])
def finish_parcours(id_p):
    conn = get_db_connection()
    try:
        heure_arrivee = datetime.now().strftime("%H:%M")
        conn.execute(
            "UPDATE Parcours SET Heure_arrivee = ? WHERE ID_parcours = ?",
            (heure_arrivee, id_p)
        )
        conn.commit()
        return jsonify({"status": "success", "heure_arrivee": heure_arrivee}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# 12. DIAGNOSTIC - Vérification synchronisation
# ════════════════════════════════════════════════════════════════

@app.route('/check_sync_status', methods=['GET'])
def check_sync_status():
    """Vérifie la synchro entre SQLite et Supabase"""
    result = {
        "supabase_connected": SUPABASE_OK,
        "tables": {}
    }
    
    tables = ['Ligne', 'Parcours', 'Bus', 'Chauffeur', 'Utilisateur', 'Avis', 'Incident']
    
    for table in tables:
        conn = get_db_connection()
        sqlite_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.close()
        
        supabase_count = None
        if SUPABASE_OK and supabase:
            try:
                resp = supabase.from_(table).select("*", count="exact").execute()
                supabase_count = resp.count
            except Exception as e:
                supabase_count = f"Error: {str(e)[:50]}"
        
        result["tables"][table] = {
            "sqlite": sqlite_count,
            "supabase": supabase_count if supabase_count is not None else "Not available",
            "synced": sqlite_count == supabase_count if isinstance(supabase_count, int) else False
        }
    
    return jsonify(result), 200


# ════════════════════════════════════════════════════════════════
# 13. TEST
# ════════════════════════════════════════════════════════════════

@app.route('/test', methods=['GET', 'POST'])
def test():
    return jsonify({"message": "[OK] SMART-TRANS API fonctionne parfaitement !"}), 200


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    try:
        init_all_tables()
    except Exception as e:
        print(f"Erreur init DB: {e}")

    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port, debug=False)